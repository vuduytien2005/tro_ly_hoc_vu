"""/api/documents/{id}/file: mở văn bản gốc từ trích dẫn."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.assistant_api.models import NguoiDung, VanBan
from src.assistant_api.routers import admin as admin_router
from tests.assistant.conftest import login

PDF = b"%PDF-1.4\n% gia lap\n"


@pytest.fixture
def uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(admin_router, "upload_dir", lambda: root)
    return root


@pytest.fixture
def make_doc(db: Session) -> Callable[..., int]:
    def make(path: Path, trang_thai: str = "da_lap_chi_muc") -> int:
        vb = VanBan(
            ten="Quy chế đào tạo (thử)",
            loai="quy_che",
            phien_ban="2023",
            ten_tep=path.name,
            duong_dan_tep=str(path),
            trang_thai=trang_thai,
        )
        db.add(vb)
        db.commit()
        return vb.id

    return make


def test_student_opens_indexed_pdf_inline(
    client: TestClient, student: NguoiDung, uploads: Path, make_doc: Callable[..., int]
) -> None:
    path = uploads / "quy_che.pdf"
    path.write_bytes(PDF)
    r = client.get(f"/api/documents/{make_doc(path)}/file", headers=login(client, student.email))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.content == PDF


def test_requires_login(client: TestClient, uploads: Path, make_doc: Callable[..., int]) -> None:
    path = uploads / "quy_che.pdf"
    path.write_bytes(PDF)
    assert client.get(f"/api/documents/{make_doc(path)}/file").status_code == 401


def test_not_indexed_or_missing_is_404(
    client: TestClient, student: NguoiDung, uploads: Path, make_doc: Callable[..., int]
) -> None:
    headers = login(client, student.email)
    path = uploads / "dang_xu_ly.pdf"
    path.write_bytes(PDF)
    r = client.get(f"/api/documents/{make_doc(path, 'dang_xu_ly')}/file", headers=headers)
    assert (r.status_code, r.json()["code"]) == (404, "VAN_BAN_KHONG_TON_TAI")
    gone = make_doc(uploads / "khong_co.pdf")
    assert client.get(f"/api/documents/{gone}/file", headers=headers).status_code == 404
    assert client.get("/api/documents/999999999/file", headers=headers).status_code == 404


def test_file_outside_upload_dir_is_refused(
    client: TestClient,
    student: NguoiDung,
    uploads: Path,
    tmp_path: Path,
    make_doc: Callable[..., int],
) -> None:
    outside = tmp_path / "bi_mat.txt"
    outside.write_text("không được lộ", encoding="utf-8")
    r = client.get(f"/api/documents/{make_doc(outside)}/file", headers=login(client, student.email))
    assert r.status_code == 404


# ----- Nguyên văn Điều qua MCP resource (bổ sung 23/11/2026) -----------------------------------
@pytest.fixture
def article_doc(
    db: Session, session_factory: Callable[[], Session], monkeypatch: pytest.MonkeyPatch
) -> int:
    from src.assistant_api.models import DoanVanBan
    from src.mcp_servers import quy_che

    monkeypatch.setattr(quy_che, "assistant_session_factory", lambda: session_factory)
    vb = VanBan(
        ten="Quy chế đào tạo (thử)",
        loai="quy_che",
        phien_ban="2023",
        ten_tep="qc.pdf",
        duong_dan_tep="qc.pdf",
        trang_thai="da_lap_chi_muc",
    )
    db.add(vb)
    db.flush()
    for i, (dieu, body) in enumerate(
        [
            ("Điều 12. Đăng ký học phần", "1. Sinh viên đăng ký tối đa 25 tín chỉ."),
            ("Điều 12. Đăng ký học phần", "2. Đăng ký muộn phải có đơn."),
            ("Điều 13. Rút học phần", "1. Được rút trong 4 tuần đầu."),
        ]
    ):
        db.add(
            DoanVanBan(
                van_ban_id=vb.id,
                thu_tu=i,
                dieu=dieu,
                trang=8,
                noi_dung=f"{dieu}\n{body}",
                vector_id=f"test_vb{vb.id}_d{i}",
            )
        )
    db.commit()
    return vb.id


def test_student_reads_article_via_mcp_resource(
    client: TestClient, student: NguoiDung, article_doc: int, db: Session
) -> None:
    from sqlalchemy import func, select

    from src.assistant_api.models import LuotGoiCongCu

    before = db.scalar(select(func.count()).select_from(LuotGoiCongCu))
    r = client.get(
        f"/api/documents/{article_doc}/articles/12", headers=login(client, student.email)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["so_dieu"] == 12
    assert "tối đa 25 tín chỉ" in body["noi_dung"] and "Đăng ký muộn" in body["noi_dung"]
    assert "Rút học phần" not in body["noi_dung"]
    assert "<tai_lieu" not in body["noi_dung"]
    # resource do ứng dụng đọc, không phải lượt gọi công cụ
    assert db.scalar(select(func.count()).select_from(LuotGoiCongCu)) == before


@pytest.mark.parametrize("so", ["99", "abc", "12345"])
def test_missing_or_bad_article_is_404(
    client: TestClient, student: NguoiDung, article_doc: int, so: str
) -> None:
    r = client.get(
        f"/api/documents/{article_doc}/articles/{so}", headers=login(client, student.email)
    )
    assert r.status_code == 404
    assert r.json()["code"] == "DIEU_KHONG_TON_TAI"


def test_article_requires_login(client: TestClient, article_doc: int) -> None:
    assert client.get(f"/api/documents/{article_doc}/articles/12").status_code == 401

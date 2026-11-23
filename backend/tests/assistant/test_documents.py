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

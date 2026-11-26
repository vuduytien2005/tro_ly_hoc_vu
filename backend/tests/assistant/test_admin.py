"""API quản trị (/api/admin/*): phân quyền, tài liệu (lập chỉ mục qua quy_che), MCP & quyền,
nhật ký, thống kê, kịch bản demo 7.

Server quy_che chạy TRONG tiến trình (httpx.ASGITransport tới app thật, có middleware Bearer),
dùng Chroma tạm + HashingEmbedder; lập chỉ mục chạy đồng bộ thay cho luồng nền.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient as StarletteClient

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.agent.registry import ToolRegistry
from src.assistant_api.deps import get_db
from src.assistant_api.main import create_app
from src.assistant_api.models import (
    CongCu,
    DanhGiaCauTraLoi,
    HanhDongChoXacNhan,
    HoiThoai,
    LuotGoiCongCu,
    McpServer,
    NguoiDung,
    TinNhan,
    VanBan,
)
from src.assistant_api.rag_admin import RagAdminClient
from src.assistant_api.routers import admin as admin_router
from src.mcp_servers import quy_che
from src.mcp_servers.common import build_app
from src.rag import retriever as rag
from src.rag.embedder import HashingEmbedder
from src.rag.retriever import Retriever
from src.rag.store import VectorStore
from src.shared.config import get_settings
from tests.assistant.conftest import login

SAMPLE = Path(__file__).parents[1] / "rag" / "fixtures" / "quy_che_mau.txt"
DOC = "Quy chế thử nghiệm GĐ8"
QUY_CHE_URL = "http://127.0.0.1:9104"


@pytest.fixture
def quy_che_inproc(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    session_factory: Callable[[], Session],
    db: Session,
) -> Retriever:
    """quy_che dùng CSDL của test (rollback), Chroma tạm, embedder giả, chạy đồng bộ."""
    db.execute(delete(VanBan))  # cô lập khỏi văn bản thật (bị rollback cuối test)
    db.commit()
    embedder = HashingEmbedder()
    retriever = Retriever(
        session_factory, VectorStore(tmp_path / "chroma", embedder.name), embedder
    )
    monkeypatch.setattr(rag, "get_retriever", lambda: retriever)
    monkeypatch.setattr(quy_che, "assistant_session_factory", lambda: session_factory)
    monkeypatch.setattr(quy_che, "_spawn", lambda fn, *args: fn(*args))
    monkeypatch.setattr(admin_router, "upload_dir", lambda: tmp_path / "uploads")
    return retriever


def _client(
    session_factory: Callable[[], Session],
    registry: ToolRegistry,
    llm: FakeLLM,
    db: Session,
    rag_admin: RagAdminClient,
) -> Iterator[TestClient]:
    import anyio

    anyio.run(registry.sync, db)
    app = create_app(
        registry=registry, llm=llm, session_factory=session_factory, rag_admin=rag_admin
    )

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session
            if session.in_transaction():
                session.commit()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_client(
    session_factory: Callable[[], Session],
    registry: ToolRegistry,
    fake_llm: FakeLLM,
    db: Session,
    quy_che_inproc: Retriever,
) -> Iterator[TestClient]:
    transport = httpx.ASGITransport(app=build_app(quy_che.mcp))
    yield from _client(
        session_factory, registry, fake_llm, db, RagAdminClient(QUY_CHE_URL, transport)
    )


@pytest.fixture
def ad(admin_client: TestClient, admin: NguoiDung) -> dict[str, str]:
    return login(admin_client, admin.email)


def upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    content: bytes | None = None,
    filename: str = "quy_che.txt",
    **fields: str,
) -> httpx.Response:
    data = {"ten": DOC, "loai": "quy_che", "phien_ban": "2099", "ap_dung_tu_khoa": "K22"}
    data.update(fields)
    body = SAMPLE.read_bytes() if content is None else content
    return client.post(
        "/api/admin/documents",
        data=data,
        files={"tep": (filename, body, "text/plain")},
        headers=headers,
    )


def search(client: TestClient, headers: dict[str, str], **body: object) -> dict:
    payload = {"cau_hoi": "học lại học phần bị điểm F", "ma_khoa": "K22", "top_k": 5, **body}
    r = client.post("/api/admin/rag/search", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ----- Phân quyền -------------------------------------------------------------
def test_requires_admin(client: TestClient, student: NguoiDung) -> None:
    assert client.get("/api/admin/stats").json()["code"] == "CHUA_DANG_NHAP"
    r = client.get("/api/admin/stats", headers=login(client, student.email))
    assert r.status_code == 403


def test_quy_che_internal_routes_require_token() -> None:
    with StarletteClient(build_app(quy_che.mcp), base_url=QUY_CHE_URL) as c:
        assert c.post("/internal/rag/search", json={"cau_hoi": "abc"}).status_code == 401
        assert c.delete("/internal/documents/1").status_code == 401
        bad = {"Authorization": "Bearer sai"}
        assert c.post("/internal/documents/1/index", headers=bad).status_code == 401


# ----- Tài liệu -----------------------------------------------------------------
def test_upload_index_search_and_delete(admin_client: TestClient, ad: dict[str, str]) -> None:
    r = upload(admin_client, ad)
    assert r.status_code == 202, r.text
    doc = r.json()
    # quy_che lập chỉ mục xong (chạy đồng bộ trong test) -> tìm được NGAY
    assert doc["trang_thai"] == "da_lap_chi_muc" and doc["so_doan"] > 0
    assert doc["ten_tep"] == "quy_che.txt" and doc["ap_dung_tu_khoa"] == 22
    assert doc["created_at"].endswith("+07:00")

    listed = admin_client.get("/api/admin/documents", headers=ad).json()
    assert [d["id"] for d in listed] == [doc["id"]]

    page = admin_client.get(
        f"/api/admin/documents/{doc['id']}/chunks?page=1&page_size=3", headers=ad
    ).json()
    assert page["tong"] == doc["so_doan"] and len(page["doan"]) == 3
    assert [c["thu_tu"] for c in page["doan"]] == sorted(c["thu_tu"] for c in page["doan"])

    out = search(admin_client, ad)
    assert out["doan"] and {d["van_ban"] for d in out["doan"]} == {DOC}
    first = out["doan"][0]
    assert first["so"] == 1 and first["diem"] > 0
    assert first["hang_vector"] is not None or first["hang_tu_khoa"] is not None

    # Lọc phiên bản: văn bản áp dụng từ K22 -> K21 không thấy; tắt lọc thì thấy
    assert search(admin_client, ad, ma_khoa="K21")["doan"] == []
    assert search(admin_client, ad, ma_khoa="K21", use_version_filter=False)["doan"]
    only_kw = search(admin_client, ad, use_vector=False)["doan"]
    assert only_kw and all(d["hang_vector"] is None for d in only_kw)
    assert search(admin_client, ad, use_rerank=True)["ghi_chu"]  # chưa cấu hình reranker

    stored = Path(admin_router.upload_dir()) / next(
        p.name for p in Path(admin_router.upload_dir()).iterdir()
    )
    assert stored.is_file()
    assert admin_client.delete(f"/api/admin/documents/{doc['id']}", headers=ad).status_code == 204
    assert not stored.exists()
    assert search(admin_client, ad)["doan"] == []
    assert admin_client.get("/api/admin/documents", headers=ad).json() == []


def test_reupload_replaces_and_reindex(admin_client: TestClient, ad: dict[str, str]) -> None:
    first = upload(admin_client, ad).json()
    shorter = SAMPLE.read_text(encoding="utf-8").split("Điều 3")[0].encode("utf-8")
    second = upload(admin_client, ad, content=shorter, filename="ban_moi.txt").json()
    assert second["id"] == first["id"]  # cùng tên + loại + phiên bản -> thay thế
    assert second["ten_tep"] == "ban_moi.txt" and second["so_doan"] < first["so_doan"]
    assert len(list(admin_router.upload_dir().iterdir())) == 1  # tệp cũ đã xóa

    r = admin_client.post(f"/api/admin/documents/{first['id']}/reindex", headers=ad)
    assert r.status_code == 202 and r.json()["trang_thai"] == "da_lap_chi_muc"

    for f in admin_router.upload_dir().iterdir():
        f.unlink()
    r = admin_client.post(f"/api/admin/documents/{first['id']}/reindex", headers=ad)
    assert r.status_code == 409 and r.json()["code"] == "TEP_GOC_KHONG_CON"


def test_index_failure_is_recorded(admin_client: TestClient, ad: dict[str, str]) -> None:
    r = upload(admin_client, ad, content=b"   \n\n  \n")
    assert r.status_code == 202
    assert r.json()["trang_thai"] == "loi"
    assert "Không trích được nội dung" in r.json()["loi"]


@pytest.mark.parametrize(
    ("filename", "content", "fields", "status", "code"),
    [
        ("virus.exe", b"MZ...", {}, 415, "DINH_DANG_KHONG_HO_TRO"),
        ("gia.pdf", b"khong phai pdf", {}, 415, "TEP_KHONG_HOP_LE"),
        ("rong.txt", b"", {}, 422, "TEP_RONG"),
        ("a.txt", b"Dieu 1.", {"ap_dung_tu_khoa": "23", "ap_dung_den_khoa": "22"}, 422, None),
        ("a.txt", b"Dieu 1.", {"ap_dung_tu_khoa": "abc"}, 422, None),
        ("a.txt", b"Dieu 1.", {"loai": "bi_mat"}, 422, None),
    ],
)
def test_upload_validation(
    admin_client: TestClient,
    ad: dict[str, str],
    filename: str,
    content: bytes,
    fields: dict[str, str],
    status: int,
    code: str | None,
) -> None:
    r = upload(admin_client, ad, content=content, filename=filename, **fields)
    assert r.status_code == status, r.text
    if code:
        assert r.json()["code"] == code
    assert admin_client.get("/api/admin/documents", headers=ad).json() == []
    assert not list(admin_router.upload_dir().glob("*"))  # không để lại tệp rác


def test_safe_filename_blocks_traversal() -> None:
    assert admin_router.safe_filename("..\\..\\windows\\evil.PDF") == "evil.pdf"
    assert admin_router.safe_filename("../../etc/passwd") == "passwd"
    assert admin_router.safe_filename("Quy chế 2023 (bản sửa).docx") == "Quy chế 2023 _bản sửa.docx"


def test_quy_che_down_marks_document_failed(
    session_factory: Callable[[], Session],
    registry: ToolRegistry,
    fake_llm: FakeLLM,
    db: Session,
    admin: NguoiDung,
    quy_che_inproc: Retriever,
) -> None:
    unreachable = RagAdminClient("http://127.0.0.1:1")
    for c in _client(session_factory, registry, fake_llm, db, unreachable):
        headers = login(c, admin.email)
        r = upload(c, headers)
        assert r.status_code == 503 and r.json()["code"] == "QUY_CHE_KHONG_KET_NOI"
        [doc] = c.get("/api/admin/documents", headers=headers).json()
        assert doc["trang_thai"] == "loi" and "quy_che" in doc["loi"]
        r = c.post("/api/admin/rag/search", json={"cau_hoi": "abc"}, headers=headers)
        assert r.status_code == 503


def test_rag_search_validation(admin_client: TestClient, ad: dict[str, str]) -> None:
    r = admin_client.post(
        "/api/admin/rag/search", json={"cau_hoi": "học lại", "ma_khoa": None}, headers=ad
    )
    assert r.status_code == 422 and r.json()["code"] == "THIEU_MA_KHOA"
    r = admin_client.post(
        "/api/admin/rag/search",
        json={"cau_hoi": "học lại", "ma_khoa": "K22", "use_vector": False, "use_keyword": False},
        headers=ad,
    )
    assert r.json()["code"] == "CAN_BAT_MOT_NHANH"
    r = admin_client.post(
        "/api/admin/rag/search", json={"cau_hoi": "học lại", "ma_khoa": "XYZ"}, headers=ad
    )
    assert r.json()["code"] == "MA_KHOA_KHONG_HOP_LE"


# ----- MCP & quyền + kịch bản demo 7 --------------------------------------------
def test_mcp_servers_listing(admin_client: TestClient, ad: dict[str, str]) -> None:
    servers = admin_client.get("/api/admin/mcp-servers", headers=ad).json()
    by_name = {s["ten"]: s for s in servers}
    assert {"dao_tao", "ctsv", "tai_chinh", "quy_che"} <= set(by_name)
    assert by_name["dao_tao"]["trang_thai"] == "ok"
    register = next(t for t in by_name["dao_tao"]["cong_cu"] if t["ten"] == "register_course")
    assert register["co_tren_server"] and register["can_xac_nhan"]
    refreshed = admin_client.post("/api/admin/mcp-servers/refresh", headers=ad)
    assert refreshed.status_code == 200 and len(refreshed.json()) == len(servers)


def test_write_tool_cannot_drop_confirmation(
    admin_client: TestClient, ad: dict[str, str], db: Session
) -> None:
    tool = db.scalar(select(CongCu).where(CongCu.ten == "register_course"))
    r = admin_client.patch(f"/api/admin/tools/{tool.id}", json={"can_xac_nhan": False}, headers=ad)
    assert r.status_code == 422 and r.json()["code"] == "KHONG_THE_BO_XAC_NHAN"
    db.expire_all()
    assert db.get(CongCu, tool.id).can_xac_nhan
    r = admin_client.patch(
        f"/api/admin/tools/{tool.id}",
        json={"muc_rui_ro": "doc", "can_xac_nhan": False},
        headers=ad,
    )
    assert r.status_code == 200  # hạ mức rủi ro thì được (quản trị viên chịu trách nhiệm)
    assert admin_client.patch("/api/admin/tools/999999", json={}, headers=ad).status_code == 404


def test_demo_7_disable_register_course(
    admin_client: TestClient,
    ad: dict[str, str],
    admin: NguoiDung,
    student: NguoiDung,
    db: Session,
    script: Callable[..., FakeLLM],
) -> None:
    """Quản trị viên tắt register_course -> LLM không nhận tool đó, system prompt báo tạm dừng
    -> trợ lý trả lời tạm dừng; nhật ký ghi lại cả lần LLM cố gọi tool đã tắt."""
    tool = db.scalar(select(CongCu).where(CongCu.ten == "register_course"))
    r = admin_client.patch(f"/api/admin/tools/{tool.id}", json={"bat": False}, headers=ad)
    assert r.status_code == 200 and r.json()["bat"] is False

    llm = script(
        FakeResponse(tool_calls=[("register_course", {"ma_lop": "IT004.02"})]),
        FakeResponse(text="Chức năng đăng ký học phần đang tạm dừng em nhé."),
    )
    sv = login(admin_client, student.email)
    conv = admin_client.post("/api/conversations", json={}, headers=sv).json()
    r = admin_client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"noi_dung": "Đăng ký giúp em lớp IT004.02"},
        headers=sv,
    )
    assert r.status_code == 200
    first_call = llm.calls[0]
    names = {t["function"]["name"] for t in first_call["tools"]}
    assert "register_course" not in names and "search_course_sections" in names
    system = first_call["messages"][0]["content"]
    assert "TẠM DỪNG" in system and "đăng ký học phần" in system
    assert "tạm dừng" in r.text

    logs = admin_client.get(
        f"/api/admin/audit-logs?nguoi_dung_id={student.id}&ten_cong_cu=register_course",
        headers=ad,
    ).json()
    assert logs["tong"] == 1
    assert logs["luot_goi"][0]["trang_thai"] == "bi_tu_choi"


# ----- Nhật ký --------------------------------------------------------------------
def _log(db: Session, user: NguoiDung, name: str, status: str, llm_args: dict | None) -> int:
    log = LuotGoiCongCu(
        nguoi_dung_id=user.id,
        mcp_server="dao_tao",
        ten_cong_cu=name,
        tham_so={"ma_sv": user.ma_sv, "hoc_ky": None},
        tham_so_llm=llm_args,
        ket_qua={"ok": True},
        trang_thai=status,
        thoi_gian_ms=12,
    )
    db.add(log)
    db.commit()
    return log.id


def test_audit_logs_filter_and_injection_flag(
    admin_client: TestClient, ad: dict[str, str], db: Session, admin: NguoiDung
) -> None:
    """Ghi log cho tài khoản admin mới tạo trong test (chưa có lịch sử) -> đếm chính xác."""
    injected = _log(db, admin, "get_transcript", "thanh_cong", {"hoc_ky": None})
    forged = _log(db, admin, "get_transcript", "thanh_cong", {"ma_sv": "SV99999", "hoc_ky": None})
    same = _log(db, admin, "get_exam_schedule", "loi", {"ma_sv": admin.ma_sv, "hoc_ky": None})

    base = f"/api/admin/audit-logs?nguoi_dung_id={admin.id}"
    page = admin_client.get(base, headers=ad).json()
    assert page["tong"] == 3
    rows = {row["id"]: row for row in page["luot_goi"]}
    assert [row["id"] for row in page["luot_goi"]] == [same, forged, injected]  # mới nhất trước
    assert rows[injected]["da_tiem_ngu_canh"] and rows[forged]["da_tiem_ngu_canh"]
    assert not rows[same]["da_tiem_ngu_canh"]
    assert rows[same]["nguoi_dung"]["email"] == admin.email
    assert "ket_qua" not in rows[same]

    assert admin_client.get(f"{base}&trang_thai=loi", headers=ad).json()["tong"] == 1
    assert admin_client.get(f"{base}&ten_cong_cu=get_transcript", headers=ad).json()["tong"] == 2
    paged = admin_client.get(f"{base}&page=2&page_size=2", headers=ad).json()
    assert [row["id"] for row in paged["luot_goi"]] == [injected]
    assert admin_client.get(f"{base}&trang_thai=bay_ba", headers=ad).status_code == 422

    detail = admin_client.get(f"/api/admin/audit-logs/{forged}", headers=ad).json()
    assert detail["ket_qua"] == {"ok": True} and detail["tham_so_llm"]["ma_sv"] == "SV99999"
    assert admin_client.get("/api/admin/audit-logs/0", headers=ad).status_code == 404


# ----- Thống kê -------------------------------------------------------------------
def test_stats(
    admin_client: TestClient, ad: dict[str, str], db: Session, student: NguoiDung
) -> None:
    """Dữ liệu đặt vào một ngày tương lai -> tách biệt với dữ liệu thật trong CSDL."""
    day = datetime(2030, 1, 15, 9, 0)
    conv = HoiThoai(nguoi_dung_id=student.id, tieu_de="Thống kê", created_at=day, updated_at=day)
    db.add(conv)
    db.flush()

    def msg(role: str, text: str, ms: int | None = None) -> TinNhan:
        m = TinNhan(
            hoi_thoai_id=conv.id, vai_tro=role, noi_dung=text, thoi_gian_ms=ms, created_at=day
        )
        db.add(m)
        db.flush()
        return m

    msg("user", "Học lại thế nào?")
    good = msg("assistant", "Em đăng ký lại học phần [1].", 1000)
    msg("user", "Còn học phí?")
    bad = msg("assistant", "Mình không rõ.", 3000)
    msg("user", "Xác nhận: Đăng ký lớp IT004.02")  # tin hệ thống, không tính là câu hỏi
    for m, diem, note in ((good, 1, None), (bad, -1, "Sai rồi")):
        db.add(
            DanhGiaCauTraLoi(
                tin_nhan_id=m.id, nguoi_dung_id=student.id, diem=diem, gop_y=note, created_at=day
            )
        )
    for status in ("thanh_cong", "loi"):
        db.add(
            LuotGoiCongCu(
                nguoi_dung_id=student.id,
                mcp_server="tai_chinh",
                ten_cong_cu="get_tuition_status",
                tham_so={},
                trang_thai=status,
                created_at=day,
            )
        )
    db.commit()

    s = admin_client.get("/api/admin/stats?tu=2030-01-15&den=2030-01-16", headers=ad).json()
    assert (s["so_hoi_thoai"], s["so_cau_hoi"]) == (1, 2)
    assert (s["so_danh_gia"], s["so_huu_ich"], s["ti_le_huu_ich"]) == (2, 1, 0.5)
    assert s["thoi_gian_phan_hoi_tb_ms"] == 2000
    assert s["top_cong_cu"] == [{"ten_cong_cu": "get_tuition_status", "so_lan": 2, "so_loi": 1}]
    assert s["theo_ngay"] == [
        {"ngay": "2030-01-15", "so_cau_hoi": 2},
        {"ngay": "2030-01-16", "so_cau_hoi": 0},
    ]
    [disliked] = s["cau_bi_che"]
    assert disliked["cau_hoi"] == "Còn học phí?" and disliked["gop_y"] == "Sai rồi"
    assert disliked["tin_nhan_id"] == bad.id

    empty = admin_client.get("/api/admin/stats?tu=2031-01-01&den=2031-01-01", headers=ad).json()
    assert empty["ti_le_huu_ich"] is None and empty["thoi_gian_phan_hoi_tb_ms"] is None
    r = admin_client.get("/api/admin/stats?tu=2030-02-01&den=2030-01-01", headers=ad)
    assert r.status_code == 422


def test_stats_safety(
    admin_client: TestClient, ad: dict[str, str], db: Session, student: NguoiDung
) -> None:
    """An toàn & độ tin cậy: trạng thái lượt gọi, hành động cần xác nhận, chặn ma_sv, kiểm chứng."""
    day = datetime(2031, 3, 10, 9, 0)
    conv = HoiThoai(nguoi_dung_id=student.id, tieu_de="An toàn", created_at=day, updated_at=day)
    db.add(conv)
    db.flush()
    logs = []
    for status, llm_args in (
        ("thanh_cong", {}),
        ("thanh_cong", {"ma_sv": "SV22002"}),  # LLM cố chọn ma_sv -> bị ghi đè
        ("bi_tu_choi", None),
        ("cho_xac_nhan", {"ma_lop": "IT004.02"}),
        ("cho_xac_nhan", {"ma_lop": "SE105.02"}),
        ("cho_xac_nhan", {"ma_lop": "SE104.01"}),
    ):
        log = LuotGoiCongCu(
            nguoi_dung_id=student.id,
            hoi_thoai_id=conv.id,
            mcp_server="dao_tao",
            ten_cong_cu="register_course",
            tham_so={
                "ma_sv": "SV22001",
                **{k: v for k, v in (llm_args or {}).items() if k != "ma_sv"},
            },
            tham_so_llm=llm_args,
            trang_thai=status,
            created_at=day,
        )
        db.add(log)
        db.flush()
        logs.append(log)
    for log, status in zip(logs[3:], ("da_xac_nhan", "da_huy", "het_han"), strict=True):
        db.add(
            HanhDongChoXacNhan(
                ma=str(uuid.uuid4()),
                hoi_thoai_id=conv.id,
                nguoi_dung_id=student.id,
                luot_goi_id=log.id,
                mcp_server="dao_tao",
                ten_cong_cu="register_course",
                tham_so=log.tham_so,
                mo_ta="Đăng ký lớp",
                trang_thai=status,
                het_han_luc=day,
                created_at=day,
            )
        )
    for verdict in ({"tong": 4, "co_can_cu": 3, "y": []}, {"tong": 2, "co_can_cu": 2, "y": []}):
        db.add(
            TinNhan(
                hoi_thoai_id=conv.id,
                vai_tro="assistant",
                noi_dung="Theo quy chế [1].",
                kiem_chung=verdict,
                created_at=day,
            )
        )
    db.commit()

    s = admin_client.get("/api/admin/stats?tu=2031-03-10&den=2031-03-10", headers=ad).json()
    safety = s["an_toan"]
    assert safety["trang_thai_goi"] == {
        "thanh_cong": 2,
        "loi": 0,
        "bi_tu_choi": 1,
        "cho_xac_nhan": 3,
        "da_huy": 0,
    }
    assert safety["hanh_dong"] == {
        "cho": 0,
        "cho_bo_sung": 0,
        "da_xac_nhan": 1,
        "da_huy": 1,
        "het_han": 1,
    }
    assert safety["so_lan_chan_ma_sv"] == 1
    assert (safety["so_cau_kiem_chung"], safety["so_menh_de"], safety["so_co_can_cu"]) == (2, 6, 5)
    assert safety["ti_le_co_can_cu"] == round(5 / 6, 4)


def test_stats_safety_empty_range(admin_client: TestClient, ad: dict[str, str]) -> None:
    s = admin_client.get("/api/admin/stats?tu=2032-01-01&den=2032-01-01", headers=ad).json()
    assert s["an_toan"]["ti_le_co_can_cu"] is None
    assert sum(s["an_toan"]["trang_thai_goi"].values()) == 0


def test_settings_paths_unchanged() -> None:
    """Thư mục tải lên mặc định nằm trong data/ của dự án (không commit)."""
    assert get_settings().upload_dir.name == "van_ban"


# ----- Thêm / sửa MCP server lúc chạy (server thư viện) --------------------------------------
LIB = "http://127.0.0.1:9105/mcp"


@pytest.fixture
def adm(client: TestClient, admin: NguoiDung) -> dict[str, str]:
    return login(client, admin.email)


def add_library(client: TestClient, headers: dict[str, str], **body: str) -> httpx.Response:
    payload = {"ten": "thu_vien", "mo_ta": "Thư viện", "dia_chi": LIB, **body}
    return client.post("/api/admin/mcp-servers", json=payload, headers=headers)


def count_servers(db: Session) -> int:
    db.expire_all()
    return len(db.scalars(select(McpServer)).all())


def test_address_normalized() -> None:
    assert admin_router.normalize_mcp_address(" http://LOCALHOST:9105/mcp ") == (
        "http://LOCALHOST:9105/mcp"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "https://example.com/mcp",
        "http://127.0.0.1.evil.com:9105/mcp",
        "http://10.0.0.5:9105/mcp",
        "http://localhost/mcp",
        "ftp://127.0.0.1:9105/mcp",
        "http://user@127.0.0.1:9105/mcp",
    ],
)
def test_address_rejected(bad: str) -> None:
    from src.assistant_api.errors import ApiError

    with pytest.raises(ApiError) as exc:
        admin_router.normalize_mcp_address(bad)
    assert exc.value.code == "DIA_CHI_MCP_KHONG_HOP_LE"


def test_check_lists_tools_without_saving(
    client: TestClient, adm: dict[str, str], db: Session
) -> None:
    before = count_servers(db)
    r = client.post("/api/admin/mcp-servers/check", json={"dia_chi": LIB}, headers=adm)
    assert r.status_code == 200, r.text
    tools = {t["ten"]: t for t in r.json()["cong_cu"]}
    assert set(tools) == {"get_borrowed_books", "search_books", "renew_book"}
    assert tools["renew_book"]["chi_doc_theo_server"] is False
    assert tools["renew_book"]["title"] == "Gia hạn sách"
    assert "ma_sv" not in tools["renew_book"]["tham_so"]["properties"]
    assert tools["renew_book"]["trung_ten_voi"] is None
    assert count_servers(db) == before


def test_add_server_then_tools_disabled_new(
    client: TestClient, adm: dict[str, str], db: Session
) -> None:
    r = add_library(client, adm)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ten"] == "thu_vien" and body["trang_thai"] == "ok"
    assert {t["ten"] for t in body["cong_cu"]} == {
        "get_borrowed_books",
        "search_books",
        "renew_book",
    }
    for t in body["cong_cu"]:
        assert t["bat"] is False and t["duyet"] == "moi" and t["can_xac_nhan"] is True
    assert body["cong_cu_bi_bo_qua"] == []
    dup = add_library(client, adm)
    assert dup.status_code == 409 and dup.json()["code"] == "TEN_MCP_DA_TON_TAI"
    bad = add_library(client, adm, ten="Thu Vien")
    assert bad.status_code == 422 and bad.json()["code"] == "TEN_MCP_KHONG_HOP_LE"


def test_add_unreachable_server_rejected(
    client: TestClient, adm: dict[str, str], db: Session
) -> None:
    before = count_servers(db)
    r = add_library(client, adm, dia_chi="http://127.0.0.1:9199/mcp")
    assert r.status_code == 422 and r.json()["code"] == "MCP_KHONG_KET_NOI_DUOC"
    assert count_servers(db) == before


def test_enable_tool_records_approval(client: TestClient, adm: dict[str, str], db: Session) -> None:
    assert add_library(client, adm).status_code == 201
    db.expire_all()
    tool = db.scalar(select(CongCu).where(CongCu.ten == "renew_book"))
    r = client.patch(f"/api/admin/tools/{tool.id}", json={"bat": True}, headers=adm)
    assert r.status_code == 200, r.text
    assert r.json()["duyet"] == "da_duyet" and r.json()["title"] == "Gia hạn sách"
    db.expire_all()
    assert db.get(CongCu, tool.id).ban_duyet
    r = client.patch(f"/api/admin/tools/{tool.id}", json={"can_xac_nhan": False}, headers=adm)
    assert r.status_code == 422 and r.json()["code"] == "KHONG_THE_BO_XAC_NHAN"


def test_patch_server_bad_address_keeps_db(
    client: TestClient, adm: dict[str, str], db: Session
) -> None:
    server_id = add_library(client, adm).json()["id"]
    r = client.patch(
        f"/api/admin/mcp-servers/{server_id}", json={"dia_chi": "https://x.com/mcp"}, headers=adm
    )
    assert r.status_code == 422 and r.json()["code"] == "DIA_CHI_MCP_KHONG_HOP_LE"
    r = client.patch(
        f"/api/admin/mcp-servers/{server_id}",
        json={"dia_chi": "http://127.0.0.1:9199/mcp"},
        headers=adm,
    )
    assert r.status_code == 422 and r.json()["code"] == "MCP_KHONG_KET_NOI_DUOC"
    db.expire_all()
    assert db.get(McpServer, server_id).dia_chi == LIB
    r = client.patch(
        f"/api/admin/mcp-servers/{server_id}", json={"mo_ta": "Thư viện trường"}, headers=adm
    )
    assert r.status_code == 200 and r.json()["mo_ta"] == "Thư viện trường"
    r = client.patch("/api/admin/mcp-servers/999999", json={"bat": False}, headers=adm)
    assert r.status_code == 404 and r.json()["code"] == "MCP_KHONG_TON_TAI"


def test_student_cannot_manage_servers(client: TestClient, student: NguoiDung) -> None:
    headers = login(client, student.email)
    assert add_library(client, headers).status_code == 403
    r = client.post("/api/admin/mcp-servers/check", json={"dia_chi": LIB}, headers=headers)
    assert r.status_code == 403

"""Kho hỏi đáp cán bộ (/api/admin/knowledge) — nâng cấp 10.

quy_che chạy TRONG tiến trình, lập chỉ mục đồng bộ (fixture của test_admin): thêm/sửa/gỡ mục là
tìm thấy / hết thấy NGAY qua /api/admin/rag/search.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.assistant_api.knowledge import personal_info_problem
from src.assistant_api.models import HoiThoai, NguoiDung, TinNhan, VanBan
from tests.assistant import test_admin as _admin
from tests.assistant.conftest import login

# Fixture dùng chung với test_admin: quy_che chạy trong tiến trình, lập chỉ mục đồng bộ
quy_che_inproc = _admin.quy_che_inproc
admin_client = _admin.admin_client
ad = _admin.ad
search = _admin.search
upload = _admin.upload


@pytest.fixture(autouse=True)
def empty_knowledge_base(db: Session) -> None:
    """Cô lập khỏi kho thật trên CSDL dev (bị rollback cuối test, như văn bản ở quy_che_inproc)."""
    from sqlalchemy import delete

    from src.assistant_api.models import KhoHoiDap

    db.execute(delete(KhoHoiDap))
    db.commit()


QUESTION = "Ký túc xá khu B đóng cửa lúc mấy giờ vào cuối tuần?"
ANSWER = "Ký túc xá khu B đóng cửa lúc 23 giờ, kể cả thứ Bảy và Chủ nhật."


def add(client: TestClient, headers: dict[str, str], **body: object):  # type: ignore[no-untyped-def]
    payload = {"cau_hoi": QUESTION, "tra_loi": ANSWER, "phong_ban": "ctsv", **body}
    return client.post("/api/admin/knowledge", json=payload, headers=headers)


def kb_search(client: TestClient, headers: dict[str, str]) -> list[dict]:
    return search(client, headers, cau_hoi="ký túc xá khu B đóng cửa mấy giờ cuối tuần")["doan"]


def test_add_entry_is_searchable_then_edit_and_remove(
    admin_client: TestClient, ad: dict[str, str]
) -> None:
    r = add(admin_client, ad, ma_don="DT-2026-0042")
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["ma_don"] == "DT-2026-0042" and entry["created_at"].endswith("+07:00")

    listed = admin_client.get("/api/admin/knowledge", headers=ad).json()
    assert [m["id"] for m in listed["muc"]] == [entry["id"]]
    assert listed["van_ban"]["trang_thai"] == "da_lap_chi_muc"
    assert listed["van_ban"]["so_doan"] == 1

    found = kb_search(admin_client, ad)
    assert found and found[0]["loai"] == "hoi_dap" and "23 giờ" in found[0]["noi_dung"]

    edited = admin_client.put(
        f"/api/admin/knowledge/{entry['id']}",
        json={"cau_hoi": QUESTION, "tra_loi": "Đóng cửa lúc 22 giờ 30 từ tháng 12.",
              "phong_ban": "ctsv"},
        headers=ad,
    )  # fmt: skip
    assert edited.status_code == 200, edited.text
    assert "22 giờ 30" in kb_search(admin_client, ad)[0]["noi_dung"]

    gone = admin_client.delete(f"/api/admin/knowledge/{entry['id']}", headers=ad)
    assert gone.status_code == 204
    assert kb_search(admin_client, ad) == []
    after = admin_client.get("/api/admin/knowledge", headers=ad).json()
    assert after == {"van_ban": None, "muc": []}  # kho rỗng -> văn bản kho bị xóa


def test_personal_info_is_rejected(admin_client: TestClient, ad: dict[str, str]) -> None:
    r = add(admin_client, ad, cau_hoi="Em SV22001 muốn hỏi ký túc xá đóng cửa mấy giờ?")
    assert r.status_code == 422 and r.json()["code"] == "CO_THONG_TIN_CA_NHAN"
    r = add(admin_client, ad, tra_loi="Em liên hệ thầy qua 0912345678 nhé, ký túc xá đóng 23h.")
    assert r.status_code == 422 and r.json()["code"] == "CO_THONG_TIN_CA_NHAN"
    assert admin_client.get("/api/admin/knowledge", headers=ad).json()["muc"] == []


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Mã SV22001 hỏi về học bổng", True),
        ("liên hệ an.nguyen@truong.example để biết thêm", True),
        ("gọi 0912 345 678", True),
        ("+84 912345678", True),
        ("Lệ phí là 50.000 đồng, nộp trước 15/12/2026", False),
        ("Điều 12 khoản 3 quy chế 2023", False),
    ],
)
def test_personal_info_problem(text: str, flagged: bool) -> None:
    assert (personal_info_problem(text) is not None) is flagged


def test_entry_links_to_assistant_message(
    admin_client: TestClient, ad: dict[str, str], db: Session, student: NguoiDung
) -> None:
    conv = HoiThoai(nguoi_dung_id=student.id, tieu_de="KTX")
    db.add(conv)
    db.flush()
    msg = TinNhan(hoi_thoai_id=conv.id, vai_tro="assistant", noi_dung="Chưa có thông tin.")
    db.add(msg)
    db.commit()
    assert add(admin_client, ad, tin_nhan_id=msg.id).json()["tin_nhan_id"] == msg.id
    r = add(admin_client, ad, tin_nhan_id=999_999_999)
    assert r.status_code == 404 and r.json()["code"] == "TIN_NHAN_KHONG_TON_TAI"


def test_knowledge_doc_cannot_be_deleted_from_documents_page(
    admin_client: TestClient, ad: dict[str, str], db: Session
) -> None:
    add(admin_client, ad)
    doc = db.scalar(select(VanBan).where(VanBan.loai == "hoi_dap"))
    assert doc is not None
    r = admin_client.delete(f"/api/admin/documents/{doc.id}", headers=ad)
    assert r.status_code == 409 and r.json()["code"] == "VAN_BAN_KHO_HOI_DAP"
    # lập chỉ mục lại được dù không có tệp gốc
    r = admin_client.post(f"/api/admin/documents/{doc.id}/reindex", headers=ad)
    assert r.status_code == 202, r.text
    assert r.json()["trang_thai"] == "da_lap_chi_muc"
    # không có tệp để mở
    assert admin_client.get(f"/api/documents/{doc.id}/file", headers=ad).status_code == 404


def test_upload_cannot_use_knowledge_kind(
    admin_client: TestClient, ad: dict[str, str], tmp_path: Path
) -> None:
    assert upload(admin_client, ad, loai="hoi_dap").status_code == 422


def test_student_cannot_manage_knowledge(admin_client: TestClient, student: NguoiDung) -> None:
    headers = login(admin_client, student.email)
    assert admin_client.get("/api/admin/knowledge", headers=headers).status_code == 403
    assert add(admin_client, headers).status_code == 403


# ----- Lỗ hổng tri thức -----------------------------------------------------------
class FakeDirectory:
    def __init__(self, requests: list[dict] | None = None, fail: bool = False) -> None:
        self.requests = requests or []
        self.fail = fail
        self.params: dict | None = None

    async def list_requests(self, params: dict) -> dict:
        from src.assistant_api.errors import ApiError

        self.params = params
        if self.fail:
            raise ApiError("QLSV_KHONG_KET_NOI", "Không kết nối được qlsv.", 503)
        return {"tong": len(self.requests), "trang_so": 1, "so_moi_trang": 100,
                "don": self.requests}  # fmt: skip


def use_directory(client: TestClient, directory: FakeDirectory) -> None:
    from src.assistant_api.routers.admin_users import qlsv_directory

    client.app.dependency_overrides[qlsv_directory] = lambda: directory  # type: ignore[attr-defined]


QUESTION_REQUEST = {
    "ma_don": "HD-2026-0007",
    "loai_don": "hoi_dap",
    "noi_dung": {"cau_hoi": "Thư viện có mở cửa Chủ nhật không ạ?", "phong_ban": "ctsv"},
    "trang_thai": "hoan_tat",
    "ghi_chu_xu_ly": "Thư viện mở Chủ nhật từ 8 đến 17 giờ.",
    "tao_boi": "tro_ly",
    "created_at": "2026-11-19T10:00:00+07:00",
    "updated_at": "2026-11-19T15:00:00+07:00",
    "ma_sv": "SV22001",
    "ho_ten": "Nguyễn Văn An",
}


def _chat_turn(db: Session, conv_id: int, question: str, answer: str, **extra: object) -> TinNhan:
    db.add(TinNhan(hoi_thoai_id=conv_id, vai_tro="user", noi_dung=question))
    db.flush()
    msg = TinNhan(hoi_thoai_id=conv_id, vai_tro="assistant", noi_dung=answer, **extra)
    db.add(msg)
    db.flush()
    return msg


def test_gaps_merge_three_sources(
    admin_client: TestClient, ad: dict[str, str], db: Session, student: NguoiDung
) -> None:
    from src.assistant_api.models import DanhGiaCauTraLoi

    conv = HoiThoai(nguoi_dung_id=student.id, tieu_de="KTX")
    db.add(conv)
    db.flush()
    verdict = {
        "tong": 2,
        "co_can_cu": 1,
        "y": [
            {"cau": "KTX đóng cửa lúc 22 giờ.", "ket_luan": "khong_co_can_cu", "doan": [],
             "ly_do": "Không đoạn nào nêu giờ đóng cửa."},
            {"cau": "Sinh viên phải đăng ký ở KTX [1].", "ket_luan": "co_can_cu", "doan": [1],
             "ly_do": "Đoạn 1 nêu."},
        ],
    }  # fmt: skip
    unsupported = _chat_turn(
        db, conv.id, "KTX khu B đóng cửa lúc mấy giờ ạ?", "KTX đóng cửa lúc 22 giờ.",
        kiem_chung=verdict,
    )  # fmt: skip
    disliked = _chat_turn(db, conv.id, "Học phí kỳ hè tính thế nào?", "Học phí kỳ hè miễn phí.")
    not_found = _chat_turn(
        db, conv.id, "Phòng gym của trường mở mấy giờ?", "Văn bản hiện có không đề cập.",
        kiem_chung={"tong": 0, "co_can_cu": 0, "y": [], "mo_hinh": "x", "thoi_gian_ms": 1},
    )  # fmt: skip
    db.add(DanhGiaCauTraLoi(tin_nhan_id=disliked.id, nguoi_dung_id=student.id, diem=-1,
                            gop_y="Sai, kỳ hè vẫn đóng học phí"))  # fmt: skip
    db.commit()
    directory = FakeDirectory([QUESTION_REQUEST])
    use_directory(admin_client, directory)
    # mục đã đưa vào kho được đánh dấu
    assert add(admin_client, ad, tin_nhan_id=unsupported.id).status_code == 201

    r = admin_client.get("/api/admin/knowledge/gaps?ngay=30", headers=ad)
    assert r.status_code == 200, r.text
    body = r.json()
    assert directory.params == {"loai_don": "hoi_dap", "page": 1, "page_size": 100}
    assert body["nguon_loi"] == []
    mine = [
        m for m in body["muc"]
        if m["tin_nhan_id"] in (unsupported.id, disliked.id, not_found.id)
        or m["ma_don"] == "HD-2026-0007"
    ]  # fmt: skip
    by_source = {m["nguon"]: m for m in mine}
    assert len(mine) == 4  # ý "có căn cứ" không phải lỗ hổng

    missing = by_source["khong_tim_thay"]
    assert missing["cau_hoi"] == "Phòng gym của trường mở mấy giờ?"
    assert missing["noi_dung"] == "Văn bản hiện có không đề cập."

    claim = by_source["khong_can_cu"]
    assert claim["cau_hoi"] == "KTX khu B đóng cửa lúc mấy giờ ạ?"
    assert claim["noi_dung"] == "KTX đóng cửa lúc 22 giờ."
    assert claim["ly_do"] == "Không đoạn nào nêu giờ đóng cửa." and claim["da_vao_kho"] is True

    rating = by_source["danh_gia_xau"]
    assert rating["cau_hoi"] == "Học phí kỳ hè tính thế nào?"
    assert rating["ly_do"] == "Sai, kỳ hè vẫn đóng học phí" and rating["da_vao_kho"] is False

    question = by_source["hoi_can_bo"]
    assert question["cau_hoi"] == "Thư viện có mở cửa Chủ nhật không ạ?"
    assert question["tra_loi_can_bo"] == "Thư viện mở Chủ nhật từ 8 đến 17 giờ."
    assert question["phong_ban"] == "ctsv" and question["trang_thai"] == "hoan_tat"
    # tối thiểu hóa dữ liệu: không trả mã SV / họ tên / id người dùng
    assert all(k not in m for m in mine for k in ("ma_sv", "ho_ten", "nguoi_dung_id"))
    assert body["dem"]["khong_can_cu"] >= 1 and body["dem"]["hoi_can_bo"] == 1

    only = admin_client.get("/api/admin/knowledge/gaps?nguon=hoi_can_bo", headers=ad).json()
    assert {m["nguon"] for m in only["muc"]} == {"hoi_can_bo"}


def test_gaps_survive_qlsv_down_and_old_requests_are_filtered(
    admin_client: TestClient, ad: dict[str, str]
) -> None:
    use_directory(admin_client, FakeDirectory(fail=True))
    body = admin_client.get("/api/admin/knowledge/gaps", headers=ad).json()
    assert body["nguon_loi"] == ["hoi_can_bo"]
    assert all(m["nguon"] != "hoi_can_bo" for m in body["muc"])

    old = {**QUESTION_REQUEST, "created_at": "2020-01-01T08:00:00+07:00"}
    use_directory(admin_client, FakeDirectory([old]))
    body = admin_client.get("/api/admin/knowledge/gaps?ngay=7", headers=ad).json()
    assert body["dem"]["hoi_can_bo"] == 0


def test_gaps_validation(admin_client: TestClient, ad: dict[str, str]) -> None:
    use_directory(admin_client, FakeDirectory())
    assert admin_client.get("/api/admin/knowledge/gaps?ngay=0", headers=ad).status_code == 422
    assert admin_client.get("/api/admin/knowledge/gaps?nguon=x", headers=ad).status_code == 422

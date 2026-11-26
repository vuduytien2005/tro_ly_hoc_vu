"""Quản lý hồ sơ sinh viên trên qlsv_api (AD-10): danh sách, thêm, sửa, đổi trạng thái.
Chạy trên CSDL thật, rollback cuối mỗi test (tests/qlsv/conftest.py)."""

from typing import Any

from fastapi.testclient import TestClient

from src.shared.security import INTERNAL_TOKEN_HEADER

NEW: dict[str, Any] = {
    "ma_sv": " sv22099 ",
    "ho_ten": "Đỗ Minh Khoa",
    "email": "SV22099@Truong.Example",
    "ngay_sinh": "2004-03-15",
    "gioi_tinh": "nam",
    "ma_nganh": "CNPM",
    "ma_khoa": "k22",
    "lop": "KTPM2022",
}


def test_requires_internal_token(client: TestClient) -> None:
    r = client.get("/internal/students", headers={INTERNAL_TOKEN_HEADER: "sai"})
    assert r.status_code == 401
    r = client.post("/internal/students", json=NEW, headers={INTERNAL_TOKEN_HEADER: "sai"})
    assert r.status_code == 401


def test_list_and_search(client: TestClient) -> None:
    body = client.get("/internal/students").json()
    assert body["tong"] >= 5  # 5 SV của 03_qlsv_seed.sql (+ 9 SV nếu đã chạy 11)
    codes = [s["ma_sv"] for s in body["sinh_vien"]]
    assert codes == sorted(codes) and codes[0] == "SV21001"

    found = client.get("/internal/students", params={"q": "Bình"}).json()
    assert [s["ma_sv"] for s in found["sinh_vien"]] == ["SV22002"]

    page = client.get("/internal/students", params={"page": 2, "page_size": 2}).json()
    assert page["tong"] == body["tong"] and len(page["sinh_vien"]) == 2


def test_programs(client: TestClient) -> None:
    programs = client.get("/internal/programs").json()
    assert {(p["ma_nganh"], p["ma_khoa"]) for p in programs} >= {
        ("CNPM", "K21"),
        ("CNPM", "K22"),
        ("CNPM", "K23"),
    }


def test_create_student_normalizes_and_is_readable(client: TestClient) -> None:
    before = client.get("/internal/students").json()["tong"]
    r = client.post("/internal/students", json=NEW)
    assert r.status_code == 201, r.text
    sv = r.json()
    assert sv["ma_sv"] == "SV22099"
    assert sv["email"] == "sv22099@truong.example"
    assert sv["khoa"] == "K22"
    assert sv["nganh"] == "Công nghệ phần mềm"
    assert sv["trang_thai"] == "dang_hoc"

    # Các API khác (MCP dùng) đọc được ngay; chưa có điểm
    assert client.get("/internal/students/SV22099").json()["ho_ten"] == "Đỗ Minh Khoa"
    transcript = client.get("/internal/students/SV22099/transcript")
    assert transcript.status_code == 200
    assert client.get("/internal/students").json()["tong"] == before + 1


def test_create_rejects_duplicates_and_bad_data(client: TestClient) -> None:
    cases = [
        ({"ma_sv": "SV22001"}, 409, "SV_DA_TON_TAI"),
        ({"email": "sv22001@truong.example"}, 409, "EMAIL_DA_TON_TAI"),
        ({"ma_nganh": "KHMT"}, 422, "NGANH_KHONG_TON_TAI"),
        ({"ma_khoa": "K30"}, 422, "KHOA_HOC_KHONG_TON_TAI"),
        ({"ngay_sinh": "2025-01-01"}, 422, "NGAY_SINH_KHONG_HOP_LE"),
        ({"ma_sv": "SV/../1"}, 422, None),
        ({"email": "khong-phai-email"}, 422, None),
        ({"gioi_tinh": "x"}, 422, None),
    ]
    for override, status, code in cases:
        r = client.post("/internal/students", json={**NEW, **override})
        assert r.status_code == status, (override, r.text)
        if code:
            assert r.json()["code"] == code, override


def test_update_profile_and_status(client: TestClient) -> None:
    r = client.patch(
        "/internal/students/sv22003",  # không cần viết hoa: ma_sv so khớp theo collation CI
        json={"ho_ten": "Hoàng Gia Huy (sửa)", "lop": "KTPM2023", "ma_khoa": "K23"},
    )
    assert r.status_code == 200, r.text
    sv = r.json()
    assert sv["ho_ten"] == "Hoàng Gia Huy (sửa)"
    assert sv["lop"] == "KTPM2023"
    assert sv["khoa"] == "K23"
    assert sv["email"] == "sv22003@truong.example"  # trường không gửi thì giữ nguyên

    r = client.patch("/internal/students/SV22003", json={"trang_thai": "bao_luu"})
    assert r.json()["trang_thai"] == "bao_luu"


def test_suspended_student_cannot_submit_requests(client: TestClient) -> None:
    """Đổi trạng thái có tác dụng nghiệp vụ thật: SV bảo lưu không nộp đơn được."""
    client.patch("/internal/students/SV22001", json={"trang_thai": "bao_luu"})
    r = client.post(
        "/internal/students/SV22001/requests",
        json={
            "loai_don": "bao_luu",
            "noi_dung": {"ly_do": "Gia đình có việc", "tu_hoc_ky": "2026-2027-HK2", "so_hoc_ky": 1},
            "tao_boi": "sinh_vien",
        },
    )
    assert r.status_code >= 400


def test_update_errors(client: TestClient) -> None:
    r = client.patch("/internal/students/SV99999", json={"lop": "X"})
    assert r.status_code == 404
    assert r.json()["code"] == "SV_KHONG_TON_TAI"

    r = client.patch("/internal/students/SV22003", json={"email": "sv22001@truong.example"})
    assert r.status_code == 409
    assert r.json()["code"] == "EMAIL_DA_TON_TAI"

    # Giữ nguyên email của chính mình thì không phải trùng
    r = client.patch("/internal/students/SV22003", json={"email": "SV22003@truong.example"})
    assert r.status_code == 200

    r = client.patch("/internal/students/SV22003", json={"ma_khoa": "K99"})
    assert r.json()["code"] == "KHOA_HOC_KHONG_TON_TAI"

    r = client.patch("/internal/students/SV22003", json={"ma_sv": "SV11111"})
    assert r.status_code == 200
    assert r.json()["ma_sv"] == "SV22003"  # ma_sv không có trong schema sửa -> bị bỏ qua

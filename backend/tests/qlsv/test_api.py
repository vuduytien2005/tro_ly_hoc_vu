"""Kiểm tra tầng HTTP: token nội bộ, định dạng lỗi, gọi thử endpoint."""

from fastapi.testclient import TestClient

from src.qlsv_api.main import app
from src.shared.security import INTERNAL_TOKEN_HEADER


def test_missing_token_is_401() -> None:
    with TestClient(app) as c:
        r = c.get("/internal/students/SV22001")
    assert r.status_code == 401
    assert r.json() == {
        "detail": "Thiếu token xác thực nội bộ (X-Internal-Token).",
        "code": "THIEU_TOKEN_NOI_BO",
    }


def test_wrong_token_is_401() -> None:
    with TestClient(app, headers={INTERNAL_TOKEN_HEADER: "sai-token"}) as c:
        r = c.get("/internal/students/SV22001")
    assert r.status_code == 401 and r.json()["code"] == "TOKEN_NOI_BO_KHONG_HOP_LE"


def test_docs_open_without_token() -> None:
    with TestClient(app) as c:
        assert c.get("/docs").status_code == 200
        assert c.get("/openapi.json").status_code == 200


def test_profile_and_transcript(client: TestClient) -> None:
    p = client.get("/internal/students/SV22001").json()
    assert (p["ho_ten"], p["khoa"], p["nganh"]) == ("Nguyễn Văn An", "K22", "Công nghệ phần mềm")

    t = client.get("/internal/students/SV22001/transcript").json()
    assert (t["tin_chi_tich_luy"], t["gpa_tich_luy"]) == (25, 3.06)


def test_unknown_student_404_format(client: TestClient) -> None:
    r = client.get("/internal/students/SV99999")
    assert r.status_code == 404
    assert r.json()["code"] == "SV_KHONG_TON_TAI" and "SV99999" in r.json()["detail"]


def test_semesters_current(client: TestClient) -> None:
    s = client.get("/internal/semesters/current").json()
    assert s["hien_tai"]["ma_hoc_ky"] == "2026-2027-HK1"
    assert s["dang_mo_dang_ky"]["ma_hoc_ky"] == "2026-2027-HK2"
    assert s["dang_mo_dang_ky"]["dang_ky_tu"].endswith("+07:00")


def test_course_sections_with_free_seats(client: TestClient) -> None:
    rows = client.get("/internal/course-sections", params={"q": "IT004"}).json()
    assert [r["ma_lop"] for r in rows] == ["IT004.02", "IT004.03"]
    full = client.get("/internal/course-sections", params={"q": "SE202"}).json()[0]
    assert (full["si_so_toi_da"], full["da_dang_ky"], full["con_trong"]) == (2, 2, 0)


def test_register_201_then_409(client: TestClient) -> None:
    ok = client.post("/internal/students/SV22001/registrations", json={"ma_lop": "IT004.02"})
    assert ok.status_code == 201 and ok.json()["thanh_cong"] is True

    dup = client.post("/internal/students/SV22001/registrations", json={"ma_lop": "SE105.02"})
    assert dup.status_code == 409 and dup.json()["code"] == "TRUNG_LICH"

    sched = client.get(
        "/internal/students/SV22001/schedule", params={"ma_hoc_ky": "2026-2027-HK2"}
    ).json()
    assert [r["ma_lop"] for r in sched["lop"]] == ["IT004.02"]

    cancel = client.delete("/internal/students/SV22001/registrations/IT004.02")
    assert cancel.status_code == 200 and cancel.json()["trang_thai"] == "da_huy"


def test_validation_error_format(client: TestClient) -> None:
    r = client.post("/internal/students/SV22001/registrations", json={})
    assert r.status_code == 422 and r.json()["code"] == "DU_LIEU_KHONG_HOP_LE"


def test_tuition_and_exam(client: TestClient) -> None:
    fee = client.get("/internal/students/SV22002/tuition").json()
    assert (fee["phai_nop"], fee["da_nop"], fee["con_no"]) == (9800000, 5000000, 4800000)
    exams = client.get("/internal/students/SV22001/exam-schedule").json()
    assert exams["lich_thi"][0]["ma_lop"] == "SE105.01"


def test_request_endpoints(client: TestClient) -> None:
    r = client.post(
        "/internal/students/SV21001/requests",
        json={"loai_don": "giay_xac_nhan_sv", "noi_dung": {"muc_dich": "Vay vốn"}},
    )
    assert r.status_code == 201
    ma_don = r.json()["ma_don"]
    assert client.get(f"/internal/students/SV21001/requests/{ma_don}").status_code == 200
    assert client.get(f"/internal/students/SV22001/requests/{ma_don}").status_code == 404
    patched = client.patch(f"/internal/requests/{ma_don}", json={"trang_thai": "da_duyet"})
    assert patched.json()["trang_thai"] == "da_duyet"

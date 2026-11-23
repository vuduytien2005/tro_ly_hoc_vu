"""Đơn từ: sinh mã đơn, bảo lưu (NO_HOC_PHI), phúc khảo (học kỳ đã kết thúc gần nhất)."""

import pytest
from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.services import request_service
from tests.qlsv.conftest import DEMO_NOW


def create(db: Session, ma_sv: str, loai: str, noi_dung: dict):  # type: ignore[no-untyped-def,type-arg]
    out = request_service.create_request(db, ma_sv, loai, noi_dung, "tro_ly_ai", DEMO_NOW)
    db.commit()
    return out


def test_certificate_request_gets_next_code(db: Session) -> None:
    out = create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "Hồ sơ vay vốn", "so_ban": 2})
    assert out.ma_don == "DT-2026-0002"  # dữ liệu mẫu đã có DT-2026-0001
    assert out.trang_thai == "moi_tao" and out.tao_boi == "tro_ly_ai"
    assert out.noi_dung == {"muc_dich": "Hồ sơ vay vốn", "so_ban": 2}
    assert out.created_at == DEMO_NOW

    out2 = create(db, "SV22001", "giay_xac_nhan_sv", {"muc_dich": "Làm thẻ xe"})
    assert out2.ma_don == "DT-2026-0003"


def test_invalid_content_is_422(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "x", "so_ban": 9})
    assert (e.value.code, e.value.status) == ("DU_LIEU_KHONG_HOP_LE", 422)


def test_deferral_blocked_when_tuition_unpaid(db: Session) -> None:
    # SV22002 mới nộp 5.000.000/9.800.000 học kỳ hiện tại
    with pytest.raises(BusinessError) as e:
        create(db, "SV22002", "bao_luu", {"ly_do": "Đi làm", "tu_hoc_ky": "2026-2027-HK2"})
    assert e.value.code == "NO_HOC_PHI"
    assert "4.800.000 đồng" in e.value.message


def test_deferral_ok_when_paid(db: Session) -> None:
    out = create(db, "SV22001", "bao_luu", {"ly_do": "Đi làm", "tu_hoc_ky": "2026-2027-HK2"})
    assert out.loai_don == "bao_luu" and out.noi_dung["so_hoc_ky"] == 1


def test_regrade_latest_finished_semester(db: Session) -> None:
    # HK2 2025-2026 là học kỳ đã kết thúc gần nhất; SV22001 có điểm SE103 ở học kỳ đó
    out = create(db, "SV22001", "phuc_khao", {"ma_hp": "se103", "ly_do": "Điểm thi thấp"})
    assert out.noi_dung["ma_hp"] == "SE103"
    assert out.noi_dung["ma_hoc_ky"] == "2025-2026-HK2"


def test_regrade_old_semester_rejected(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        create(db, "SV22001", "phuc_khao", {"ma_hp": "IT001", "ly_do": "x"})
    assert e.value.code == "KHONG_CO_DIEM_HOC_KY_GAN_NHAT"


def test_cannot_read_other_students_request(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        request_service.get_request(db, "SV22001", "DT-2026-0001")  # đơn của SV21001
    assert (e.value.code, e.value.status) == ("DON_KHONG_TON_TAI", 404)


def test_update_status(db: Session) -> None:
    out = create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "Vay vốn"})
    updated = request_service.update_status(db, out.ma_don, "dang_xu_ly", "Đang in", DEMO_NOW)
    db.commit()
    assert updated.trang_thai == "dang_xu_ly" and updated.ghi_chu_xu_ly == "Đang in"
    assert updated.updated_at == DEMO_NOW  # trigger không ghi đè giờ DEMO_NOW

    with pytest.raises(BusinessError) as e:
        request_service.update_status(db, "DT-2026-0001", "dang_xu_ly", None, DEMO_NOW)
    assert e.value.code == "DON_DA_KET_THUC"


def test_list_requests_filter(db: Session) -> None:
    assert [r.ma_don for r in request_service.list_requests(db, "SV21001", "hoan_tat")] == [
        "DT-2026-0001"
    ]
    assert request_service.list_requests(db, "SV21001", "moi_tao") == []


# ----- Duyệt đơn hai phía (bổ sung 23/11/2026) --------------------------------------------------
def test_status_machine_allows_normal_flow(db: Session) -> None:
    out = create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "Vay vốn"})
    for step in ("dang_xu_ly", "da_duyet", "hoan_tat"):
        updated = request_service.update_status(db, out.ma_don, step, None, DEMO_NOW)
        assert updated.trang_thai == step


@pytest.mark.parametrize(
    ("path", "bad"),
    [((), "hoan_tat"), ((), "moi_tao"), (("dang_xu_ly",), "moi_tao"), (("da_duyet",), "tu_choi")],
)
def test_status_machine_rejects_invalid_transition(
    db: Session, path: tuple[str, ...], bad: str
) -> None:
    out = create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "Vay vốn"})
    for step in path:
        request_service.update_status(db, out.ma_don, step, None, DEMO_NOW)
    with pytest.raises(BusinessError) as e:
        request_service.update_status(db, out.ma_don, bad, "x", DEMO_NOW)
    assert (e.value.code, e.value.status) == ("CHUYEN_TRANG_THAI_KHONG_HOP_LE", 409)


@pytest.mark.parametrize("note", [None, "   "])
def test_reject_requires_reason(db: Session, note: str | None) -> None:
    out = create(db, "SV21001", "giay_xac_nhan_sv", {"muc_dich": "Vay vốn"})
    with pytest.raises(BusinessError) as e:
        request_service.update_status(db, out.ma_don, "tu_choi", note, DEMO_NOW)
    assert (e.value.code, e.value.status) == ("CAN_LY_DO_TU_CHOI", 422)
    done = request_service.update_status(db, out.ma_don, "tu_choi", "Thiếu minh chứng", DEMO_NOW)
    assert done.trang_thai == "tu_choi" and done.ghi_chu_xu_ly == "Thiếu minh chứng"


def test_staff_list_all_requests(db: Session) -> None:
    a = create(db, "SV22001", "giay_xac_nhan_sv", {"muc_dich": "Làm thẻ xe"})
    page = request_service.list_all_requests(db, None, None, 1, 20)
    assert page.tong == 2
    times = [d.created_at for d in page.don]
    assert times == sorted(times, reverse=True)  # mới nhất trước
    mine = next(d for d in page.don if d.ma_don == a.ma_don)
    assert mine.ma_sv == "SV22001" and mine.ho_ten
    assert mine.noi_dung == {"muc_dich": "Làm thẻ xe", "so_ban": 1}
    only_new = request_service.list_all_requests(db, "moi_tao", None, 1, 20)
    assert [d.ma_don for d in only_new.don] == [a.ma_don]
    assert request_service.list_all_requests(db, None, "bao_luu", 1, 20).tong == 0
    second = request_service.list_all_requests(db, None, None, 2, 1)
    assert second.tong == 2 and second.don[0].ma_don == page.don[1].ma_don

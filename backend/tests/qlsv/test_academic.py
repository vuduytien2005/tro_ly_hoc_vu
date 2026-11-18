"""GPA, tín chỉ tích lũy, tiến độ tốt nghiệp, cảnh báo học vụ — đối chiếu dữ liệu mẫu."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.services import academic_service


def test_sv22001_gpa_and_credits(db: Session) -> None:
    t = academic_service.get_transcript(db, "SV22001", None)
    assert t.tin_chi_tich_luy == 25
    assert t.gpa_tich_luy == pytest.approx(3.06)
    assert t.canh_bao_hoc_vu is False
    assert len(t.ket_qua) == 9  # gồm cả lần F môn Cơ sở dữ liệu


def test_sv21001_gpa_and_credits(db: Session) -> None:
    t = academic_service.get_transcript(db, "SV21001", None)
    assert t.tin_chi_tich_luy == 35
    assert t.gpa_tich_luy == pytest.approx(3.36)


def test_retake_uses_best_attempt(db: Session) -> None:
    """SV22003 rớt IT001 (F) rồi học lại đạt D+ -> tính lần D+ (1.50), không bị cảnh báo."""
    t = academic_service.get_transcript(db, "SV22003", None)
    assert t.tin_chi_tich_luy == 3
    assert t.gpa_tich_luy == pytest.approx(1.5)
    assert t.canh_bao_hoc_vu is False


def test_transcript_filter_by_semester_keeps_cumulative_gpa(db: Session) -> None:
    t = academic_service.get_transcript(db, "SV22001", "2025-2026-HK2")
    assert {r.ma_hp for r in t.ket_qua} == {"SE103", "SE104"}
    assert t.gpa_tich_luy == pytest.approx(3.06)  # vẫn là GPA TÍCH LŨY


def test_graduation_progress_sv22001(db: Session) -> None:
    g = academic_service.get_graduation_progress(db, "SV22001")
    assert {m.ma_hp for m in g.hoc_phan_con_thieu} == {"IT004", "SE105", "SE201", "SE202"}
    assert (g.tong_tin_chi_yeu_cau, g.tin_chi_tich_luy) == (38, 25)
    assert g.chung_chi.gdtc and g.chung_chi.gdqp and not g.chung_chi.ngoai_ngu
    assert g.du_dieu_kien is False
    assert any("ngoại ngữ" in r for r in g.ly_do_chua_du)


def test_graduation_progress_sv21001_only_missing_se202(db: Session) -> None:
    g = academic_service.get_graduation_progress(db, "SV21001")
    assert [m.ma_hp for m in g.hoc_phan_con_thieu] == ["SE202"]
    assert g.chung_chi.ngoai_ngu and g.chung_chi.gdtc and g.chung_chi.gdqp
    assert g.du_dieu_kien is False


def test_unknown_student_is_404(db: Session) -> None:
    with pytest.raises(BusinessError) as e:
        academic_service.get_profile(db, "SV99999")
    assert (e.value.code, e.value.status) == ("SV_KHONG_TON_TAI", 404)


def _result(hp_id: int, diem_chu: str, he4: str, tin_chi: int = 3) -> SimpleNamespace:
    return SimpleNamespace(
        hoc_phan_id=hp_id,
        diem_chu=diem_chu,
        diem_he_4=Decimal(he4),
        hoc_phan=SimpleNamespace(so_tin_chi=tin_chi),
    )


def test_warning_when_two_failed_courses_not_retaken() -> None:
    s = academic_service.summarize(
        [_result(1, "A", "4.0"), _result(2, "F", "0"), _result(3, "F", "0")]
    )  # type: ignore[list-item]
    assert s.gpa == Decimal("4.00")
    assert s.canh_bao_hoc_vu is True


def test_warning_when_gpa_below_threshold() -> None:
    s = academic_service.summarize([_result(1, "D", "1.0")])  # type: ignore[list-item]
    assert s.gpa == Decimal("1.00")
    assert s.canh_bao_hoc_vu is True


def test_no_warning_without_results() -> None:
    assert academic_service.summarize([]).canh_bao_hoc_vu is False

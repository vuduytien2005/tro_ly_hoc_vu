"""Sinh viên cần chú ý (trang quản trị Sinh viên): cảnh báo học vụ, nợ học phí, đủ tín chỉ nhưng
chưa đủ điều kiện tốt nghiệp. Hàm thuần build_reasons + API trên CSDL thật (rollback)."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.qlsv_api.models import SinhVien
from src.qlsv_api.schemas import CertificateStatus, GraduationProgressOut
from src.qlsv_api.services.academic_service import AcademicSummary
from src.qlsv_api.services.attention_service import build_reasons

TODAY = date(2026, 11, 20)


def summary(gpa: str = "3.00", failed: int = 0, credits: int = 20) -> AcademicSummary:
    return AcademicSummary(
        gpa=Decimal(gpa),
        tin_chi_tich_luy=credits,
        failed_course_ids=set(range(failed)),
        has_results=True,
    )


def progress(
    du: bool, credits: int = 38, reasons: list[str] | None = None
) -> GraduationProgressOut:
    return GraduationProgressOut(
        ma_sv="SV",
        tong_tin_chi_yeu_cau=38,
        tin_chi_tich_luy=credits,
        gpa=3.0,
        gpa_toi_thieu=2.0,
        hoc_phan_con_thieu=[],
        chung_chi=CertificateStatus(ngoai_ngu=du, gdtc=True, gdqp=True),
        yeu_cau_ngoai_ngu=True,
        du_dieu_kien=du,
        ly_do_chua_du=reasons or [],
    )


def test_nothing_to_flag() -> None:
    assert build_reasons(summary(), [], progress(True, credits=20), TODAY) == []


def test_academic_warning_is_urgent() -> None:
    [r] = build_reasons(summary("1.00", failed=2), [], None, TODAY)
    assert (r.loai, r.muc_do) == ("canh_bao_hoc_vu", "khan")
    assert "1,00" in r.chi_tiet and "2 học phần F" in r.chi_tiet


def test_debt_overdue_is_urgent_and_summed() -> None:
    debts = [(3_500_000, date(2026, 4, 5)), (7_000_000, date(2026, 10, 15))]
    [r] = build_reasons(summary(), debts, None, TODAY)
    assert (r.loai, r.muc_do) == ("no_hoc_phi", "khan")
    assert "10.500.000 đ" in r.chi_tiet and "2 học kỳ" in r.chi_tiet
    assert "05/04/2026" in r.chi_tiet  # hạn sớm nhất đã quá


def test_debt_not_yet_due_is_notice() -> None:
    [r] = build_reasons(summary(), [(1_000_000, date(2026, 12, 15))], None, TODAY)
    assert r.muc_do == "chu_y" and "15/12/2026" in r.chi_tiet


def test_enough_credits_but_not_eligible() -> None:
    p = progress(False, reasons=["Chưa có chứng chỉ ngoại ngữ được duyệt."])
    [r] = build_reasons(summary(credits=38), [], p, TODAY)
    assert (r.loai, r.muc_do) == ("chua_du_dk_tot_nghiep", "chu_y")
    assert "ngoại ngữ" in r.chi_tiet


def test_not_enough_credits_is_not_flagged_for_graduation() -> None:
    assert build_reasons(summary(), [], progress(False, credits=20), TODAY) == []


def test_api_lists_seed_debtors(client: TestClient) -> None:
    body = client.get("/internal/students/attention").json()
    by_sv = {s["ma_sv"]: s for s in body["sinh_vien"]}
    # 03_qlsv_seed.sql: SV22002, SV22003 nợ học phí HK1 2026-2027, hạn 15/10/2026 (đã quá)
    for ma_sv in ("SV22002", "SV22003"):
        reasons = {r["loai"]: r for r in by_sv[ma_sv]["ly_do"]}
        assert reasons["no_hoc_phi"]["muc_do"] == "khan"
    assert body["tong"] == len(body["sinh_vien"])
    assert all(s["ly_do"] for s in body["sinh_vien"])
    urgent = [sum(r["muc_do"] == "khan" for r in s["ly_do"]) for s in body["sinh_vien"]]
    assert urgent == sorted(urgent, reverse=True)


def test_api_skips_students_not_studying(client: TestClient, db: Session) -> None:
    sv = db.scalar(select(SinhVien).where(SinhVien.ma_sv == "SV22003"))
    assert sv is not None
    sv.trang_thai = "bao_luu"
    db.flush()
    body = client.get("/internal/students/attention").json()
    assert "SV22003" not in {s["ma_sv"] for s in body["sinh_vien"]}

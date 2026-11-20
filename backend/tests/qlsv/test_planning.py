"""Lập kế hoạch học kỳ tới (gói đề xuất + lý do loại), dựa trên dữ liệu mẫu (rollback)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from src.qlsv_api.errors import BusinessError
from src.qlsv_api.models import HocKy, LopHocPhan
from src.qlsv_api.services import planning_service, registration_service
from tests.qlsv.conftest import AFTER_REGISTRATION, DEMO_NOW


def plan(db: Session, ma_sv: str):  # type: ignore[no-untyped-def]
    return planning_service.plan_next_semester(db, ma_sv, DEMO_NOW)


def test_plan_sv22001(db: Session) -> None:
    out = plan(db, "SV22001")
    assert [s.ma_lop for s in out.de_xuat] == ["IT004.02", "SE201.01"]
    assert out.tong_tin_chi_de_xuat == 6
    assert (out.hoc_ky, out.tin_chi_toi_da, out.tin_chi_da_dang_ky) == ("2026-2027-HK2", 25, 0)
    assert "Học lại" in out.de_xuat[0].ly_do_chon
    assert out.de_xuat[1].bat_buoc is False
    excluded = {c.ma_hp: c for c in out.bi_loai}
    assert {k: c.ma_loi for k, c in excluded.items()} == {
        "SE105": "DANG_HOC",
        "SE202": "KHONG_CON_LOP_PHU_HOP",
    }
    assert "SE105.01" in excluded["SE105"].ly_do
    assert [(s.ma_lop, s.ma_loi) for s in excluded["SE202"].lop] == [("SE202.01", "LOP_DA_DAY")]


def test_plan_counts_existing_registration(db: Session) -> None:
    registration_service.register(db, "SV22001", "IT004.03", DEMO_NOW)
    db.commit()
    out = plan(db, "SV22001")
    assert [s.ma_lop for s in out.de_xuat] == ["SE201.01"]
    assert "IT004" not in {c.ma_hp for c in out.bi_loai}
    assert out.tin_chi_da_dang_ky == 3


def test_plan_conflict_with_chosen(db: Session) -> None:
    db.execute(
        update(LopHocPhan)
        .where(LopHocPhan.ma_lop == "SE201.01")
        .values(thu=2, tiet_bat_dau=1, tiet_ket_thuc=3)
    )
    db.commit()
    out = plan(db, "SV22001")
    assert [s.ma_lop for s in out.de_xuat] == ["IT004.02"]
    se201 = next(c for c in out.bi_loai if c.ma_hp == "SE201")
    assert [(s.ma_lop, s.ma_loi) for s in se201.lop] == [("SE201.01", "TRUNG_LICH")]
    assert "IT004.02" in se201.lop[0].ly_do


def test_plan_conflict_with_existing_registration(db: Session) -> None:
    """Review Focus 1: lớp đã đăng ký vẫn chiếm lịch."""
    registration_service.register(db, "SV22001", "IT004.02", DEMO_NOW)
    db.commit()
    db.execute(
        update(LopHocPhan)
        .where(LopHocPhan.ma_lop == "SE201.01")
        .values(thu=2, tiet_bat_dau=2, tiet_ket_thuc=4)
    )
    db.commit()
    out = plan(db, "SV22001")
    assert out.de_xuat == []
    se201 = next(c for c in out.bi_loai if c.ma_hp == "SE201")
    assert se201.lop[0].ma_loi == "TRUNG_LICH"


def test_plan_credit_limit(db: Session) -> None:
    db.execute(update(HocKy).where(HocKy.id == 8).values(tin_chi_toi_da=4))
    db.commit()
    out = plan(db, "SV22001")
    assert [s.ma_lop for s in out.de_xuat] == ["IT004.02"]
    se201 = next(c for c in out.bi_loai if c.ma_hp == "SE201")
    assert se201.lop[0].ma_loi == "VUOT_TIN_CHI_TOI_DA"


def test_plan_missing_prerequisite(db: Session) -> None:
    out = plan(db, "SV22002")
    se201 = next(c for c in out.bi_loai if c.ma_hp == "SE201")
    assert se201.ma_loi == "CHUA_DAT_TIEN_QUYET"
    assert "IT003" in se201.ly_do


def test_plan_nothing_available(db: Session) -> None:
    out = plan(db, "SV21001")
    assert out.de_xuat == [] and out.tong_tin_chi_de_xuat == 0
    assert [c.ma_hp for c in out.bi_loai] == ["SE202"]


def test_plan_no_open_semester(db: Session) -> None:
    with pytest.raises(BusinessError) as exc:
        planning_service.plan_next_semester(db, "SV22001", AFTER_REGISTRATION)
    assert (exc.value.code, exc.value.status) == ("KHONG_CO_HOC_KY_MO_DANG_KY", 409)


def test_plan_route(client: TestClient) -> None:
    r = client.get("/internal/students/SV22001/semester-plan")
    assert r.status_code == 200, r.text
    assert r.json()["de_xuat"][0]["ma_lop"] == "IT004.02"
    assert client.get("/internal/students/SV99999/semester-plan").status_code == 404

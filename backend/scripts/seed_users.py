"""Tạo tài khoản mẫu (docs/03-co-so-du-lieu.md) trong CSDL `tlhv_assistant`.

- 5 sinh viên của 03_qlsv_seed.sql + admin; thêm 9 sinh viên nếu đã chạy
  database/11_bo_sung_du_lieu_demo.sql, thêm 5 sinh viên nếu đã chạy
  database/12_du_lieu_mo_phong_hunre.sql.
- Họ tên và ma_khoa của sinh viên lấy từ CSDL `tlhv_qlsv` (nguồn sự thật của trường).
- Chạy lại nhiều lần không bị trùng: đã có email thì chỉ cập nhật thông tin,
  GIỮ NGUYÊN mật khẩu (trừ khi dùng --reset-password).

Chạy từ thư mục backend/:
    python scripts/seed_users.py [--reset-password]
"""

import argparse
import sys
from dataclasses import dataclass

import bcrypt
from sqlalchemy import select

from src.assistant_api.models import NguoiDung
from src.qlsv_api.models import KhoaHoc, SinhVien
from src.shared.db import assistant_session_factory, qlsv_session_factory

# Mật khẩu demo công khai trong tài liệu thiết kế (không phải bí mật hệ thống)
STUDENT_PASSWORD = "Sv@123456"
ADMIN_PASSWORD = "Admin@123456"
STUDENT_IDS = ["SV22001", "SV22002", "SV21001", "SV23001", "SV22003"]
# Sinh viên của database/11_bo_sung_du_lieu_demo.sql: tạo tài khoản nếu đã có trong qlsv
EXTRA_STUDENT_IDS = [
    "SV22004",
    "SV22005",
    "SV22006",
    "SV22007",
    "SV21002",
    "SV21003",
    "SV26001",
    "SV22101",
    "SV23101",
    # database/12_du_lieu_mo_phong_hunre.sql (mô phỏng theo HUNRE, mã SV 10 chữ số)
    "2411100101",
    "2411100102",
    "2411100103",
    "2611100105",
    "2611100117",
]
ADMIN_EMAIL = "admin@truong.example"
ADMIN_NAME = "Quản trị viên"


@dataclass
class AccountSpec:
    email: str
    password: str
    ho_ten: str
    vai_tro: str
    ma_sv: str | None
    ma_khoa: str | None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def load_student_specs() -> list[AccountSpec]:
    with qlsv_session_factory()() as db:
        rows = db.execute(
            select(SinhVien.ma_sv, SinhVien.ho_ten, SinhVien.email, KhoaHoc.ma_khoa)
            .join(KhoaHoc, SinhVien.khoa_hoc_id == KhoaHoc.id)
            .where(SinhVien.ma_sv.in_(STUDENT_IDS + EXTRA_STUDENT_IDS))
        ).all()

    found = {r.ma_sv: r for r in rows}
    missing = [m for m in STUDENT_IDS if m not in found]
    if missing:
        raise SystemExit(
            f"Không tìm thấy sinh viên {missing} trong CSDL qlsv. "
            "Hãy chạy database/03_qlsv_seed.sql trước."
        )
    extra = [m for m in EXTRA_STUDENT_IDS if m in found]
    return [
        AccountSpec(
            email=found[m].email,
            password=STUDENT_PASSWORD,
            ho_ten=found[m].ho_ten,
            vai_tro="sinh_vien",
            ma_sv=m,
            ma_khoa=found[m].ma_khoa,
        )
        for m in STUDENT_IDS + extra
    ]


def upsert_accounts(specs: list[AccountSpec], reset_password: bool) -> tuple[int, int]:
    created = updated = 0
    with assistant_session_factory()() as db, db.begin():
        for spec in specs:
            user = db.scalar(select(NguoiDung).where(NguoiDung.email == spec.email))
            if user is None:
                db.add(
                    NguoiDung(
                        email=spec.email,
                        mat_khau_hash=hash_password(spec.password),
                        ho_ten=spec.ho_ten,
                        vai_tro=spec.vai_tro,
                        ma_sv=spec.ma_sv,
                        ma_khoa=spec.ma_khoa,
                        dang_hoat_dong=True,
                    )
                )
                created += 1
                print(f"  + Tạo mới   {spec.email:<28} {spec.vai_tro:<10} {spec.ma_sv or '-'}")
            else:
                user.ho_ten = spec.ho_ten
                user.vai_tro = spec.vai_tro
                user.ma_sv = spec.ma_sv
                user.ma_khoa = spec.ma_khoa
                user.dang_hoat_dong = True
                if reset_password:
                    user.mat_khau_hash = hash_password(spec.password)
                updated += 1
                print(f"  = Cập nhật  {spec.email:<28} {spec.vai_tro:<10} {spec.ma_sv or '-'}")
    return created, updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tạo tài khoản mẫu cho trợ lý học vụ")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Đặt lại mật khẩu mặc định cho tài khoản đã tồn tại",
    )
    args = parser.parse_args(argv)

    specs = load_student_specs()
    specs.append(
        AccountSpec(ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, "admin", ma_sv=None, ma_khoa=None)
    )
    print("Đang tạo tài khoản mẫu...")
    created, updated = upsert_accounts(specs, args.reset_password)
    print(f"Xong: {created} tạo mới, {updated} cập nhật.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

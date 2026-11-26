"""Nạp bộ kho hỏi đáp mẫu (database/kho_hoi_dap_mau.json) vào CSDL `tlhv_assistant` rồi lập chỉ mục.

- Chỉ thêm các mục CHƯA có (so theo câu hỏi) -> chạy lại nhiều lần không trùng; mục cán bộ đã sửa
  trên trang "Tri thức" giữ nguyên. Người tạo = tài khoản admin (chạy seed_users.py trước).
- Lập chỉ mục ngay trong tiến trình này (cùng cách với quy_che) -> server quy_che (cổng 9104) phải
  đang TẮT để không ghi chồng ChromaDB. Khi quy_che đang chạy: dùng nút "Lập chỉ mục lại" trên trang
  Tri thức, hoặc tắt quy_che (.\\scripts\\run_all.ps1 -Stop) rồi chạy lại.
- --xuat: ghi các mục đang có trong CSDL ra tệp (cập nhật bộ mẫu sau khi sửa trên giao diện).

Chạy từ thư mục backend/:
    python scripts/seed_knowledge.py [--tep PATH] [--xuat] [--embedder model|hashing]
"""

import argparse
import socket
import sys
from pathlib import Path

from sqlalchemy import select

from src.assistant_api.knowledge_seed import (
    export_entries,
    index_knowledge,
    insert_missing,
    load_entries,
)
from src.assistant_api.models import NguoiDung, VanBan
from src.rag.embedder import Embedder, HashingEmbedder, get_embedder
from src.rag.knowledge import KNOWLEDGE_KIND
from src.rag.store import VectorStore
from src.shared.config import PROJECT_ROOT, get_settings
from src.shared.db import assistant_session_factory

DEFAULT_FILE = PROJECT_ROOT / "database" / "kho_hoi_dap_mau.json"
ADMIN_EMAIL = "admin@truong.example"
QUY_CHE_PORT = 9104


def _port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description="Nạp / xuất bộ kho hỏi đáp mẫu")
    parser.add_argument("--tep", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--xuat", action="store_true", help="ghi mục trong CSDL ra tệp")
    parser.add_argument("--embedder", choices=["model", "hashing"], default="model")
    args = parser.parse_args(argv)
    factory = assistant_session_factory()

    if args.xuat:
        with factory() as db:
            n = export_entries(db, args.tep)
        print(f"Đã ghi {n} mục ra {args.tep}")
        return 0

    try:
        entries = load_entries(args.tep)
    except (OSError, ValueError) as exc:
        print(f"Lỗi tệp {args.tep}: {exc}", file=sys.stderr)
        return 1

    with factory() as db:
        admin = db.scalar(select(NguoiDung).where(NguoiDung.email == ADMIN_EMAIL))
        if admin is None:
            print("Chưa có tài khoản admin: chạy scripts/seed_users.py trước.", file=sys.stderr)
            return 1
        added = insert_missing(db, entries, admin.id)
        db.commit()
        doc = db.scalar(select(VanBan).where(VanBan.loai == KNOWLEDGE_KIND))
        indexed = doc is not None and doc.trang_thai == "da_lap_chi_muc"
        print(f"Kho hỏi đáp: thêm {added} mục mới ({len(entries)} mục trong tệp).")
        if added == 0 and indexed:
            print("Văn bản kho đã được lập chỉ mục, không cần làm gì thêm.")
            return 0
        if _port_busy(QUY_CHE_PORT):
            print(
                "Server quy_che (cổng 9104) đang chạy nên chưa lập chỉ mục: vào trang Tri thức "
                "bấm 'Lập chỉ mục lại', hoặc tắt quy_che rồi chạy lại script này.",
                file=sys.stderr,
            )
            return 2
        settings = get_settings()
        embedder: Embedder = HashingEmbedder() if args.embedder == "hashing" else get_embedder()
        store = VectorStore(settings.chroma_dir, embedder.name)
        van_ban_id = index_knowledge(db, store, embedder)
        db.commit()
        print(f"Đã lập chỉ mục văn bản kho (id {van_ban_id}) bằng {embedder.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

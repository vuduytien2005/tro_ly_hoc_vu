"""Nạp bộ văn bản thực nghiệm vào một môi trường CÔ LẬP.

- CSDL tlhv_assistant: một kết nối với transaction ngoài cùng, ROLLBACK khi kết thúc. Đầu phiên xóa
  mọi văn bản đang có (cũng bị rollback) -> kết quả không lẫn văn bản thật đã nạp, và không để lại
  dữ liệu gì sau khi chạy.
- ChromaDB: thư mục tạm, xóa khi kết thúc (không đụng data/chroma).
Cách làm giống fixture của backend/tests (join_transaction_mode="create_savepoint").
"""

import importlib.util
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from evaluation.common import BACKEND, ROOT


def _ingest_module() -> Any:
    """Dùng lại read_catalog của backend/scripts/ingest_folder.py (cùng định dạng danh_muc.csv)."""
    path = BACKEND / "scripts" / "ingest_folder.py"
    spec = importlib.util.spec_from_file_location("ingest_folder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class IsolatedDb:
    connection: Any
    factory: Callable[[], Any]


@contextmanager
def isolated_db(engine: Any) -> Iterator[IsolatedDb]:
    from sqlalchemy.orm import Session

    connection = engine.connect()
    outer = connection.begin()

    def factory() -> Session:
        return Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
            expire_on_commit=False,
        )

    try:
        yield IsolatedDb(connection, factory)
    finally:
        outer.rollback()
        connection.close()


@contextmanager
def temp_dir(prefix: str) -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def corpus_folders(config: dict[str, Any]) -> list[Path]:
    value = config.get("corpus") or "evaluation/corpus_demo"
    items = value if isinstance(value, list) else [value]
    return [(ROOT / v).resolve() for v in items]


def index_corpus(
    factory: Callable[[], Any],
    store: Any,
    embedder: Any,
    folders: Sequence[Path],
    strategy: str | None = None,
    max_tokens: int = 512,
) -> dict[str, Any]:
    """Xóa văn bản cũ (trong transaction) rồi lập chỉ mục mọi tệp trong danh_muc.csv
    của từng thư mục."""
    from sqlalchemy import delete
    from src.assistant_api.models import VanBan
    from src.rag.indexer import index_document

    ingest = _ingest_module()
    started = time.perf_counter()
    docs = chunks = 0
    with factory() as db:
        db.execute(delete(VanBan))
        db.commit()
        for folder in folders:
            catalog = folder / "danh_muc.csv"
            if not catalog.exists():
                raise SystemExit(f"Không thấy {catalog}")
            for meta in ingest.read_catalog(catalog, folder, strategy):
                path = folder / meta.ten_tep
                if not path.exists():
                    raise SystemExit(f"danh_muc.csv khai báo {meta.ten_tep} nhưng không có tệp")
                meta = replace(meta, duong_dan_tep=str(path))
                result = index_document(db, store, embedder, path, meta, max_tokens=max_tokens)
                docs += 1
                chunks += result.so_doan
        db.commit()
    return {"so_van_ban": docs, "so_doan": chunks, "giay": round(time.perf_counter() - started, 1)}

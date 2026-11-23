"""Truy xuất hybrid: vector (ChromaDB) + từ khóa (BM25) -> hợp nhất RRF -> (tuỳ chọn) rerank.

search(cau_hoi, ma_khoa, top_k):
1. k = số khóa (K22 -> 22).
2. Vector: Chroma top `candidates`, lọc ap_dung_tu <= k <= ap_dung_den (lọc lại ở CSDL, kèm
   ngày hiệu lực).
3. BM25: top `candidates` trên các đoạn thuộc văn bản `da_lap_chi_muc` áp dụng cho khóa k và
   đã có hiệu lực (ngay_hieu_luc NULL hoặc <= hôm nay; hôm nay theo DEMO_NOW nếu có).
4. RRF: score(d) = Σ 1 / (rrf_k + rank_i(d)), rank tính từ 1.
5. Rerank cross-encoder trên top `rerank_top` (nếu bật).
6. Lấy chi tiết đoạn từ CSDL (chỉ đoạn của văn bản `da_lap_chi_muc` -> bỏ vector "mồ côi"),
   đánh số so = 1..top_k.

Chỉ mục BM25 được cache theo (khóa, ngày) và tự dựng lại khi dữ liệu văn bản đổi (kiểm tra "dấu vết"
COUNT + MAX(updated_at) mỗi lần tìm) -> server quy_che đang chạy thấy ngay văn bản mới nạp.
"""

import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from src.assistant_api.models import DoanVanBan, VanBan
from src.rag.embedder import Embedder, Reranker
from src.rag.keyword import KeywordIndex
from src.rag.store import VectorStore
from src.shared.time import now

logger = logging.getLogger(__name__)

MA_KHOA_RE = re.compile(r"^\s*[Kk]?(\d{2})\s*$")
INDEXED = "da_lap_chi_muc"


class InvalidCohortError(ValueError):
    pass


def parse_ma_khoa(ma_khoa: str) -> int:
    """'K22' -> 22. Nhận 'K22', 'k22', '22'."""
    m = MA_KHOA_RE.match(ma_khoa or "")
    if not m:
        raise InvalidCohortError(f"Mã khóa không hợp lệ: '{ma_khoa}' (định dạng đúng: K22).")
    return int(m.group(1))


@dataclass(frozen=True)
class SearchOptions:
    """Các cờ bật/tắt phục vụ thực nghiệm Chương 4."""

    use_vector: bool = True
    use_keyword: bool = True
    use_version_filter: bool = True
    use_rerank: bool = False
    candidates: int = 20
    rrf_k: int = 60
    rerank_top: int = 15


@dataclass
class RetrievedChunk:
    so: int
    doan_id: int
    van_ban_id: int
    van_ban: str
    phien_ban: str
    chuong: str | None
    dieu: str | None
    khoan: str | None
    trang: int | None
    noi_dung: str
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rerank_score: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _today() -> date:
    """Ngày hiện tại theo giờ Việt Nam (tôn trọng DEMO_NOW). Test có thể thay hàm này."""
    return now().date()


def _applies_to(khoa: int, today: date) -> Any:
    """Văn bản áp dụng cho khóa `khoa` VÀ đã có hiệu lực vào ngày `today`.

    Văn bản chưa đến ngày hiệu lực (vd quy chế mới ban hành trước, áp dụng từ năm học sau) chưa
    được trích dẫn. Văn bản thay thế nhau giữa các khóa do khoảng áp dụng khóa quyết định.
    """
    return and_(
        or_(VanBan.ap_dung_tu_khoa.is_(None), VanBan.ap_dung_tu_khoa <= khoa),
        or_(VanBan.ap_dung_den_khoa.is_(None), VanBan.ap_dung_den_khoa >= khoa),
        or_(VanBan.ngay_hieu_luc.is_(None), VanBan.ngay_hieu_luc <= today),
    )


def _indexed_chunks(khoa: int | None, today: date) -> Select[Any]:
    stmt = (
        select(DoanVanBan.id, DoanVanBan.noi_dung)
        .join(VanBan, VanBan.id == DoanVanBan.van_ban_id)
        .where(VanBan.trang_thai == INDEXED)
        .order_by(DoanVanBan.id)
    )
    return stmt.where(_applies_to(khoa, today)) if khoa is not None else stmt


def rrf_fuse(rankings: list[list[int]], rrf_k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion; mỗi ranking là danh sách id theo thứ tự tốt -> kém."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)


class Retriever:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        store: VectorStore,
        embedder: Embedder,
        reranker: Reranker | None = None,
        default_options: SearchOptions | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._store = store
        self._embedder = embedder
        self._reranker = reranker
        self.default_options = default_options or SearchOptions()
        self._lock = threading.Lock()
        self._stamp: tuple[Any, ...] | None = None
        # Khóa cache: (khóa, ngày) — sang ngày mới thì văn bản vừa có hiệu lực được nạp vào BM25
        self._keyword_indexes: dict[tuple[int | None, date | None], KeywordIndex[int]] = {}

    @property
    def store(self) -> VectorStore:
        return self._store

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    @property
    def has_reranker(self) -> bool:
        return self._reranker is not None

    # ----- BM25 cache --------------------------------------------------------
    @staticmethod
    def _data_stamp(db: Session) -> tuple[Any, ...]:
        row = db.execute(
            select(
                func.count(VanBan.id),
                func.max(VanBan.updated_at),
                select(func.count(DoanVanBan.id)).scalar_subquery(),
            )
        ).one()
        return tuple(row)

    def _keyword_index(self, db: Session, khoa: int | None, today: date) -> KeywordIndex[int]:
        with self._lock:
            stamp = self._data_stamp(db)
            if stamp != self._stamp:
                self._keyword_indexes.clear()
                self._stamp = stamp
            key = (khoa, today if khoa is not None else None)
            index = self._keyword_indexes.get(key)
            if index is None:
                docs = [(row.id, row.noi_dung) for row in db.execute(_indexed_chunks(khoa, today))]
                index = KeywordIndex(docs)
                self._keyword_indexes[key] = index
                logger.info("Dựng chỉ mục BM25 (khóa=%s): %d đoạn", khoa, len(index))
            return index

    # ----- Truy xuất ---------------------------------------------------------
    def search(
        self,
        cau_hoi: str,
        ma_khoa: str | None,
        top_k: int = 5,
        options: SearchOptions | None = None,
    ) -> list[RetrievedChunk]:
        opts = options or self.default_options
        if not (opts.use_vector or opts.use_keyword):
            raise ValueError("Cần bật ít nhất một trong use_vector / use_keyword.")
        khoa = parse_ma_khoa(ma_khoa or "") if opts.use_version_filter else None
        today = _today()
        query = cau_hoi.strip()
        if not query:
            return []

        with self._session_factory() as db:
            vector_ids: list[int] = []
            vector_rank: dict[int, int] = {}
            if opts.use_vector:
                hits = self._store.query(self._embedder.embed_query(query), opts.candidates, khoa)
                by_vid = self._chunk_ids_for_vectors(db, [h.vector_id for h in hits], khoa, today)
                vector_ids = [by_vid[h.vector_id] for h in hits if h.vector_id in by_vid]
                vector_rank = {doc_id: i for i, doc_id in enumerate(vector_ids, start=1)}

            keyword_ids: list[int] = []
            keyword_rank: dict[int, int] = {}
            if opts.use_keyword:
                hits_kw = self._keyword_index(db, khoa, today).search(query, opts.candidates)
                keyword_ids = [doc_id for doc_id, _ in hits_kw]
                keyword_rank = {doc_id: i for i, doc_id in enumerate(keyword_ids, start=1)}

            fused = rrf_fuse([r for r in (vector_ids, keyword_ids) if r], opts.rrf_k)
            if not fused:
                return []

            rerank_scores: dict[int, float] = {}
            if opts.use_rerank and self._reranker is not None:
                head = [doc_id for doc_id, _ in fused[: opts.rerank_top]]
                texts = self._texts(db, head)
                scores = self._reranker.score(query, [texts[i] for i in head])
                rerank_scores = dict(zip(head, scores, strict=True))
                fused = sorted(
                    ((i, rerank_scores[i]) for i in head), key=lambda kv: kv[1], reverse=True
                )
            elif opts.use_rerank:
                logger.warning("use_rerank=True nhưng chưa cấu hình reranker -> bỏ qua rerank.")

            selected = fused[:top_k]
            details = self._details(db, [doc_id for doc_id, _ in selected])

        results: list[RetrievedChunk] = []
        for doc_id, score in selected:
            chunk = details.get(doc_id)
            if chunk is None:
                continue
            results.append(
                replace(
                    chunk,
                    so=len(results) + 1,
                    score=score,
                    vector_rank=vector_rank.get(doc_id),
                    keyword_rank=keyword_rank.get(doc_id),
                    rerank_score=rerank_scores.get(doc_id),
                )
            )
        return results

    # ----- Truy vấn CSDL -----------------------------------------------------
    @staticmethod
    def _chunk_ids_for_vectors(
        db: Session, vector_ids: list[str], khoa: int | None, today: date
    ) -> dict[str, int]:
        if not vector_ids:
            return {}
        stmt = (
            select(DoanVanBan.vector_id, DoanVanBan.id)
            .join(VanBan, VanBan.id == DoanVanBan.van_ban_id)
            .where(DoanVanBan.vector_id.in_(vector_ids), VanBan.trang_thai == INDEXED)
        )
        # Lọc lần 2 ở CSDL: phòng metadata Chroma lệch với CSDL; ngày hiệu lực chỉ có ở CSDL
        if khoa is not None:
            stmt = stmt.where(_applies_to(khoa, today))
        return {vid: doc_id for vid, doc_id in db.execute(stmt)}

    @staticmethod
    def _texts(db: Session, ids: list[int]) -> dict[int, str]:
        rows = db.execute(select(DoanVanBan.id, DoanVanBan.noi_dung).where(DoanVanBan.id.in_(ids)))
        return {doc_id: text for doc_id, text in rows}

    @staticmethod
    def _details(db: Session, ids: list[int]) -> dict[int, RetrievedChunk]:
        if not ids:
            return {}
        rows = db.execute(
            select(DoanVanBan, VanBan.ten, VanBan.phien_ban)
            .join(VanBan, VanBan.id == DoanVanBan.van_ban_id)
            .where(DoanVanBan.id.in_(ids))
        )
        return {
            d.id: RetrievedChunk(
                so=0,
                doan_id=d.id,
                van_ban_id=d.van_ban_id,
                van_ban=ten,
                phien_ban=phien_ban,
                chuong=d.chuong,
                dieu=d.dieu,
                khoan=d.khoan,
                trang=d.trang,
                noi_dung=d.noi_dung,
                score=0.0,
            )
            for d, ten, phien_ban in rows
        }


_default: Retriever | None = None
_default_lock = threading.Lock()


def get_retriever() -> Retriever:
    """Retriever dùng chung cho service (mô hình thật, Chroma tại CHROMA_DIR)."""
    global _default
    with _default_lock:
        if _default is None:
            from src.rag.embedder import get_embedder, get_reranker
            from src.shared.config import get_settings
            from src.shared.db import assistant_session_factory

            settings = get_settings()
            embedder = get_embedder()
            _default = Retriever(
                session_factory=assistant_session_factory(),
                store=VectorStore(settings.chroma_dir, embedder.name),
                embedder=embedder,
                reranker=get_reranker() if settings.rerank_enabled else None,
                default_options=SearchOptions(use_rerank=settings.rerank_enabled),
            )
        return _default

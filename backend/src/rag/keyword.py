"""Tìm theo từ khóa bằng BM25 (rank-bm25, BM25Okapi) — nửa "từ khóa" của hybrid search.

Tách từ tiếng Việt đơn giản, không cần thư viện tách từ:
- chuẩn hóa NFC, chữ thường, tách theo ký tự không phải chữ/số -> các âm tiết;
- GIỮ âm tiết 1–2 ký tự ("đi", "kỳ", "nợ") vì tiếng Việt có nhiều âm tiết ngắn mang nghĩa;
- thêm bigram âm tiết liền kề ("học_lại", "tín_chỉ") để bắt cụm từ: tài liệu chứa "học lại"
  được điểm cao hơn tài liệu chỉ có "học" và "lại" ở hai chỗ khác nhau.
"""

import re
import unicodedata
from collections.abc import Hashable, Sequence
from typing import Generic, TypeVar

from rank_bm25 import BM25Okapi

WORD_RE = re.compile(r"\w+", re.UNICODE)

K = TypeVar("K", bound=Hashable)


def tokenize(text: str) -> list[str]:
    syllables = WORD_RE.findall(unicodedata.normalize("NFC", text).lower())
    bigrams = [f"{a}_{b}" for a, b in zip(syllables, syllables[1:], strict=False)]
    return syllables + bigrams


class KeywordIndex(Generic[K]):
    """Chỉ mục BM25 trong bộ nhớ trên một tập đoạn cố định."""

    def __init__(self, docs: Sequence[tuple[K, str]]) -> None:
        self.ids: list[K] = [doc_id for doc_id, _ in docs]
        corpus = [tokenize(text) for _, text in docs]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def __len__(self) -> int:
        return len(self.ids)

    def search(self, query: str, top_n: int = 20) -> list[tuple[K, float]]:
        """Top `top_n` (id, điểm) có điểm > 0, điểm giảm dần."""
        tokens = tokenize(query)
        if self._bm25 is None or not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(self.ids)), key=lambda i: scores[i], reverse=True)
        return [(self.ids[i], float(scores[i])) for i in ranked[:top_n] if scores[i] > 0]

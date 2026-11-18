"""Biến văn bản thành vector.

- `SentenceTransformerEmbedder`: mô hình thật (mặc định intfloat/multilingual-e5-base, chạy CPU).
  Họ e5 yêu cầu tiền tố "query: " cho câu hỏi và "passage: " cho đoạn văn bản.
  Vector luôn được chuẩn hóa (độ dài 1) -> khoảng cách cosine.
- `HashingEmbedder`: embedding giả, tất định, không cần tải mô hình — dùng cho test và thử nhanh.
  Mỗi âm tiết/bigram được băm vào một chiều -> giống "túi từ", vẫn đủ để kiểm tra luồng xử lý.
- `Reranker`: cross-encoder (BAAI/bge-reranker-v2-m3), chỉ nạp khi bật RERANK_ENABLED.
"""

import hashlib
import logging
import math
import re
from functools import lru_cache
from typing import Any, Protocol

from src.rag.keyword import tokenize
from src.shared.config import get_settings

logger = logging.getLogger(__name__)


def model_slug(model_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def count_tokens(self, text: str) -> int: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, batch_size: int = 16) -> None:
        self.name = model_name
        self.batch_size = batch_size
        self._model: Any = None
        is_e5 = "e5" in model_name.lower()
        self._query_prefix = "query: " if is_e5 else ""
        self._passage_prefix = "passage: " if is_e5 else ""

    @property
    def model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Nạp mô hình embedding %s (lần đầu sẽ tải về máy)...", self.name)
            self._model = SentenceTransformer(self.name, device="cpu")
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 64,
        )
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._passage_prefix + t for t in texts]) if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self._query_prefix + text])[0]

    def count_tokens(self, text: str) -> int:
        return len(self.model.tokenizer(text, add_special_tokens=False)["input_ids"])


class HashingEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self.name = f"hashing-{dim}"
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            h = int.from_bytes(hashlib.md5(token.encode("utf-8")).digest()[:4], "little")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def count_tokens(self, text: str) -> int:
        from src.rag.chunker import approx_token_count

        return approx_token_count(text)


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        self.name = model_name
        self._model: Any = None

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Nạp mô hình rerank %s (lần đầu sẽ tải về máy)...", self.name)
            self._model = CrossEncoder(self.name, device="cpu", max_length=512)
        return [float(s) for s in self._model.predict([(query, p) for p in passages])]


@lru_cache
def get_embedder() -> Embedder:
    return SentenceTransformerEmbedder(get_settings().embedding_model)


@lru_cache
def get_reranker() -> Reranker:
    return CrossEncoderReranker(get_settings().reranker_model)

"""Kho vector ChromaDB (chế độ persistent, không cần server).

- Mỗi mô hình embedding một collection riêng: `quy_che__{slug_mo_hinh}` (đổi mô hình = lập chỉ mục
  lại, không trộn vector của 2 mô hình).
- Khoảng cách cosine (vector đã chuẩn hóa).
- Metadata: van_ban_id, doan_id, loai, phien_ban, ap_dung_tu, ap_dung_den, dieu, trang.
  ap_dung_tu/den là số khóa 2 chữ số; NULL trong CSDL -> 0 / 99 (Chroma không nhận None).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.rag.embedder import model_slug

COLLECTION_PREFIX = "quy_che__"
OPEN_FROM = 0
OPEN_TO = 99


def collection_name(model_name: str) -> str:
    return f"{COLLECTION_PREFIX}{model_slug(model_name)}"[:63].rstrip("_")


def version_filter(khoa: int) -> dict[str, Any]:
    return {"$and": [{"ap_dung_tu": {"$lte": khoa}}, {"ap_dung_den": {"$gte": khoa}}]}


@dataclass(frozen=True)
class VectorHit:
    vector_id: str
    distance: float


class VectorStore:
    def __init__(self, path: Path, model_name: str) -> None:
        import chromadb
        from chromadb.config import Settings

        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path), settings=Settings(anonymized_telemetry=False)
        )
        self.name = collection_name(model_name)
        self._collection = self._client.get_or_create_collection(
            self.name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
        )

    def count(self) -> int:
        return self._collection.count()

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if ids:
            self._collection.upsert(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

    def delete_document(self, van_ban_id: int) -> None:
        self._collection.delete(where={"van_ban_id": van_ban_id})

    def query(
        self, embedding: list[float], n_results: int, khoa: int | None = None
    ) -> list[VectorHit]:
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=version_filter(khoa) if khoa is not None else None,
            include=["distances"],
        )
        return [
            VectorHit(vid, float(dist))
            for vid, dist in zip(result["ids"][0], result["distances"][0], strict=True)
        ]

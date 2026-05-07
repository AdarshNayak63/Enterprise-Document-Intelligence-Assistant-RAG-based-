import json
import os
from typing import List, Dict, Any, Optional
import faiss
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document


class VectorStore:
    def __init__(self):
        os.makedirs(settings.faiss_dir, exist_ok=True)
        self._model = None

    @property
    def model(self):
        if self._model is None:
            # Lazy import to avoid loading heavy ML libraries at startup
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    def _index_path(self, user_id: int) -> str:
        return os.path.join(settings.faiss_dir, f"user_{user_id}.index")

    def _meta_path(self, user_id: int) -> str:
        return os.path.join(settings.faiss_dir, f"user_{user_id}_meta.json")

    def _load(self, user_id: int):
        idx_path = self._index_path(user_id)
        meta_path = self._meta_path(user_id)
        if os.path.exists(idx_path) and os.path.exists(meta_path):
            index = faiss.read_index(idx_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return index, metadata
        index = faiss.IndexFlatL2(384)
        return index, []

    def _save(self, user_id: int, index, metadata):
        faiss.write_index(index, self._index_path(user_id))
        with open(self._meta_path(user_id), "w", encoding="utf-8") as f:
            json.dump(metadata, f)

    def add_chunks(self, user_id: int, chunk_records: List[Dict[str, Any]]):
        texts = [c["content"] for c in chunk_records]
        if not texts:
            return
        vectors = self.model.encode(texts, normalize_embeddings=True)
        vectors = np.array(vectors).astype("float32")

        index, metadata = self._load(user_id)
        index.add(vectors)
        metadata.extend(chunk_records)
        self._save(user_id, index, metadata)

    def search(self, user_id: int, query: str, top_k: int = 5, doc_ids: Optional[List[int]] = None):
        index, metadata = self._load(user_id)
        if index.ntotal == 0:
            return []
        qv = self.model.encode([query], normalize_embeddings=True)
        qv = np.array(qv).astype("float32")
        distances, indices = index.search(qv, min(top_k * 3, index.ntotal))

        results = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(metadata):
                continue
            m = metadata[idx]
            if doc_ids and m["document_id"] not in doc_ids:
                continue
            results.append(m)
            if len(results) >= top_k:
                break
        return results

    def rebuild_user_index(self, db: Session, user_id: int):
        chunks = (
            db.query(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .filter(Document.user_id == user_id)
            .all()
        )
        records = [
            {
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "filename": doc.filename,
                "page_number": chunk.page_number,
                "content": chunk.content,
            }
            for chunk, doc in chunks
        ]
        if not records:
            for p in [self._index_path(user_id), self._meta_path(user_id)]:
                if os.path.exists(p):
                    os.remove(p)
            return

        vectors = self.model.encode([r["content"] for r in records], normalize_embeddings=True)
        vectors = np.array(vectors).astype("float32")
        index = faiss.IndexFlatL2(vectors.shape[1])
        index.add(vectors)
        self._save(user_id, index, records)


vector_store = VectorStore()

"""Vector store backed by ChromaDB + sentence-transformers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .ingest import Chunk

# Small + fast + good-enough. Swap to a larger model for better recall.
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_COLLECTION = "notes"
DEFAULT_DB_DIR = Path.home() / ".rag-notes" / "chroma"


@dataclass
class Hit:
    """A retrieval hit: a chunk and how close it was."""
    text: str
    source: str
    chunk_index: int
    distance: float


class VectorStore:
    """Thin wrapper around a persistent Chroma collection."""

    def __init__(
        self,
        *,
        db_dir: Path = DEFAULT_DB_DIR,
        collection: str = DEFAULT_COLLECTION,
        embed_model: str = DEFAULT_EMBED_MODEL,
    ) -> None:
        db_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(db_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
        # Lazy-load the embedding model on first use.
        self._embed_model_name = embed_model
        self._embedder: SentenceTransformer | None = None

    # ---- embeddings -------------------------------------------------------

    def _embedder_or_load(self) -> SentenceTransformer:
        if self._embedder is None:
            self._embedder = SentenceTransformer(self._embed_model_name)
        return self._embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._embedder_or_load()
        vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    # ---- writes -----------------------------------------------------------

    def add_chunks(self, chunks: Iterable[Chunk], batch_size: int = 64) -> int:
        """Embed and upsert a batch of chunks. Returns the count added."""
        batch: list[Chunk] = []
        added = 0
        for c in chunks:
            batch.append(c)
            if len(batch) >= batch_size:
                added += self._upsert(batch)
                batch = []
        if batch:
            added += self._upsert(batch)
        return added

    def _upsert(self, batch: list[Chunk]) -> int:
        embeddings = self.embed([c.text for c in batch])
        self._collection.upsert(
            ids=[c.id for c in batch],
            documents=[c.text for c in batch],
            embeddings=embeddings,
            metadatas=[
                {"source": c.source, "chunk_index": c.chunk_index} for c in batch
            ],
        )
        return len(batch)

    # ---- reads ------------------------------------------------------------

    def query(self, question: str, k: int = 5) -> list[Hit]:
        if self._collection.count() == 0:
            return []
        q_emb = self.embed([question])[0]
        result = self._collection.query(
            query_embeddings=[q_emb],
            n_results=min(k, self._collection.count()),
        )
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        return [
            Hit(
                text=doc,
                source=meta.get("source", "<unknown>"),
                chunk_index=int(meta.get("chunk_index", -1)),
                distance=float(dist),
            )
            for doc, meta, dist in zip(docs, metas, dists)
        ]

    def stats(self) -> dict:
        return {
            "count": self._collection.count(),
            "collection": self._collection.name,
            "embed_model": self._embed_model_name,
        }

    def reset(self) -> None:
        """Delete every document in the collection."""
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

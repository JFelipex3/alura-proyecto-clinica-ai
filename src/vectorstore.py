from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import chromadb
from google import genai
from google.genai import types
from chromadb.config import Settings

_EMBEDDING_MODEL = "models/gemini-embedding-001"
_COLLECTION = "clinica_bienestar"
_BATCH = 20
_SLEEP_BETWEEN = 13.0
_MAX_RETRIES = 5


class VectorStore:
    def __init__(self, persist_dir: str = "./chroma_db") -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")
        self._genai = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1"),
        )

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, texts: List[str], task_type: str) -> List[List[float]]:
        from google.genai.errors import ClientError

        delay = 60.0
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                result = self._genai.models.embed_content(
                    model=_EMBEDDING_MODEL,
                    contents=texts,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return [e.values for e in result.embeddings]
            except ClientError as exc:
                if exc.status_code != 429 or attempt == _MAX_RETRIES:
                    raise
                try:
                    retry_secs = float(
                        exc.details["error"]["details"][-1]["retryDelay"].rstrip("s")
                    )
                    wait = retry_secs + 5
                except Exception:
                    wait = delay
                print(
                    f"  [rate-limit] cuota agotada, reintento {attempt}/{_MAX_RETRIES - 1}"
                    f" en {wait:.0f}s…"
                )
                time.sleep(wait)
                delay = min(delay * 2, 120)

    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def _embed_query(self, text: str) -> List[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def add_documents(self, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return
        total = len(chunks)
        for start in range(0, total, _BATCH):
            batch = chunks[start : start + _BATCH]
            texts = [c["content"] for c in batch]
            metas = [c["metadata"] for c in batch]
            ids = [f"{m['source']}_c{m['chunk_index']}" for m in metas]

            embeddings = self._embed_documents(texts)
            self._col.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metas,
            )
            print(f"  Indexados {min(start + _BATCH, total)}/{total} fragmentos…")
            if start + _BATCH < total:
                time.sleep(_SLEEP_BETWEEN)

    def search(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query_emb = self._embed_query(query)
        where = {"category": category} if category else None
        result = self._col.query(
            query_embeddings=[query_emb],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            hits.append({"content": doc, "metadata": meta, "score": 1.0 - dist})
        return hits

    def count(self) -> int:
        return self._col.count()

    def reset(self) -> None:
        self._client.delete_collection(_COLLECTION)
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

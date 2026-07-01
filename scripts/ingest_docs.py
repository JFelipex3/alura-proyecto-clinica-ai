#!/usr/bin/env python3
"""Indexa todos los documentos del directorio docs/ en ChromaDB."""
from __future__ import annotations

# --- PARCHE DE SQLITE3 PARA CHROMADB ---
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
# ---------------------------------------
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from src.ingestion import load_and_chunk_documents
from src.vectorstore import VectorStore


def main() -> None:
    docs_dir = Path(__file__).parent.parent / "docs"
    if not docs_dir.exists():
        print(f"[ERROR] El directorio {docs_dir} no existe.")
        sys.exit(1)

    print(f"Cargando documentos desde: {docs_dir}\n")
    chunks = load_and_chunk_documents(str(docs_dir))

    if not chunks:
        print("[ERROR] No se encontraron documentos para indexar.")
        sys.exit(1)

    print(f"\nTotal de fragmentos generados: {len(chunks)}")
    print("Indexando en ChromaDB...\n")

    store = VectorStore(persist_dir="./chroma_db")
    store.reset()
    store.add_documents(chunks)

    print(f"\n✅ Indexación completada: {store.count()} fragmentos almacenados.")


if __name__ == "__main__":
    main()

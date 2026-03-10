"""Schritt 2 – Index: Chunks erstellen, Embeddings berechnen, Index aufbauen.

Liest normalisierte Dokumente aus data/processed/, erstellt Chunks,
berechnet Embeddings und persistiert den Index in data/index/.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    INDEX_DIR,
    INTERIM_DIR,
    PROCESSED_DIR,
)
from rag.index.chunking import chunk_documents
from rag.index.embeddings import embed_texts
from rag.index.vectorstore import create_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Index-Pipeline gestartet ===")

    # 1. Normalisierte Dokumente laden
    docs_path = INTERIM_DIR / "documents.json"
    documents = json.loads(docs_path.read_text(encoding="utf-8"))
    logger.info("%d Dokumente geladen aus %s", len(documents), docs_path)

    # 2. Chunking
    chunks = chunk_documents(documents, CHUNK_SIZE, CHUNK_OVERLAP)
    logger.info("%d Chunks erstellt", len(chunks))

    # 2b. Chunks persistieren
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    chunks_path = PROCESSED_DIR / "chunks.json"
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Chunks gespeichert: %s", chunks_path)

    # 3. Embeddings
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts, EMBEDDING_MODEL)
    logger.info("%d Embeddings berechnet", len(embeddings))

    # 4. Index erstellen und persistieren
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    create_index(chunks, embeddings, INDEX_DIR)
    logger.info("Index gespeichert in %s", INDEX_DIR)

    logger.info("=== Index-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

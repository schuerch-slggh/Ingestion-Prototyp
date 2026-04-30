"""Schritt 2 – Index: Chunks erstellen, Embeddings berechnen, Index aufbauen.

Liest normalisierte Dokumente aus data/interim/, erstellt Chunks,
berechnet Embeddings und persistiert Index und Chunks in
variantenspezifischen Unterordnern.

Verwendung:
    python scripts/Pipeline/02_index.py [--variant v0]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    INTERIM_DIR,
    VARIANT,
    get_variant_chunks_dir,
    get_variant_index_dir,
)
from rag.index.embeddings import embed_texts
from rag.index.vectorstore import create_index
from rag.pipeline_factory import get_chunker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schritt 2 – Index")
    parser.add_argument(
        "--variant",
        default=VARIANT,
        help="Pipeline-Variante (v0|v1|v2|v3). Standard: Umgebungsvariable VARIANT oder 'v0'.",
    )
    args = parser.parse_args()
    variant = args.variant

    logger.info("=== Index-Pipeline gestartet (Variante: %s) ===", variant)

    # 1. Normalisierte Dokumente laden (INTERIM_DIR ist variantenunabhängig)
    docs_path = INTERIM_DIR / "documents.json"
    documents = json.loads(docs_path.read_text(encoding="utf-8"))
    logger.info("%d Dokumente geladen aus %s", len(documents), docs_path)

    # 2. Chunking via Factory
    chunker = get_chunker(variant)
    chunks = chunker(documents, CHUNK_SIZE, CHUNK_OVERLAP)
    logger.info("%d Chunks erstellt", len(chunks))

    # 2b. Chunks persistieren (variantenspezifisch)
    chunks_dir = get_variant_chunks_dir(variant)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = chunks_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Chunks gespeichert: %s", chunks_path)

    # 3. Embeddings
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts, EMBEDDING_MODEL)
    logger.info("%d Embeddings berechnet", len(embeddings))

    # 4. Index erstellen und persistieren (variantenspezifisch)
    index_dir = get_variant_index_dir(variant)
    index_dir.mkdir(parents=True, exist_ok=True)
    create_index(chunks, embeddings, index_dir)
    logger.info("Index gespeichert in %s", index_dir)

    logger.info("=== Index-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

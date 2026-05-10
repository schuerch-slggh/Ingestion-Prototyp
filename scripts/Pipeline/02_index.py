"""Schritt 2 – Index: Gold-JSONL laden, chunken, embedden, in ChromaDB speichern.

Aufruf:
    python scripts/Pipeline/02_index.py [--variant v0] [--reset] [--max-chunks N]
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import tiktoken

from rag.config import EMBEDDING_MODEL, GOLD_DIR, VARIANT
from rag.index.embeddings import embed_chunks
from rag.index.vectorstore import add_chunks_to_collection, get_or_create_collection
from rag.pipeline_factory import get_chunker

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GOLD_FILES = [
    "forum.jsonl",
    "tickets.jsonl",
    "handbuecher.jsonl",
    "modulbeschreibungen.jsonl",
    "schulungsunterlagen.jsonl",
]

_ENC = tiktoken.get_encoding("cl100k_base")


def _load_jsonl(path: Path) -> list[dict]:
    """Liest eine JSONL-Datei und gibt eine Liste von Dicts zurück."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _estimate_tokens(chunks: list[dict]) -> int:
    """Schätzt die Gesamtzahl Tokens für eine Liste von Chunks."""
    return sum(len(_ENC.encode(c["text"])) for c in chunks)


def main() -> None:
    parser = argparse.ArgumentParser(description="V0-Indexierung: Gold → ChromaDB")
    parser.add_argument("--variant", default=VARIANT, help="Pipeline-Variante (v0|…)")
    parser.add_argument("--reset", action="store_true", help="Collection vor Indexierung löschen")
    parser.add_argument(
        "--max-chunks", type=int, default=None, metavar="N",
        help="Maximal N Chunks indexieren (für Smoke-Tests)",
    )
    args = parser.parse_args()
    variant = args.variant

    logger.info("=== V0-Indexierung gestartet (Variante: %s) ===", variant)
    t_start = time.monotonic()

    chunker = get_chunker(variant)

    # ── 1. Gold-JSONL laden und chunken ────────────────────────────────────────
    all_chunks: list[dict] = []
    source_stats: list[tuple[str, int, int]] = []  # (name, n_entries, n_chunks)

    for filename in GOLD_FILES:
        path = GOLD_DIR / filename
        if not path.exists():
            logger.warning("Gold-Datei fehlt, wird übersprungen: %s", path)
            continue

        entries = _load_jsonl(path)
        chunks = chunker(entries)
        all_chunks.extend(chunks)
        source_stats.append((filename, len(entries), len(chunks)))
        logger.info("  %-35s %4d Einträge → %5d Chunks", filename, len(entries), len(chunks))

    if not all_chunks:
        logger.error("Keine Chunks erzeugt – Abbruch.")
        sys.exit(1)

    if args.max_chunks is not None:
        all_chunks = all_chunks[: args.max_chunks]
        logger.info("--max-chunks: auf %d Chunks begrenzt.", len(all_chunks))

    logger.info("Total: %d Chunks aus %d Quellen", len(all_chunks), len(source_stats))

    # ── 2. Embeddings ──────────────────────────────────────────────────────────
    total_tokens = _estimate_tokens(all_chunks)
    cost_usd = total_tokens / 1_000_000 * 0.13
    logger.info(
        "Geschätzte Tokens: %d (~%.4f USD mit %s)",
        total_tokens, cost_usd, EMBEDDING_MODEL,
    )

    embeddings = embed_chunks(all_chunks)

    # ── 3. ChromaDB befüllen ───────────────────────────────────────────────────
    collection = get_or_create_collection(variant, reset=args.reset)
    add_chunks_to_collection(collection, all_chunks, embeddings)

    # ── 3b. BM25-Index für V2 ──────────────────────────────────────────────────
    if variant == "v2":
        from rag.config import V2_BM25_INDEX_PATH
        from rag.index.bm25_index import build_bm25_index

        build_bm25_index(all_chunks, V2_BM25_INDEX_PATH)
        logger.info("BM25-Index geschrieben: %s", V2_BM25_INDEX_PATH)

    # ── 4. Summary ─────────────────────────────────────────────────────────────
    duration = time.monotonic() - t_start
    logger.info("=== Indexierung abgeschlossen in %.1f s ===", duration)
    logger.info("Chunks pro Quelle:")
    for name, n_entries, n_chunks in source_stats:
        logger.info("  %-35s %4d Einträge → %5d Chunks", name, n_entries, n_chunks)
    logger.info("Total Chunks im Index: %d", collection.count())
    logger.info("Embedding-Kosten (geschätzt): %.4f USD", cost_usd)
    logger.info("Dauer: %.1f s (%.1f min)", duration, duration / 60)


if __name__ == "__main__":
    main()

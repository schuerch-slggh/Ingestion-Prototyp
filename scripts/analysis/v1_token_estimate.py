"""Pre-Flight: Schätzt Token-Anzahl und Embedding-Kosten für V1-Indexlauf.

Lädt Gold-JSONL, ruft V1-Chunker auf, summiert Tokens — ohne API-Calls.
Soll vor dem teuren Embedding-Lauf 02_index.py --variant v1 gerunnt werden.
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import tiktoken

from rag.config import GOLD_DIR
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
EMBEDDING_COST_PER_MTOK = 0.13  # text-embedding-3-large
COST_ABORT_THRESHOLD = 2.00


def main() -> None:
    chunker = get_chunker("v1")

    grand_total_chunks = 0
    grand_total_tokens = 0
    strategy_counter: Counter[str] = Counter()
    per_source_stats = []

    for filename in GOLD_FILES:
        path = GOLD_DIR / filename
        if not path.exists():
            logger.warning("Gold-Datei fehlt: %s", path)
            continue

        entries = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        chunks = chunker(entries)
        n_tokens = sum(len(_ENC.encode(c["text"])) for c in chunks)

        strats: Counter[str] = Counter(
            c["metadata"].get("chunking_strategy", "unknown") for c in chunks
        )
        strategy_counter.update(strats)

        per_source_stats.append(
            {
                "filename": filename,
                "n_entries": len(entries),
                "n_chunks": len(chunks),
                "n_tokens": n_tokens,
                "strategies": dict(strats),
            }
        )

        grand_total_chunks += len(chunks)
        grand_total_tokens += n_tokens

    estimated_cost = grand_total_tokens / 1_000_000 * EMBEDDING_COST_PER_MTOK

    logger.info("=== V1 Pre-Flight-Schätzung ===")
    logger.info("Pro Quelle:")
    for s in per_source_stats:
        logger.info(
            "  %-35s %5d Einträge → %6d Chunks (%d Tokens)",
            s["filename"],
            s["n_entries"],
            s["n_chunks"],
            s["n_tokens"],
        )
        logger.info("    Strategien: %s", s["strategies"])
    logger.info("---")
    logger.info("Total Chunks:           %d", grand_total_chunks)
    logger.info("Total Tokens:           %d", grand_total_tokens)
    logger.info("Strategie-Gesamt:       %s", dict(strategy_counter))
    logger.info("Geschätzte Kosten:      %.4f USD", estimated_cost)
    logger.info(
        "Vergleich V0:           11'789 Chunks, ~6.34M Tokens, ~0.82 USD"
    )

    if estimated_cost > COST_ABORT_THRESHOLD:
        logger.warning(
            "WARNUNG: Geschätzte Kosten %.4f USD > %.2f USD Schwellwert.",
            estimated_cost,
            COST_ABORT_THRESHOLD,
        )
        logger.warning(
            "Vor 02_index.py --variant v1 manuell prüfen, ob das plausibel ist."
        )
        sys.exit(1)

    logger.info(
        "Kosten OK (%.4f USD <= %.2f USD) – bereit für 02_index.py --variant v1",
        estimated_cost,
        COST_ABORT_THRESHOLD,
    )


if __name__ == "__main__":
    main()

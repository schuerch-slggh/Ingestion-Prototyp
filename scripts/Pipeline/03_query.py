"""Schritt 3 – Query: Frage stellen und Antwort generieren.

Aufruf:
    python scripts/Pipeline/03_query.py --query "Wie konfiguriere ich MwSt?"
    python scripts/Pipeline/03_query.py --query "..." --variant v0
    python scripts/Pipeline/03_query.py --query "..." --no-save
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import RUNS_DIR, VARIANT
from rag.generate.pipeline import answer_query

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _make_slug(query: str) -> str:
    """Erzeugt einen dateinamen-sicheren Slug aus der Query."""
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:30].strip("_")
    return slug or "query"


def main() -> None:
    parser = argparse.ArgumentParser(description="V0-Query: Retrieval + Generation")
    parser.add_argument("--query", required=True, help="Anfrage an die RAG-Pipeline")
    parser.add_argument("--variant", default=VARIANT, help="Pipeline-Variante (default: v0)")
    parser.add_argument("--no-save", action="store_true", help="Kein JSON-File schreiben")
    args = parser.parse_args()

    logger.info("=== Query-Pipeline gestartet (Variante: %s) ===", args.variant)
    logger.info("Frage: %s", args.query)

    result = answer_query(args.query, args.variant)

    # ── Konsolen-Ausgabe ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"FRAGE:  {result['query']}")
    print("=" * 70)
    print(f"\nANTWORT:\n{result['answer']}")
    print("\n" + "-" * 70)
    print(f"Abgerufene Chunks: {len(result['retrieved_chunks'])}  |  "
          f"Tokens: {result['metadata']['input_tokens']} in / "
          f"{result['metadata']['output_tokens']} out  |  "
          f"Dauer: {result['metadata']['duration_seconds']:.1f}s")
    print("=" * 70 + "\n")

    if not args.no_save:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = _make_slug(args.query)
        out_dir = RUNS_DIR / args.variant / "queries"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ts}_{slug}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Ergebnis gespeichert: %s", out_path)

    logger.info("=== Query-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

"""Schritt 3 – Query: Frage stellen und Antwort generieren.

Nimmt eine Benutzerfrage als Argument entgegen, führt Retrieval
und Generierung durch und speichert das Ergebnis.

Verwendung:
    python scripts/Pipeline/03_query.py [--variant v0] "Deine Frage hier"
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import RUNS_DIR, VARIANT, get_variant_index_dir
from rag.generate.pipeline import run_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schritt 3 – Query")
    parser.add_argument(
        "--variant",
        default=VARIANT,
        help="Pipeline-Variante (v0|v1|v2|v3). Standard: Umgebungsvariable VARIANT oder 'v0'.",
    )
    parser.add_argument("query", help="Frage an die RAG-Pipeline")
    args = parser.parse_args()

    logger.info("=== Query-Pipeline gestartet (Variante: %s) ===", args.variant)
    logger.info("Frage: %s", args.query)

    index_dir = get_variant_index_dir(args.variant)
    result = run_query(args.query, index_dir=index_dir)

    logger.info("Antwort: %s", result.get("answer", ""))

    runs_dir = RUNS_DIR / args.variant
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = runs_dir / f"query_{ts}.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Ergebnis gespeichert: %s", output_path)

    logger.info("=== Query-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

"""Schritt 3 – Query: Frage stellen und Antwort generieren.

Nimmt eine Benutzerfrage als CLI-Argument entgegen, führt Retrieval
und Generierung durch und gibt die Antwort aus.

Verwendung:
    python scripts/03_query.py "Deine Frage hier"
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.config import NAIVE_RAG_RUNS_DIR
from rag.generate.pipeline import run_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Bitte eine Frage als Argument übergeben.")
        sys.exit(1)

    query = sys.argv[1]
    logger.info("=== Query-Pipeline gestartet ===")
    logger.info("Frage: %s", query)

    # RAG-Query ausführen
    result = run_query(query)

    # Antwort ausgeben
    logger.info("Antwort: %s", result.get("answer", ""))

    # Ergebnis persistieren
    NAIVE_RAG_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = NAIVE_RAG_RUNS_DIR / f"query_{ts}.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Ergebnis gespeichert: %s", output_path)

    logger.info("=== Query-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

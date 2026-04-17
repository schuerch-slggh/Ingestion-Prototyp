"""Schritt 1 – Ingest: Rohdokumente einlesen und normalisieren.

Liest PDFs und CSVs aus data/raw/, normalisiert den Text und
schreibt die Ergebnisse nach data/processed/.
"""

import json
import logging
import sys

# Projekt-Root zum Pfad hinzufügen, damit src.rag importierbar ist
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.config import INTERIM_DIR, RAW_DIR
from rag.ingest.csv_loader import load_csvs
from rag.ingest.normalize import normalize_documents
from rag.ingest.pdf_loader import load_pdfs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Ingest-Pipeline gestartet ===")

    # 1. Rohdokumente laden
    documents: list[dict] = []
    documents.extend(load_pdfs(RAW_DIR))
    documents.extend(load_csvs(RAW_DIR))
    logger.info("Insgesamt %d Rohdokumente geladen", len(documents))

    # 2. Normalisieren
    normalized = normalize_documents(documents)
    logger.info("%d Dokumente normalisiert", len(normalized))

    # 3. Persistieren
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = INTERIM_DIR / "documents.json"
    output_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Normalisierte Dokumente gespeichert: %s", output_path)

    logger.info("=== Ingest-Pipeline abgeschlossen ===")


if __name__ == "__main__":
    main()

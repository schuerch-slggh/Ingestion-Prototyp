"""Schritt 1 – Ingest: Rohdokumente einlesen und normalisieren.

Liest PDFs und CSVs aus data/raw/, normalisiert den Text und
schreibt die Ergebnisse nach data/interim/ (variantenunabhängig).

Verwendung:
    python scripts/Pipeline/01_ingest.py [--variant v0]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import INTERIM_DIR, RAW_DIR, VARIANT
from rag.ingest.normalize import normalize_documents
from rag.pipeline_factory import get_loaders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schritt 1 – Ingest")
    parser.add_argument(
        "--variant",
        default=VARIANT,
        help="Pipeline-Variante (v0|v1|v2|v3). Standard: Umgebungsvariable VARIANT oder 'v0'.",
    )
    args = parser.parse_args()
    variant = args.variant

    logger.info("=== Ingest-Pipeline gestartet (Variante: %s) ===", variant)

    loaders = get_loaders(variant)

    # 1. Rohdokumente laden
    documents: list[dict] = []
    documents.extend(loaders["pdf"](RAW_DIR))
    documents.extend(loaders["csv"](RAW_DIR))
    logger.info("Insgesamt %d Rohdokumente geladen", len(documents))

    # 2. Normalisieren
    normalized = normalize_documents(documents)
    logger.info("%d Dokumente normalisiert", len(normalized))

    # 3. Persistieren (INTERIM_DIR ist variantenunabhängig)
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

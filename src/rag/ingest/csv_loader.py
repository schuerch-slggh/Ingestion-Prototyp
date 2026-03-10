"""CSV-Loader: Extrahiert Text aus CSV-Dateien.

Verantwortung:
- CSV-Dateien aus data/raw/ lesen
- Zeilen als Dokumente aufbereiten
- Ergebnis als Liste von Dokumenten zurückgeben
"""

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_csvs(input_dir: Path) -> list[dict]:
    """Liest alle CSVs aus *input_dir* und gibt pro Zeile ein Dokument zurück.

    Jede Zeile wird als Key-Value-Textdarstellung aufbereitet.
    """
    logger.info("CSV-Loader gestartet für %s", input_dir)
    documents: list[dict] = []

    csv_files = sorted(input_dir.glob("*.csv"))
    if not csv_files:
        logger.warning("Keine CSV-Dateien in %s gefunden", input_dir)
        return documents

    for csv_path in csv_files:
        logger.info("Lese CSV: %s", csv_path.name)
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                text = "\n".join(
                    f"{k}: {v}" for k, v in row.items() if v
                )
                if not text.strip():
                    continue
                documents.append({
                    "text": text,
                    "metadata": {
                        "source": str(csv_path),
                        "doc_id": f"{csv_path.stem}_row{row_num}",
                        "row": row_num,
                        "filename": csv_path.name,
                    },
                })

    logger.info(
        "%d Zeilen aus %d CSVs extrahiert",
        len(documents),
        len(csv_files),
    )
    return documents

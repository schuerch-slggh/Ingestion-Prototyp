"""Generischer JSONL-Writer für das Gold-Format."""

import json
import logging
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


def write_jsonl(records: Iterable[dict], target_path: Path) -> int:
    """Schreibt eine Sequenz von Dictionaries als JSONL nach *target_path*.

    Erstellt das Zielverzeichnis bei Bedarf. Gibt die Anzahl
    geschriebener Zeilen zurück.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with target_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    logger.info("JSONL geschrieben: %d Zeilen → %s", count, target_path)
    return count

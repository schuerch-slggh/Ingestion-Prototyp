"""Migration: erweitert data/eval/testset_v1.jsonl um ground_truth-Feld.

Liest die bestehende Test-Set-Datei, fügt pro Eintrag das Feld
`ground_truth` (leerer String) hinzu und schreibt das Ergebnis zurück.

Idempotent: Existierende Werte werden nicht überschrieben.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import TESTSET_PATH


def main() -> None:
    if not TESTSET_PATH.exists():
        print(f"FEHLER: {TESTSET_PATH} nicht vorhanden")
        sys.exit(1)

    entries = []
    with TESTSET_PATH.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    print(f"Geladen: {len(entries)} Einträge")

    migrated = 0
    for entry in entries:
        if "ground_truth" not in entry:
            entry["ground_truth"] = ""
            migrated += 1

    print(f"Migriert: {migrated} Einträge ergänzt um ground_truth-Feld")

    backup_path = TESTSET_PATH.with_suffix(".jsonl.backup")
    if not backup_path.exists():
        backup_path.write_text(
            TESTSET_PATH.read_text(encoding="utf-8"), encoding="utf-8"
        )
        print(f"Backup angelegt: {backup_path}")
    else:
        print(f"Backup bereits vorhanden: {backup_path}")

    with TESTSET_PATH.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Geschrieben: {TESTSET_PATH}")


if __name__ == "__main__":
    main()

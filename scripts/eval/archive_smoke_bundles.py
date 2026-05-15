"""Archiviert bestehende Smoke-Eval-Bundles vor dem Vollauf.

Verschiebt alle Dateien aus runs/eval/v0-v4/ nach
runs/eval/archive/<datum>_smoke/<variante>/.
"""

import shutil
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path("runs/eval")
ARCHIVE_DIR = EVAL_DIR / "archive" / f"{datetime.now():%Y-%m-%d}_smoke"


def archive_bundles() -> None:
    """Verschiebt Smoke-Bundles aller Varianten ins Archiv."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    for variant in ["v0", "v1", "v2", "v3", "v4"]:
        variant_dir = EVAL_DIR / variant
        if not variant_dir.exists():
            continue
        target = ARCHIVE_DIR / variant
        target.mkdir(parents=True, exist_ok=True)
        for f in variant_dir.glob("*"):
            if f.is_file():
                shutil.move(str(f), str(target / f.name))
                moved_count += 1
    print(f"Archiviert: {moved_count} Dateien nach {ARCHIVE_DIR}")


if __name__ == "__main__":
    archive_bundles()

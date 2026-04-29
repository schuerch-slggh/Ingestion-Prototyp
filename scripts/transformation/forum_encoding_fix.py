"""Zeichensatz-Korrektur für Forum_Export.csv.

Das CSV wurde mit falschem Encoding exportiert: UTF-8-Bytes wurden als
Latin-1 interpretiert, sodass Umlaute (ö → Ã¶, ü → Ã¼, ä → Ã¤ usw.)
korrumpiert sind.

Vorgehen:
  1. Datei als Latin-1 einlesen  →  die Bytes sind jetzt korrekte UTF-8-Bytes,
     aber in einem latin-1-String gespeichert.
  2. String zurück zu Bytes (latin-1)  →  echte UTF-8-Byte-Sequenzen.
  3. Bytes als UTF-8 dekodieren  →  korrekte Unicode-Zeichen.
  4. Korrigierte Datei in data/interim/ speichern.
"""

import logging
import sys
from pathlib import Path

# Projektroot ermitteln (zwei Ebenen über diesem Skript: data/ → Prototyp Alpha/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag.config import INTERIM_DIR, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCE: Path = RAW_DIR / "Forum_Export.csv"
TARGET: Path = INTERIM_DIR / "Forum_Export_fixed.csv"


def fix_encoding(source: Path, target: Path) -> None:
    """Liest *source* als Latin-1, dekodiert die Bytes als UTF-8 und
    schreibt das Ergebnis nach *target*.

    Args:
        source: Pfad zur korrumpierten CSV-Datei.
        target: Pfad für die korrigierte Ausgabedatei.
    """
    logger.info("Lese Quelldatei: %s", source)
    raw_text = source.read_text(encoding="latin-1")

    # Latin-1-Bytes → echte UTF-8-Bytes → korrekter Unicode-String
    fixed_text = raw_text.encode("latin-1").decode("utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(fixed_text, encoding="utf-8")
    logger.info("Korrigierte Datei gespeichert: %s", target)


if __name__ == "__main__":
    fix_encoding(SOURCE, TARGET)

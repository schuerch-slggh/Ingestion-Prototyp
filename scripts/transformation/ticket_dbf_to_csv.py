"""Wrapper für die Rückwärtskompatibilität.

Die eigentliche DBF-Lese-Logik liegt in src/rag/preparation/dbf_reader.py.
Dieses Skript schreibt das Ergebnis als CSV nach data/silver/.
"""

from pathlib import Path

from rag.config import RAW_DIR, INTERIM_DIR
from rag.preparation.dbf_reader import read_dbf


def main() -> None:
    df, stats = read_dbf(RAW_DIR / "vorgaenge.dbf", RAW_DIR / "vorgaenge.dbt")
    target = INTERIM_DIR / "vorgaenge.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()

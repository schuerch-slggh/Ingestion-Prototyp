"""Forum-Datenaufbereitung: Bronze → Silver → Gold.

Aufruf:
    python scripts/Pipeline/00_prepare_forum.py
    python scripts/Pipeline/00_prepare_forum.py --sample 100
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import INTERIM_DIR, PROCESSED_DIR, RAW_DIR
from rag.preparation.forum import clean_to_silver, load_bronze, transform_to_gold
from rag.preparation.jsonl_writer import write_jsonl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SOURCE = RAW_DIR / "forum" / "forum.csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forum-Datenaufbereitung Bronze → Silver → Gold"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Verarbeite nur eine Stichprobe von N Beiträgen.",
    )
    args = parser.parse_args()

    suffix = "_sample" if args.sample else ""
    silver_path = INTERIM_DIR / f"forum{suffix}.csv"
    gold_path = PROCESSED_DIR / f"forum{suffix}.jsonl"

    logger.info("=== Forum-Aufbereitung gestartet ===")
    logger.info("Quelle: %s", SOURCE)
    if args.sample:
        logger.info("Stichprobengrösse: %d", args.sample)

    # Bronze laden
    df_bronze = load_bronze(SOURCE, sample_size=args.sample)

    # Silver bereinigen und persistieren
    df_silver = clean_to_silver(df_bronze)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df_silver.to_csv(silver_path, index=False, encoding="utf-8")
    logger.info("Silver gespeichert: %s", silver_path)

    # Gold erzeugen und persistieren
    records = transform_to_gold(df_silver)
    count = write_jsonl(records, gold_path)

    logger.info("=== Forum-Aufbereitung abgeschlossen ===")
    logger.info("  Bronze:  %d Beiträge geladen", len(df_bronze))
    logger.info("  Silver:  %d Beiträge nach Bereinigung", len(df_silver))
    logger.info("  Gold:    %d Datensätze → %s", count, gold_path)


if __name__ == "__main__":
    main()

"""Ticket-Datenaufbereitung: Bronze → Silver → Gold.

Aufruf:
    python scripts/Pipeline/00_prepare_tickets.py
    python scripts/Pipeline/00_prepare_tickets.py --sample 100
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import GOLD_DIR, INTERIM_DIR, RAW_DIR
from rag.preparation.jsonl_writer import write_jsonl
from rag.preparation.tickets import clean_to_silver, load_bronze, transform_to_gold

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket Bronze → Silver → Gold")
    parser.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Reproduzierbare Stichprobe von N Tickets verarbeiten",
    )
    args = parser.parse_args()

    suffix = f"_sample" if args.sample else ""

    # Bronze laden
    bronze_df = load_bronze(
        RAW_DIR / "helpdesk" / "vorgaenge.dbf",
        RAW_DIR / "helpdesk" / "vorgaenge.dbt",
        sample_size=args.sample,
    )
    logger.info("Bronze: %d Tickets geladen", len(bronze_df))

    # Silver
    silver_df = clean_to_silver(bronze_df)
    silver_path = INTERIM_DIR / f"tickets{suffix}.csv"
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    silver_df.to_csv(silver_path, index=False, encoding="utf-8")
    logger.info("Silver geschrieben: %s (%d Zeilen)", silver_path, len(silver_df))

    # Gold
    gold_records = transform_to_gold(silver_df)
    gold_path = GOLD_DIR / f"tickets{suffix}.jsonl"
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(gold_records, gold_path)
    logger.info("Gold geschrieben: %s (%d Records)", gold_path, len(gold_records))

    logger.info(
        "Summary: %d Bronze → %d Silver → %d Gold",
        len(bronze_df),
        len(silver_df),
        len(gold_records),
    )


if __name__ == "__main__":
    main()

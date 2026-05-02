"""Modulbeschreibungen-Datenaufbereitung: Bronze → Silver → Gold.

Aufruf:
    python scripts/Pipeline/00_prepare_modulbeschreibungen.py
    python scripts/Pipeline/00_prepare_modulbeschreibungen.py --sample 3
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import GOLD_DIR, INTERIM_DIR, RAW_DIR
from rag.preparation.jsonl_writer import write_jsonl
from rag.preparation.modulbeschreibungen import (
    clean_to_silver,
    load_bronze,
    transform_to_gold,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODULBESCHREIBUNGEN_DIR = RAW_DIR / "modulbeschreibungen"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modulbeschreibungen Bronze → Silver → Gold"
    )
    parser.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help="Nur N Dokumente verarbeiten (reproduzierbare Stichprobe)",
    )
    args = parser.parse_args()

    suffix = "_sample" if args.sample else ""

    # Bronze laden
    documents = load_bronze(MODULBESCHREIBUNGEN_DIR, sample_size=args.sample)
    if not documents:
        logger.error("Keine Dokumente geladen – Abbruch.")
        sys.exit(1)
    logger.info("Bronze: %d Dokumente geladen", len(documents))

    # Silver
    silver_df = clean_to_silver(documents)
    silver_path = INTERIM_DIR / f"modulbeschreibungen{suffix}.csv"
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    silver_df.drop(columns=["outline_json", "pages_json", "images_json"]).to_csv(
        silver_path, index=False, encoding="utf-8"
    )
    logger.info("Silver geschrieben: %s (%d Zeilen)", silver_path, len(silver_df))

    # Gold
    gold_records = transform_to_gold(silver_df)
    gold_path = GOLD_DIR / f"modulbeschreibungen{suffix}.jsonl"
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(gold_records, gold_path)
    logger.info("Gold geschrieben: %s (%d Records)", gold_path, len(gold_records))

    total_images = sum(len(r["images"]) for r in gold_records)
    total_pages = sum(r["metadata"]["page_count"] for r in gold_records)
    docs_with_outline = sum(
        1 for r in gold_records if r["content"]["outline"]
    )
    logger.info(
        "Summary: %d Dokumente, %d Seiten, %d Bilder, %d/%d mit Outline",
        len(gold_records),
        total_pages,
        total_images,
        docs_with_outline,
        len(gold_records),
    )


if __name__ == "__main__":
    main()

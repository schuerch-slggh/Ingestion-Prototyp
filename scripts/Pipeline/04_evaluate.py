"""Schritt 4 – Evaluate: Pipeline über das Test-Set ausführen und Bundle persistieren.

Aufruf:
    python scripts/Pipeline/04_evaluate.py
    python scripts/Pipeline/04_evaluate.py --variant v0
    python scripts/Pipeline/04_evaluate.py --dry-run
    python scripts/Pipeline/04_evaluate.py --dry-run --verbose
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import EVAL_RUNS_DIR, VARIANT
from rag.evaluate import runner
from rag.evaluate.testset import load_testset

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluation-Runner: Pipeline über Test-Set ausführen"
    )
    parser.add_argument(
        "--variant", default=VARIANT, help="Pipeline-Variante (default: v0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur 5 stratifizierte Fragen ausführen (Smoke-Test)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="DEBUG-Logging aktivieren"
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    logger.info(
        "=== Evaluation-Runner gestartet (Variante: %s%s) ===",
        args.variant,
        ", dry-run" if args.dry_run else "",
    )

    questions = load_testset()
    logger.info("Test-Set geladen: %d Fragen", len(questions))

    if args.dry_run:
        questions = runner._select_dry_run_subset(questions)
        logger.info("Dry-Run: %d Fragen selektiert", len(questions))

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    output_path = EVAL_RUNS_DIR / args.variant / f"responses_{ts}.jsonl"

    bundle_path = runner.run_testset(questions, args.variant, output_path)
    logger.info("Bundle geschrieben: %s", bundle_path)
    logger.info("=== Evaluation-Runner abgeschlossen ===")


if __name__ == "__main__":
    main()

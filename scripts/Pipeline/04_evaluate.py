"""Schritt 4 – Evaluate: Runner, Scorer und Reporter für eine Pipeline-Variante.

Aufruf:
    python scripts/Pipeline/04_evaluate.py                       # Runner (V0)
    python scripts/Pipeline/04_evaluate.py --variant v0          # Runner explizit
    python scripts/Pipeline/04_evaluate.py --dry-run             # Runner Dry-Run
    python scripts/Pipeline/04_evaluate.py --score               # Score neuestes Bundle
    python scripts/Pipeline/04_evaluate.py --score --bundle PATH  # Score spezif. Bundle
    python scripts/Pipeline/04_evaluate.py --variant v0 --score  # Runner + Score
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import EVAL_RUNS_DIR, VARIANT
from rag.evaluate import runner
from rag.evaluate.reporter import build_summary, write_markdown
from rag.evaluate.scorer import score_bundle
from rag.evaluate.testset import load_testset

logger = logging.getLogger(__name__)


def _find_latest_bundle(variant: str) -> Path:
    """Findet das neueste responses_*.jsonl in runs/eval/<variant>/.

    Returns:
        Pfad zum neuesten Bundle.

    Raises:
        FileNotFoundError: Wenn kein Bundle existiert.
    """
    bundle_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(bundle_dir.glob("responses_*.jsonl"))
    if not bundles:
        raise FileNotFoundError(
            f"Kein Bundle in {bundle_dir} gefunden. "
            "Bitte zuerst den Runner ausführen."
        )
    return bundles[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluation: Runner, Scorer und Reporter für eine Variante"
    )
    parser.add_argument(
        "--variant", default=VARIANT, help="Pipeline-Variante (default: v0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur 5 stratifizierte Fragen (Smoke-Test); schliesst --no-runner aus",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Scorer und Reporter auf Bundle ausführen",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Spezifisches Bundle-File scoren (impliziert --score)",
    )
    parser.add_argument(
        "--no-runner",
        action="store_true",
        help="Runner überspringen, nur Scorer auf bestehendem Bundle",
    )
    parser.add_argument(
        "--question-ids",
        type=str,
        default=None,
        help="Komma-getrennte Frage-IDs, die das Dry-Run-Subset überschreiben "
             "(z. B. --question-ids Q036,Q042,Q001,Q002). "
             "Nur gültig mit --dry-run.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="DEBUG-Logging aktivieren"
    )
    args = parser.parse_args()

    if args.dry_run and args.no_runner:
        parser.error("--dry-run und --no-runner schliessen sich gegenseitig aus.")

    if args.bundle:
        args.score = True
        args.no_runner = True  # --bundle impliziert: Runner überspringen

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    logger.info("=== Evaluation gestartet (Variante: %s) ===", args.variant)

    bundle_path: Path | None = None

    # ── Runner-Phase ──────────────────────────────────────────────────────────
    if not args.no_runner:
        questions = load_testset()
        logger.info("Test-Set geladen: %d Fragen", len(questions))

        if args.dry_run:
            override_ids = (
                [qid.strip() for qid in args.question_ids.split(",")]
                if args.question_ids
                else None
            )
            questions = runner._select_dry_run_subset(questions, override_ids)
            logger.info("Dry-Run: %d Fragen selektiert", len(questions))

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        output_path = EVAL_RUNS_DIR / args.variant / f"responses_{ts}.jsonl"
        bundle_path = runner.run_testset(questions, args.variant, output_path)
        logger.info("Bundle geschrieben: %s", bundle_path)

    # ── Score-Phase ───────────────────────────────────────────────────────────
    if args.score or args.no_runner:
        if args.bundle:
            bundle_path = args.bundle
        elif bundle_path is None:
            bundle_path = _find_latest_bundle(args.variant)

        bundle_ts = bundle_path.stem.replace("responses_", "")
        scores_path = bundle_path.parent / f"ragas_{bundle_ts}.json"
        summary_path = bundle_path.parent / f"summary_{bundle_ts}.md"

        logger.info("Scoring Bundle: %s", bundle_path)
        score_bundle(bundle_path, scores_path)

        summary = build_summary(scores_path, args.variant)
        write_markdown(summary, summary_path)

        logger.info("Scores:   %s", scores_path)
        logger.info("Summary:  %s", summary_path)

    logger.info("=== Evaluation abgeschlossen ===")


if __name__ == "__main__":
    main()

"""Schritt 4 – Evaluate: RAG-Pipeline mit RAGAS evaluieren.

Führt die Evaluation durch und speichert die Ergebnisse
in variantenspezifischen Unterordnern.

Verwendung:
    python scripts/Pipeline/04_evaluate.py [--variant v0]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import EVAL_DIR, RUNS_DIR, VARIANT, get_variant_index_dir
from rag.evaluate.ragas_eval import run_evaluation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schritt 4 – Evaluate")
    parser.add_argument(
        "--variant",
        default=VARIANT,
        help="Pipeline-Variante (v0|v1|v2|v3). Standard: Umgebungsvariable VARIANT oder 'v0'.",
    )
    args = parser.parse_args()

    logger.info("=== Evaluation gestartet (Variante: %s) ===", args.variant)

    # Testdatensatz ist variantenunabhängig
    test_dataset_path = EVAL_DIR / "test_dataset.json"

    if not test_dataset_path.exists():
        logger.error(
            "Testdatensatz nicht gefunden: %s. "
            "Bitte zuerst einen Testdatensatz anlegen.",
            test_dataset_path,
        )
        sys.exit(1)

    index_dir = get_variant_index_dir(args.variant)
    eval_runs_dir = RUNS_DIR / "eval" / args.variant
    eval_runs_dir.mkdir(parents=True, exist_ok=True)
    metrics = run_evaluation(test_dataset_path, eval_runs_dir, index_dir=index_dir)
    logger.info("Evaluation abgeschlossen. Metriken: %s", metrics)

    logger.info("=== Evaluation abgeschlossen ===")


if __name__ == "__main__":
    main()

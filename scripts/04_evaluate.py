"""Schritt 4 – Evaluate: RAG-Pipeline mit RAGAS evaluieren.

Führt die Evaluation durch und speichert die Ergebnisse
in data/eval/ und runs/eval/.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.config import EVAL_DIR, EVAL_RUNS_DIR
from rag.evaluate.ragas_eval import run_evaluation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== Evaluation gestartet ===")

    # Testdatensatz – Pfad kann später angepasst werden
    test_dataset_path = EVAL_DIR / "test_dataset.json"

    if not test_dataset_path.exists():
        logger.error(
            "Testdatensatz nicht gefunden: %s. "
            "Bitte zuerst einen Testdatensatz anlegen.",
            test_dataset_path,
        )
        sys.exit(1)

    EVAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    metrics = run_evaluation(test_dataset_path, EVAL_RUNS_DIR)
    logger.info("Evaluation abgeschlossen. Metriken: %s", metrics)

    logger.info("=== Evaluation abgeschlossen ===")


if __name__ == "__main__":
    main()

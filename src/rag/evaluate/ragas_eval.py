"""RAGAS-Evaluation: Bewertet die RAG-Pipeline mit dem RAGAS-Framework.

Verantwortung:
- Testdatensatz laden (Fragen + erwartete Antworten)
- Pipeline für jede Frage ausführen
- RAGAS-Metriken berechnen (Faithfulness, Answer Relevancy, …)
- Ergebnisse in data/eval/ und runs/eval/ schreiben
"""

import json
import logging
from pathlib import Path

from rag.generate.pipeline import run_query

logger = logging.getLogger(__name__)


def run_evaluation(
    test_dataset_path: Path,
    output_dir: Path,
) -> dict:
    """Führt Queries aus dem Testdatensatz aus und speichert Ergebnisse
    im RAGAS-kompatiblen Format für spätere Evaluation.

    Testdatensatz-Format:
    [{"question": "...", "ground_truth": "..."}, ...]
    """
    logger.info(
        "Starte Evaluation mit Testdaten aus %s", test_dataset_path
    )

    test_data = json.loads(
        test_dataset_path.read_text(encoding="utf-8")
    )
    logger.info("%d Testfragen geladen", len(test_data))

    results: list[dict] = []
    for i, item in enumerate(test_data, start=1):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")

        logger.info(
            "Frage %d/%d: %s", i, len(test_data), question[:80]
        )
        result = run_query(question)

        results.append({
            "question": question,
            "answer": result["answer"],
            "contexts": result["contexts"],
            "ground_truth": ground_truth,
            "retrieved_chunks": result["retrieved_chunks"],
        })

    # Ergebnisse speichern
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "eval_results.json"
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Evaluationsergebnisse gespeichert: %s", output_path)

    return {
        "num_questions": len(results),
        "output_path": str(output_path),
        "note": "RAGAS-Metriken werden im nächsten Schritt berechnet.",
    }

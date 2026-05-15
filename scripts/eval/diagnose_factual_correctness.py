"""Diagnostischer Mini-Lauf: 3 Fragen mit FactualCorrectness, sequenziell.

Zweck: Bestätigen, dass FactualCorrectness mit den aktuellen Bundles
funktioniert, bevor der Vollauf-Rescore startet.
"""

import json
import logging
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import FactualCorrectness

from rag.config import (
    EVAL_RUNS_DIR,
    OPENAI_API_KEY,
    RAGAS_JUDGE_MODEL,
    RAGAS_JUDGE_SEED,
    RAGAS_JUDGE_TEMPERATURE,
)
from rag.evaluate.testset import load_testset

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    v0_dir = EVAL_RUNS_DIR / "v0"
    bundles = sorted(v0_dir.glob("responses_*.jsonl"))
    if not bundles:
        logger.error("Kein V0-Bundle gefunden in %s", v0_dir)
        sys.exit(1)
    bundle_path = bundles[-1]
    logger.info("Verwende Bundle: %s", bundle_path)

    with bundle_path.open(encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]

    questions = load_testset()
    gt_by_id = {q.id: q.ground_truth for q in questions}

    valid_entries = [
        e for e in entries
        if e.get("error") is None and gt_by_id.get(e["question_id"], "").strip()
    ][:3]

    if len(valid_entries) < 3:
        logger.error("Zu wenige Einträge mit Ground-Truth: %d/3", len(valid_entries))
        sys.exit(1)

    logger.info("Diagnostischer Lauf: %d Fragen", len(valid_entries))

    samples = []
    for entry in valid_entries:
        result = entry["result"]
        gt = gt_by_id[entry["question_id"]]
        samples.append(
            SingleTurnSample(
                user_input=result["query"],
                response=result["answer"],
                retrieved_contexts=[c["text"] for c in result["retrieved_chunks"]],
                reference=gt,
            )
        )
        logger.info(
            "  %s: Ref-Länge=%d, Antw-Länge=%d",
            entry["question_id"],
            len(gt),
            len(result["answer"]),
        )

    dataset = EvaluationDataset(samples=samples)

    llm = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL,
        temperature=RAGAS_JUDGE_TEMPERATURE,
        seed=RAGAS_JUDGE_SEED,
        api_key=OPENAI_API_KEY,
        timeout=120.0,
        max_retries=3,
    )
    judge = LangchainLLMWrapper(llm)

    run_config = RunConfig(
        timeout=300,
        max_workers=1,
        max_retries=5,
        log_tenacity=True,
    )

    logger.info("Starte FactualCorrectness-Scoring sequenziell (max_workers=1)...")
    result = evaluate(
        dataset=dataset,
        metrics=[FactualCorrectness(llm=judge)],
        run_config=run_config,
        raise_exceptions=False,
        show_progress=True,
    )

    df = result.to_pandas()
    logger.info("Verfügbare Spalten: %s", list(df.columns))

    # Spaltenname robust ermitteln
    fc_col = next(
        (c for c in df.columns if "factual_correctness" in c.lower()), None
    )

    valid_scores = []
    for i, entry in enumerate(valid_entries):
        score = df[fc_col].iloc[i] if fc_col and i < len(df) else None
        try:
            score = None if score is None or math.isnan(float(score)) else float(score)
        except (TypeError, ValueError):
            score = None
        logger.info("  %s: %s", entry["question_id"], score)
        if score is not None:
            valid_scores.append(score)

    logger.info(
        "DIAGNOSE-ERGEBNIS: %d/%d Scores erfolgreich (Spalte: %s)",
        len(valid_scores),
        len(valid_entries),
        fc_col,
    )

    if len(valid_scores) == len(valid_entries):
        logger.info("→ FactualCorrectness funktioniert. Vollauf-Rescore kann starten.")
    elif len(valid_scores) > 0:
        logger.warning(
            "→ FactualCorrectness teilweise erfolgreich (%d/%d). "
            "Vollauf-Rescore möglich, aber mit Vorsicht.",
            len(valid_scores),
            len(valid_entries),
        )
    else:
        logger.error(
            "→ FactualCorrectness komplett gescheitert. "
            "Stoppe vor Vollauf-Rescore und prüfe Logs."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()

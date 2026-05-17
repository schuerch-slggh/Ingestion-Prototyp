"""Diagnose der RAGAS-Scoring-Ausfälle: Reproduktion mit Debug-Output.

Lädt drei ausgewählte Antworten aus dem V0-Bundle, scort sie einzeln
mit Faithfulness und LLMContextRecall und protokolliert die Zwischen-
ergebnisse, um die Ursache der NaN-Werte zu identifizieren.

Test-Fälle:
- Q005: strukturierte Antwort mittlerer Länge
- Q006: sehr lange strukturierte Antwort
- Q020: kurze Hedging-Antwort (Referenz)
"""

import json
import logging
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextRecall

from rag.config import (
    EVAL_RUNS_DIR,
    OPENAI_API_KEY,
    RAGAS_JUDGE_MODEL,
    RAGAS_JUDGE_SEED,
    RAGAS_JUDGE_TEMPERATURE,
)
from rag.evaluate.testset import load_testset

# Verbose Logging für RAGAS und LangChain
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Test-Fälle: question_id → Variante
TEST_CASES = [
    ("Q005", "v0", "Strukturierte mittellange Antwort"),
    ("Q006", "v0", "Sehr lange strukturierte Antwort"),
    ("Q020", "v0", "Kurze Hedging-Antwort (Referenz)"),
]


def _load_bundle(variant: str) -> dict[str, dict]:
    """Lädt jüngstes Bundle der Variante als Dict qid → entry."""
    variant_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(variant_dir.glob("responses_*.jsonl"))
    if not bundles:
        raise FileNotFoundError(f"Kein Bundle in {variant_dir}")
    out = {}
    with bundles[-1].open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                entry = json.loads(line)
                out[entry["question_id"]] = entry
    return out


def _build_judge() -> LangchainLLMWrapper:
    """Erstellt Judge-LLM mit erhöhtem Timeout und Logging."""
    llm = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL,
        temperature=RAGAS_JUDGE_TEMPERATURE,
        seed=RAGAS_JUDGE_SEED,
        api_key=OPENAI_API_KEY,
        timeout=180.0,
        max_retries=2,
    )
    return LangchainLLMWrapper(llm)


def diagnose_case(
    qid: str,
    variant: str,
    description: str,
    questions_by_id: dict,
    judge: LangchainLLMWrapper,
) -> None:
    """Diagnose eines Test-Falls: Score erneut und protokolliere alle Details."""
    print("\n" + "=" * 80)
    print(f"DIAGNOSE: {qid} / {variant.upper()} – {description}")
    print("=" * 80)

    bundle = _load_bundle(variant)
    entry = bundle.get(qid)
    if entry is None:
        print(f"FEHLER: {qid} nicht im Bundle gefunden")
        return

    if entry.get("error") is not None:
        print(f"FEHLER: Bundle-Eintrag hat error: {entry['error']}")
        return

    result = entry["result"]
    q_meta = questions_by_id.get(qid)
    if q_meta is None:
        print(f"FEHLER: {qid} nicht im Testset")
        return

    print(f"\n--- INPUTS ---")
    print(f"Frage: {result['query']}")
    print(f"Antwort-Länge: {len(result['answer'])} Zeichen")
    print(f"Antwort (vollständig):\n{result['answer']}")
    print(f"\nAnzahl retrieved Chunks: {len(result['retrieved_chunks'])}")
    print(f"Ground-Truth-Länge: {len(q_meta.ground_truth)} Zeichen")
    print(f"Ground-Truth (vollständig):\n{q_meta.ground_truth}")

    sample = SingleTurnSample(
        user_input=result["query"],
        response=result["answer"],
        retrieved_contexts=[c["text"] for c in result["retrieved_chunks"]],
        reference=q_meta.ground_truth,
    )

    run_config = RunConfig(
        timeout=300, max_workers=1, max_retries=3, log_tenacity=True
    )

    print(f"\n--- FAITHFULNESS-SCORING ---")
    try:
        dataset = EvaluationDataset(samples=[sample])
        ragas_result = evaluate(
            dataset=dataset,
            metrics=[Faithfulness(llm=judge)],
            run_config=run_config,
            raise_exceptions=False,
            show_progress=False,
        )
        df = ragas_result.to_pandas()
        print(f"Faithfulness-Wert: {df['faithfulness'].iloc[0]}")
        print(f"DataFrame-Spalten: {list(df.columns)}")
        print(f"Volltext-Output:\n{df.to_dict(orient='records')}")
    except Exception as exc:
        print(f"FEHLER bei Faithfulness: {exc}")
        traceback.print_exc()

    print(f"\n--- LLM-CONTEXT-RECALL-SCORING ---")
    try:
        dataset = EvaluationDataset(samples=[sample])
        ragas_result = evaluate(
            dataset=dataset,
            metrics=[LLMContextRecall(llm=judge)],
            run_config=run_config,
            raise_exceptions=False,
            show_progress=False,
        )
        df = ragas_result.to_pandas()
        col = next(
            (c for c in df.columns if "context_recall" in c.lower()), None
        )
        if col:
            print(f"LLMContextRecall-Wert ({col}): {df[col].iloc[0]}")
        else:
            print(f"Keine context_recall-Spalte. Spalten: {list(df.columns)}")
        print(f"Volltext-Output:\n{df.to_dict(orient='records')}")
    except Exception as exc:
        print(f"FEHLER bei LLMContextRecall: {exc}")
        traceback.print_exc()


def main() -> None:
    questions = load_testset()
    questions_by_id = {q.id: q for q in questions}

    judge = _build_judge()

    for qid, variant, description in TEST_CASES:
        try:
            diagnose_case(qid, variant, description, questions_by_id, judge)
        except Exception as exc:
            logger.error("Test-Fall %s fehlgeschlagen: %s", qid, exc)
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("DIAGNOSE ABGESCHLOSSEN")
    print("=" * 80)


if __name__ == "__main__":
    main()

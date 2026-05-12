"""Scorer: Berechnet RAGAS-Metriken auf einem Response-Bundle."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ragas import EvaluationDataset, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    FactualCorrectness,
    Faithfulness,
    LLMContextRecall,
    ResponseRelevancy,
)

from rag.config import (
    OPENAI_API_KEY,
    RAGAS_JUDGE_MODEL,
    RAGAS_JUDGE_SEED,
    RAGAS_JUDGE_TEMPERATURE,
)
from rag.evaluate.testset import load_testset

logger = logging.getLogger(__name__)

# Stand Mai 2026 (https://openai.com/api/pricing/)
GPT_4O_INPUT_COST_PER_MTOK: float = 2.50   # USD pro 1M Input-Tokens
GPT_4O_OUTPUT_COST_PER_MTOK: float = 10.00  # USD pro 1M Output-Tokens

# Interne Metrik-Schlüssel (RAGAS 0.2 DataFrame-Spaltennamen)
_COL_FAITHFULNESS = "faithfulness"
_COL_ANSWER_RELEVANCE = "answer_relevancy"
_COL_CONTEXT_RECALL = "context_recall"
_COL_FACTUAL_CORRECTNESS = "factual_correctness"


@dataclass
class RagasScores:
    """RAGAS-Scores für eine einzelne Frage."""

    question_id: str
    category: str
    faithfulness: float | None
    answer_relevance: float | None
    context_recall: float | None
    factual_correctness: float | None


def score_bundle(
    bundle_path: Path,
    output_path: Path,
    judge_model: str | None = None,
) -> Path:
    """Berechnet RAGAS-Scores für alle Einträge eines Bundles.

    Lädt das Bundle, filtert Einträge mit error != null heraus, baut
    ein RAGAS-EvaluationDataset mit Ground-Truth-Referenzen aus dem
    Test-Set, ruft ragas.evaluate() auf und persistiert die Scores.

    Args:
        bundle_path: Pfad zu responses_<ts>.jsonl.
        output_path: Pfad zur Output-JSON (typischerweise ragas_<ts>.json).
        judge_model: OpenAI-Modell für RAGAS-Bewertung. Falls None,
                     wird RAGAS_JUDGE_MODEL aus config.py verwendet.

    Returns:
        Pfad zur erzeugten ragas_<ts>.json.

    Raises:
        FileNotFoundError: Bundle nicht vorhanden.
        ValueError: Bundle ist leer oder enthält nur Fehler-Einträge.
    """
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle nicht gefunden: {bundle_path}")

    model = judge_model or RAGAS_JUDGE_MODEL

    all_entries = _load_bundle(bundle_path)
    n_total = len(all_entries)
    valid_entries = [e for e in all_entries if e.get("error") is None]
    n_skipped = n_total - len(valid_entries)

    if not valid_entries:
        raise ValueError(
            f"Bundle enthält keine erfolgreichen Einträge "
            f"(total={n_total}, Fehler={n_skipped}): {bundle_path}"
        )

    logger.info(
        "Scoring: %d/%d Einträge (übersprungen: %d Fehler)",
        len(valid_entries),
        n_total,
        n_skipped,
    )

    # Ground-Truth-Lookup aus Test-Set
    questions = load_testset()
    ground_truth_by_id = {q.id: q.ground_truth for q in questions}

    n_with_gt = sum(
        1
        for e in valid_entries
        if ground_truth_by_id.get(e["question_id"], "").strip()
    )
    n_without_gt = len(valid_entries) - n_with_gt

    if n_without_gt > 0:
        logger.warning(
            "%d von %d Einträgen haben kein ground_truth gesetzt. "
            "Referenz-gestützte Metriken (LLMContextRecall, FactualCorrectness) "
            "werden für diese Einträge als None gespeichert.",
            n_without_gt,
            len(valid_entries),
        )

    dataset = _build_ragas_dataset(valid_entries, ground_truth_by_id)
    judge = _configure_judge(model)
    metrics = [
        Faithfulness(llm=judge),
        ResponseRelevancy(llm=judge),
        LLMContextRecall(llm=judge),
        FactualCorrectness(llm=judge),
    ]

    ragas_result = evaluate(
        dataset=dataset,
        metrics=metrics,
        raise_exceptions=False,
        show_progress=True,
    )

    scores = _extract_scores(ragas_result, valid_entries)
    output_path = _persist_scores(
        scores, output_path, bundle_path, model, n_skipped, n_with_gt
    )

    def _safe_mean(vals: list) -> str:
        nums = [v for v in vals if v is not None]
        return f"{sum(nums)/len(nums):.3f}" if nums else "–"

    logger.info(
        "RAGAS-Mittelwerte: faithfulness=%s | answer_relevance=%s | "
        "context_recall=%s | factual_correctness=%s",
        _safe_mean([s.faithfulness for s in scores]),
        _safe_mean([s.answer_relevance for s in scores]),
        _safe_mean([s.context_recall for s in scores]),
        _safe_mean([s.factual_correctness for s in scores]),
    )
    return output_path


def _load_bundle(bundle_path: Path) -> list[dict]:
    """Liest alle Zeilen aus dem JSONL-Bundle."""
    entries = []
    with bundle_path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def _build_ragas_dataset(
    bundle_entries: list[dict],
    ground_truth_by_id: dict[str, str],
) -> EvaluationDataset:
    """Konvertiert Bundle-Einträge in RAGAS EvaluationDataset.

    RAGAS 0.2 erwartet SingleTurnSample mit:
        user_input:         die Frage
        response:           die generierte Antwort
        retrieved_contexts: Liste der Kontext-Strings (nur text)
        reference:          Ground-Truth-Antwort (leer falls nicht vorhanden)

    Args:
        bundle_entries: Bundle-Einträge mit error == null.
        ground_truth_by_id: Mapping question_id → ground_truth.

    Returns:
        ragas.EvaluationDataset
    """
    samples = []
    for entry in bundle_entries:
        result = entry["result"]
        samples.append(
            SingleTurnSample(
                user_input=result["query"],
                response=result["answer"],
                retrieved_contexts=[
                    chunk["text"] for chunk in result["retrieved_chunks"]
                ],
                reference=ground_truth_by_id.get(entry["question_id"], ""),
            )
        )
    return EvaluationDataset(samples=samples)


def _configure_judge(model_name: str) -> LangchainLLMWrapper:
    """Erstellt RAGAS-konformen Judge-LLM-Wrapper.

    Args:
        model_name: OpenAI-Modell-ID (z. B. "gpt-4o").

    Returns:
        ragas.llms.LangchainLLMWrapper für den Judge.
    """
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=model_name,
        temperature=RAGAS_JUDGE_TEMPERATURE,
        seed=RAGAS_JUDGE_SEED,
        api_key=OPENAI_API_KEY,
    )
    return LangchainLLMWrapper(llm)


def _extract_scores(
    ragas_result, bundle_entries: list[dict]
) -> list[RagasScores]:
    """Extrahiert Pro-Frage-Scores aus dem RAGAS-EvaluationResult.

    RAGAS gibt ein EvaluationResult zurück; to_pandas() liefert
    einen DataFrame in Eingabe-Reihenfolge.

    Args:
        ragas_result: Output von ragas.evaluate().
        bundle_entries: Einträge mit error == null, in derselben
                        Reihenfolge wie das EvaluationDataset.

    Returns:
        Liste von RagasScores in Bundle-Reihenfolge.
    """
    import math

    df = ragas_result.to_pandas()
    scores: list[RagasScores] = []

    for i, entry in enumerate(bundle_entries):
        row = df.iloc[i] if i < len(df) else None

        def _get(col: str, _row=row) -> float | None:
            if _row is None or col not in df.columns:
                return None
            val = _row[col]
            if val is None:
                return None
            try:
                f = float(val)
                return None if math.isnan(f) else f
            except (TypeError, ValueError):
                return None

        scores.append(
            RagasScores(
                question_id=entry["question_id"],
                category=entry["category"],
                faithfulness=_get(_COL_FAITHFULNESS),
                answer_relevance=_get(_COL_ANSWER_RELEVANCE),
                context_recall=_get(_COL_CONTEXT_RECALL),
                factual_correctness=_get(_COL_FACTUAL_CORRECTNESS),
            )
        )
    return scores


def _persist_scores(
    scores: list[RagasScores],
    output_path: Path,
    bundle_path: Path,
    judge_model: str,
    n_skipped_errors: int,
    n_with_ground_truth: int,
) -> Path:
    """Schreibt Scores plus Metadaten als JSON.

    Schema:
        {
            "metadata": {
                "bundle_path": "<path>",
                "judge_model": "gpt-4o",
                "scored_at": "<iso-ts>",
                "n_total": <int>,
                "n_skipped_errors": <int>,
                "n_with_ground_truth": <int>
            },
            "scores": [...]
        }
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "bundle_path": str(bundle_path),
            "judge_model": judge_model,
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "n_total": len(scores) + n_skipped_errors,
            "n_skipped_errors": n_skipped_errors,
            "n_with_ground_truth": n_with_ground_truth,
        },
        "scores": [asdict(s) for s in scores],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Scores persistiert: %s", output_path)
    return output_path

"""Rescore Faithfulness und LLMContextRecall für alle Bundles aus AP-14.

Lädt das aktuellste Bundle und Score-File pro Variante, scort beide Metriken
mit konservativen Concurrency-Parametern und merged die Resultate in die
bestehenden ragas_*.json-Dateien.

Hintergrund: AP-14 lieferte für 168 von 800 Metrik-Werten NaN wegen
TimeoutErrors bei paralleler Ausführung mit RAGAS 0.4.3. AP-19 hat
diagnostisch bestätigt, dass die Antworten selbst scorebar sind und
das Problem rein in der Bewertungs-Infrastruktur liegt.
"""

import json
import logging
import math
import sys
from datetime import datetime, timezone
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
from rag.evaluate.reporter import build_summary, write_markdown
from rag.evaluate.testset import load_testset

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

VARIANTS = ["v0", "v1", "v2", "v3", "v4"]

RUN_CONFIG = RunConfig(
    timeout=300,
    max_workers=2,
    max_retries=5,
    log_tenacity=True,
)

# Erfolgsquote-Schwellenwert für Stopp-Bedingung nach V0
_STOP_THRESHOLD = 0.80


def _load_bundle(bundle_path: Path) -> list[dict]:
    """Lädt JSONL-Bundle."""
    with bundle_path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _find_latest(variant: str) -> tuple[Path, Path]:
    """Findet jüngstes responses_*.jsonl und ragas_*.json pro Variante."""
    variant_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(variant_dir.glob("responses_*.jsonl"))
    scores = sorted(variant_dir.glob("ragas_*.json"))
    if not bundles or not scores:
        raise FileNotFoundError(f"Bundle/Score fehlt in {variant_dir}")
    return bundles[-1], scores[-1]


def _build_judge() -> LangchainLLMWrapper:
    """Erstellt Judge-LLM mit erhöhtem Timeout."""
    llm = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL,
        temperature=RAGAS_JUDGE_TEMPERATURE,
        seed=RAGAS_JUDGE_SEED,
        api_key=OPENAI_API_KEY,
        timeout=180.0,
        max_retries=3,
    )
    return LangchainLLMWrapper(llm)


def _extract_metric(df, metric_keys: list[str], n_samples: int) -> list[float | None]:
    """Extrahiert Metrik-Werte robust gegen Spaltennamen-Variation."""
    col = None
    for key in metric_keys:
        for c in df.columns:
            if key in c.lower():
                col = c
                break
        if col:
            break
    if col is None:
        logger.error(
            "Keine passende Spalte für %s. Verfügbare: %s", metric_keys, list(df.columns)
        )
        return [None] * n_samples

    logger.info("  Spalte: %s", col)
    values: list[float | None] = []
    for i in range(n_samples):
        if i >= len(df):
            values.append(None)
            continue
        v = df[col].iloc[i]
        if v is None:
            values.append(None)
            continue
        try:
            f = float(v)
            values.append(None if math.isnan(f) else f)
        except (TypeError, ValueError):
            values.append(None)
    return values


def rescore_variant(variant: str, gt_by_id: dict[str, str]) -> dict:
    """Rescort Faithfulness und LLMContextRecall für eine Variante."""
    bundle_path, scores_path = _find_latest(variant)
    logger.info("=== Rescore %s ===", variant.upper())
    logger.info("  Bundle: %s", bundle_path)
    logger.info("  Scores: %s", scores_path)

    entries = _load_bundle(bundle_path)
    valid_entries = [e for e in entries if e.get("error") is None]
    n_samples = len(valid_entries)
    logger.info("  %d/%d Einträge ohne Fehler", n_samples, len(entries))

    if n_samples == 0:
        logger.warning("  Keine scorebaren Samples – überspringe %s", variant)
        return {
            "variant": variant,
            "n_scored": 0,
            "faithfulness_success": 0,
            "context_recall_success": 0,
        }

    samples = []
    samples_meta = []
    for entry in valid_entries:
        result = entry["result"]
        gt = gt_by_id.get(entry["question_id"], "")
        samples.append(
            SingleTurnSample(
                user_input=result["query"],
                response=result["answer"],
                retrieved_contexts=[c["text"] for c in result["retrieved_chunks"]],
                reference=gt,
            )
        )
        samples_meta.append({"qid": entry["question_id"]})

    judge = _build_judge()
    dataset = EvaluationDataset(samples=samples)

    logger.info(
        "  Starte Scoring (%d Samples, max_workers=2, timeout=300s)...", n_samples
    )
    ragas_result = evaluate(
        dataset=dataset,
        metrics=[
            Faithfulness(llm=judge),
            LLMContextRecall(llm=judge),
        ],
        run_config=RUN_CONFIG,
        raise_exceptions=False,
        show_progress=True,
    )

    df = ragas_result.to_pandas()
    logger.info("  DataFrame-Spalten: %s", list(df.columns))

    faith_values = _extract_metric(df, ["faithfulness"], n_samples)
    recall_values = _extract_metric(df, ["context_recall"], n_samples)

    faith_by_qid = {
        meta["qid"]: faith_values[i] for i, meta in enumerate(samples_meta)
    }
    recall_by_qid = {
        meta["qid"]: recall_values[i] for i, meta in enumerate(samples_meta)
    }

    # Merge in bestehende Scores
    payload = json.loads(scores_path.read_text(encoding="utf-8"))
    n_faith_success = 0
    n_recall_success = 0
    for score_entry in payload["scores"]:
        qid = score_entry["question_id"]
        new_faith = faith_by_qid.get(qid)
        new_recall = recall_by_qid.get(qid)
        if new_faith is not None:
            score_entry["faithfulness"] = new_faith
            n_faith_success += 1
        if new_recall is not None:
            score_entry["context_recall"] = new_recall
            n_recall_success += 1

    now_iso = datetime.now(timezone.utc).isoformat()
    payload["metadata"]["faithfulness_rescored_at"] = now_iso
    payload["metadata"]["context_recall_rescored_at"] = now_iso
    payload["metadata"]["faithfulness_n_scored"] = n_faith_success
    payload["metadata"]["context_recall_n_scored"] = n_recall_success

    # Backup (einmalig)
    backup_path = scores_path.with_suffix(".json.backup_pre_ap20")
    if not backup_path.exists():
        backup_path.write_bytes(scores_path.read_bytes())
        logger.info("  Backup: %s", backup_path)

    scores_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "  → Faithfulness: %d/%d, ContextRecall: %d/%d",
        n_faith_success, n_samples,
        n_recall_success, n_samples,
    )

    # Summary aktualisieren
    bundle_ts = scores_path.stem.replace("ragas_", "")
    summary_path = scores_path.parent / f"summary_{bundle_ts}.md"
    summary = build_summary(scores_path, variant)
    write_markdown(summary, summary_path)
    logger.info("  Summary: %s", summary_path)

    return {
        "variant": variant,
        "n_scored": n_samples,
        "faithfulness_success": n_faith_success,
        "context_recall_success": n_recall_success,
    }


def main() -> None:
    questions = load_testset()
    gt_by_id = {q.id: q.ground_truth for q in questions}

    stats = []
    for i, variant in enumerate(VARIANTS):
        try:
            stat = rescore_variant(variant, gt_by_id)
            stats.append(stat)

            # Stopp-Bedingung nach V0
            if i == 0 and stat["n_scored"] > 0:
                faith_rate = stat["faithfulness_success"] / stat["n_scored"]
                recall_rate = stat["context_recall_success"] / stat["n_scored"]
                if faith_rate < _STOP_THRESHOLD or recall_rate < _STOP_THRESHOLD:
                    logger.error(
                        "STOPP: V0-Erfolgsquote unter 80%% "
                        "(Faith: %.0f%%, Recall: %.0f%%). "
                        "Bitte max_workers auf 1 reduzieren.",
                        faith_rate * 100, recall_rate * 100,
                    )
                    return

        except Exception as exc:
            logger.error("Variante %s fehlgeschlagen: %s", variant, exc)
            stats.append({"variant": variant, "error": str(exc)})

    logger.info("=" * 60)
    logger.info("Gesamt-Übersicht:")
    for s in stats:
        if "error" in s:
            logger.info("  %s: FEHLER (%s)", s["variant"].upper(), s["error"])
        else:
            logger.info(
                "  %s: Faith %d/%d, Recall %d/%d",
                s["variant"].upper(),
                s["faithfulness_success"], s["n_scored"],
                s["context_recall_success"], s["n_scored"],
            )


if __name__ == "__main__":
    main()

"""Rescore FactualCorrectness für alle Bundles aus AP-14.

Lädt das aktuellste Bundle und Score-File pro Variante, scort nur die
FactualCorrectness-Metrik mit konservativen Concurrency-Parametern,
und merged die Resultate in die bestehenden ragas_*.json-Dateien.

Hintergrund: AP-14 lieferte für FactualCorrectness durchgängig None
wegen TimeoutErrors bei paralleler Ausführung mit RAGAS 0.4.3.
Fix: max_workers=2, timeout=300s, max_retries=5.
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
from ragas.metrics import FactualCorrectness

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

# Bekannter Spaltenname aus Diagnose-Lauf (RAGAS 0.4.3)
_FC_COLUMN = "factual_correctness(mode=f1)"


def _load_bundle(bundle_path: Path) -> list[dict]:
    with bundle_path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _find_latest_files(variant: str) -> tuple[Path, Path]:
    """Findet jüngstes responses_*.jsonl und ragas_*.json für eine Variante."""
    variant_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(variant_dir.glob("responses_*.jsonl"))
    scores = sorted(variant_dir.glob("ragas_*.json"))
    if not bundles or not scores:
        raise FileNotFoundError(f"Bundle oder Score-File fehlt in {variant_dir}")
    return bundles[-1], scores[-1]


def _build_judge() -> LangchainLLMWrapper:
    llm = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL,
        temperature=RAGAS_JUDGE_TEMPERATURE,
        seed=RAGAS_JUDGE_SEED,
        api_key=OPENAI_API_KEY,
        timeout=120.0,
        max_retries=3,
    )
    return LangchainLLMWrapper(llm)


def _extract_fc_values(df, n_samples: int) -> list[float | None]:
    """Extrahiert FactualCorrectness-Werte robust gegen Spaltennamen-Variation."""
    candidates = [
        _FC_COLUMN,
        "factual_correctness",
        "factual_correctness(mode=precision)",
        "factual_correctness(mode=recall)",
    ]
    col = next((c for c in candidates if c in df.columns), None)
    if col is None:
        logger.error(
            "Keine FactualCorrectness-Spalte gefunden. Verfügbare: %s",
            list(df.columns),
        )
        return [None] * n_samples

    logger.info("  Verwende Spalte: %s", col)
    values: list[float | None] = []
    for i in range(n_samples):
        v = df[col].iloc[i] if i < len(df) else None
        try:
            f = float(v)  # type: ignore[arg-type]
            values.append(None if math.isnan(f) else f)
        except (TypeError, ValueError):
            values.append(None)
    return values


def rescore_variant(variant: str, gt_by_id: dict[str, str]) -> dict:
    """Rescort FactualCorrectness für eine Variante und merged in bestehendes JSON."""
    bundle_path, scores_path = _find_latest_files(variant)
    logger.info("=== Rescore %s ===", variant.upper())
    logger.info("  Bundle: %s", bundle_path)
    logger.info("  Scores: %s", scores_path)

    entries = _load_bundle(bundle_path)
    valid_entries = [e for e in entries if e.get("error") is None]

    # Nur Einträge mit Ground-Truth können gescort werden
    scoreable = [
        e for e in valid_entries
        if gt_by_id.get(e["question_id"], "").strip()
    ]
    n_scoreable = len(scoreable)
    logger.info(
        "  %d Einträge total, %d ohne Fehler, %d mit Ground-Truth",
        len(entries), len(valid_entries), n_scoreable,
    )

    if n_scoreable == 0:
        logger.warning("  Keine scoreable Samples – überspringe %s", variant)
        return {"variant": variant, "n_scored": 0, "n_success": 0, "n_failed": 0}

    samples = [
        SingleTurnSample(
            user_input=e["result"]["query"],
            response=e["result"]["answer"],
            retrieved_contexts=[c["text"] for c in e["result"]["retrieved_chunks"]],
            reference=gt_by_id[e["question_id"]],
        )
        for e in scoreable
    ]

    judge = _build_judge()
    dataset = EvaluationDataset(samples=samples)

    logger.info("  Scoring %d Samples (max_workers=2, timeout=300s)...", n_scoreable)
    ragas_result = evaluate(
        dataset=dataset,
        metrics=[FactualCorrectness(llm=judge)],
        run_config=RUN_CONFIG,
        raise_exceptions=False,
        show_progress=True,
    )

    df = ragas_result.to_pandas()
    fc_values = _extract_fc_values(df, n_scoreable)

    # Map question_id → score
    score_by_qid: dict[str, float | None] = {
        e["question_id"]: fc_values[i] for i, e in enumerate(scoreable)
    }

    # Bestehende ragas_*.json laden und FactualCorrectness mergen
    payload = json.loads(scores_path.read_text(encoding="utf-8"))

    n_success = 0
    n_failed = 0
    for score_entry in payload["scores"]:
        qid = score_entry["question_id"]
        new_val = score_by_qid.get(qid)
        score_entry["factual_correctness"] = new_val
        if new_val is not None:
            n_success += 1
        else:
            n_failed += 1

    payload["metadata"]["factual_correctness_rescored_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    payload["metadata"]["factual_correctness_n_success"] = n_success

    # Backup anlegen (einmalig)
    backup_path = scores_path.with_suffix(".json.backup_pre_ap15")
    if not backup_path.exists():
        backup_path.write_bytes(scores_path.read_bytes())
        logger.info("  Backup: %s", backup_path)

    scores_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(
        "  Scores aktualisiert: %d/%d FactualCorrectness gesetzt",
        n_success, n_scoreable,
    )

    # Markdown-Summary aktualisieren
    bundle_ts = scores_path.stem.replace("ragas_", "")
    summary_path = scores_path.parent / f"summary_{bundle_ts}.md"
    summary = build_summary(scores_path, variant)
    write_markdown(summary, summary_path)
    logger.info("  Summary: %s", summary_path)

    return {
        "variant": variant,
        "n_scored": n_scoreable,
        "n_success": n_success,
        "n_failed": n_failed,
    }


def main() -> None:
    questions = load_testset()
    gt_by_id = {q.id: q.ground_truth for q in questions}

    stats = []
    for variant in VARIANTS:
        try:
            stat = rescore_variant(variant, gt_by_id)
            stats.append(stat)
        except Exception as exc:
            logger.error("Variante %s fehlgeschlagen: %s", variant, exc)
            stats.append(
                {"variant": variant, "n_scored": 0, "n_success": 0,
                 "n_failed": 0, "error": str(exc)}
            )

    logger.info("=" * 60)
    logger.info("Gesamt-Übersicht:")
    total_success = 0
    total_scored = 0
    for s in stats:
        if "error" in s:
            logger.info("  %s: FEHLER (%s)", s["variant"].upper(), s["error"])
        else:
            logger.info(
                "  %s: %d/%d Werte erfolgreich",
                s["variant"].upper(), s["n_success"], s["n_scored"],
            )
            total_success += s["n_success"]
            total_scored += s["n_scored"]

    if total_scored > 0:
        rate = total_success / total_scored
        logger.info("Gesamt-Erfolgsrate: %d/%d (%.0f%%)", total_success, total_scored, rate * 100)
        if rate < 0.30:
            logger.error(
                "ACHTUNG: Erfolgsrate <30%%. User-Entscheid erforderlich."
            )


if __name__ == "__main__":
    main()

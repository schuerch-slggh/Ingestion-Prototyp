"""Konsolidiert alle Antwort-Bundles aus dem Vollauf-Eval in eine zentrale JSON-Datei.

Lädt pro Variante (V0-V4) das jüngste responses_*.jsonl und kombiniert
die Antworten in einer frage-zentrierten Struktur, in der jede Frage die
Antworten aller fünf Varianten enthält.

Output: runs/eval/aggregate/full_run_answers_<timestamp>.json
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.config import EVAL_RUNS_DIR
from rag.evaluate.testset import load_testset

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

VARIANTS = ["v0", "v1", "v2", "v3", "v4"]


def _load_latest_bundle(variant: str) -> tuple[Path, list[dict]]:
    """Lädt das jüngste responses_*.jsonl pro Variante."""
    variant_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(variant_dir.glob("responses_*.jsonl"))
    if not bundles:
        raise FileNotFoundError(f"Kein Bundle in {variant_dir}")
    bundle_path = bundles[-1]
    with bundle_path.open(encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    return bundle_path, entries


def _extract_answer_record(entry: dict) -> dict:
    """Reduziert einen Bundle-Eintrag auf die für den Anhang relevanten Felder."""
    if entry.get("error") is not None:
        return {"error": entry["error"], "answer": None, "retrieved_chunk_ids": [], "n_retrieved": 0}

    result = entry["result"]
    chunk_ids = [c.get("chunk_id") for c in result.get("retrieved_chunks", [])]
    return {
        "error": None,
        "answer": result.get("answer", ""),
        "retrieved_chunk_ids": chunk_ids,
        "n_retrieved": len(chunk_ids),
    }


def main() -> None:
    questions = load_testset()

    bundles_by_variant: dict[str, dict[str, dict]] = {}
    bundle_paths: dict[str, str] = {}
    for variant in VARIANTS:
        bundle_path, entries = _load_latest_bundle(variant)
        bundle_paths[variant] = str(bundle_path)
        bundles_by_variant[variant] = {e["question_id"]: e for e in entries}
        logger.info(
            "%s: %d Einträge aus %s", variant.upper(), len(entries), bundle_path.name
        )

    consolidated: list[dict] = []
    for q in questions:
        record = {
            "question_id": q.id,
            "question": q.question,
            "category": q.category,
            "ground_truth": q.ground_truth,
            "answers": {},
        }
        for variant in VARIANTS:
            entry = bundles_by_variant[variant].get(q.id)
            if entry is None:
                record["answers"][variant] = {
                    "error": "not_found_in_bundle",
                    "answer": None,
                    "retrieved_chunk_ids": [],
                    "n_retrieved": 0,
                }
            else:
                record["answers"][variant] = _extract_answer_record(entry)
        consolidated.append(record)

    output_dir = EVAL_RUNS_DIR / "aggregate"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"full_run_answers_{ts}.json"

    payload = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_questions": len(consolidated),
            "variants": VARIANTS,
            "source_bundles": bundle_paths,
        },
        "questions": consolidated,
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Konsolidierte Datei: %s", output_path)
    logger.info(
        "→ %d Fragen × %d Varianten = %d Antwort-Datensätze",
        len(consolidated),
        len(VARIANTS),
        len(consolidated) * len(VARIANTS),
    )


if __name__ == "__main__":
    main()

"""AP-18: Analysiert fehlende RAGAS-Scores über alle Varianten.

Lädt pro Variante das jüngste Bundle und Score-File, identifiziert
Fragen ohne gültige Score-Werte pro Metrik und erzeugt einen
Markdown-Bericht mit Übersichtstabelle und Detailabschnitten.

Output: runs/eval/aggregate/missing_scores_analysis_<timestamp>.md
"""

import json
import logging
import math
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

METRICS = [
    ("faithfulness", "Faithfulness"),
    ("answer_relevance", "Answer Relevance"),
    ("context_recall", "Context Recall"),
    ("factual_correctness", "Factual Correctness"),
]


def _is_missing(value) -> bool:
    """Prüft ob ein Score-Wert fehlt (None oder NaN)."""
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def _find_latest_files(variant: str) -> tuple[Path, Path]:
    """Findet jüngstes responses_*.jsonl und ragas_*.json für eine Variante."""
    variant_dir = EVAL_RUNS_DIR / variant
    bundles = sorted(variant_dir.glob("responses_*.jsonl"))
    scores = sorted(variant_dir.glob("ragas_*.json"))
    if not bundles or not scores:
        raise FileNotFoundError(f"Bundle oder Score-File fehlt in {variant_dir}")
    return bundles[-1], scores[-1]


def collect_missing(
    variant: str, questions_by_id: dict[str, object]
) -> dict:
    """Sammelt alle Fragen mit fehlenden Scores für eine Variante.

    Args:
        variant:          Variant-Identifier (z.B. "v0").
        questions_by_id:  Dict question_id → TestQuestion.

    Returns:
        Dict mit Varianten-Metadaten und fehlenden Scores pro Metrik.
    """
    bundle_path, scores_path = _find_latest_files(variant)

    # Bundle laden: question_id → entry
    with bundle_path.open(encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    bundle_by_qid = {e["question_id"]: e for e in entries}

    # Score-File laden: question_id → score-record
    payload = json.loads(scores_path.read_text(encoding="utf-8"))
    scores_by_qid = {s["question_id"]: s for s in payload["scores"]}

    missing_by_metric: dict[str, list[dict]] = {key: [] for key, _ in METRICS}

    for qid, score_rec in scores_by_qid.items():
        bundle_entry = bundle_by_qid.get(qid, {})
        result = bundle_entry.get("result", {})
        retrieved_chunks = result.get("retrieved_chunks", [])
        chunk_ids = [c.get("id") for c in retrieved_chunks]
        n_retrieved = len(chunk_ids)
        answer = result.get("answer", "") or ""
        query = result.get("query", "") or ""

        q = questions_by_id.get(qid)
        category = score_rec.get("category", q.category if q else "unknown")

        for key, _ in METRICS:
            if _is_missing(score_rec.get(key)):
                missing_by_metric[key].append(
                    {
                        "question_id": qid,
                        "category": category,
                        "n_retrieved": n_retrieved,
                        "question": query,
                        "answer": answer,
                        "bundle_error": bundle_entry.get("error"),
                        "has_ground_truth": bool(
                            q and q.ground_truth and q.ground_truth.strip()
                        ),
                    }
                )

    logger.info(
        "%s: fehlende Scores – %s",
        variant.upper(),
        ", ".join(
            f"{label}={len(missing_by_metric[key])}"
            for key, label in METRICS
        ),
    )

    return {
        "variant": variant,
        "bundle_path": str(bundle_path),
        "scores_path": str(scores_path),
        "n_total": payload["metadata"]["n_total"],
        "missing_by_metric": missing_by_metric,
    }


def render_report(stats_by_variant: list[dict]) -> str:
    """Erzeugt Markdown-Bericht über fehlende Scores.

    Args:
        stats_by_variant: Liste von collect_missing()-Ergebnissen.

    Returns:
        Markdown-String des vollständigen Berichts.
    """
    lines: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines.append("# Analyse fehlender RAGAS-Scores")
    lines.append("")
    lines.append(f"Generiert: {ts}")
    lines.append("")

    # Übersichtstabelle
    lines.append("## Übersicht: Fehlende Scores nach Variante und Metrik")
    lines.append("")
    header = "| Variante | " + " | ".join(label for _, label in METRICS) + " |"
    sep = "|---|" + "|".join("---" for _ in METRICS) + "|"
    lines.append(header)
    lines.append(sep)
    for stats in stats_by_variant:
        v = stats["variant"].upper()
        n = stats["n_total"]
        cells = []
        for key, _ in METRICS:
            count = len(stats["missing_by_metric"][key])
            cells.append(f"{count}/{n}" if count > 0 else "✓")
        lines.append("| " + v + " | " + " | ".join(cells) + " |")
    lines.append("")

    # Detailabschnitte
    lines.append("## Details pro Variante")
    lines.append("")

    for stats in stats_by_variant:
        v = stats["variant"].upper()
        any_missing = any(
            stats["missing_by_metric"][key] for key, _ in METRICS
        )
        if not any_missing:
            lines.append(f"### {v}")
            lines.append("")
            lines.append("Alle Scores vollständig – keine fehlenden Werte.")
            lines.append("")
            continue

        lines.append(f"### {v}")
        lines.append("")
        lines.append(f"- Bundle: `{stats['bundle_path']}`")
        lines.append(f"- Scores: `{stats['scores_path']}`")
        lines.append("")

        for key, label in METRICS:
            missing = stats["missing_by_metric"][key]
            if not missing:
                continue

            lines.append(f"#### {label} ({len(missing)} fehlend)")
            lines.append("")

            for m in sorted(missing, key=lambda x: x["question_id"]):
                gt_marker = "ja" if m["has_ground_truth"] else "**nein**"
                lines.append(
                    f"**{m['question_id']}** | Kategorie: {m['category']} | "
                    f"n_retrieved: {m['n_retrieved']} | Ground-Truth: {gt_marker}"
                )
                lines.append("")
                if m["bundle_error"]:
                    lines.append(f"> **Bundle-Fehler:** {m['bundle_error']}")
                else:
                    lines.append(f"*Frage:* {m['question']}")
                    lines.append("")
                    lines.append("*Generierte Antwort:*")
                    lines.append("")
                    lines.append("```")
                    lines.append(m["answer"] if m["answer"] else "(keine Antwort)")
                    lines.append("```")
                lines.append("")

            if key == "factual_correctness":
                no_gt = [m for m in missing if not m["has_ground_truth"]]
                if no_gt:
                    ids = ", ".join(m["question_id"] for m in no_gt)
                    lines.append(
                        f"> **Hinweis:** {len(no_gt)} Frage(n) ohne Ground-Truth "
                        f"(FactualCorrectness nicht scorebar): {ids}"
                    )
                    lines.append("")

    return "\n".join(lines)


def main() -> None:
    questions = load_testset()
    questions_by_id = {q.id: q for q in questions}

    stats_by_variant: list[dict] = []
    for variant in VARIANTS:
        try:
            stats = collect_missing(variant, questions_by_id)
            stats_by_variant.append(stats)
        except Exception as exc:
            logger.error("Variante %s fehlgeschlagen: %s", variant, exc)
            stats_by_variant.append(
                {
                    "variant": variant,
                    "bundle_path": "",
                    "scores_path": "",
                    "n_total": 0,
                    "missing_by_metric": {key: [] for key, _ in METRICS},
                    "error": str(exc),
                }
            )

    report = render_report(stats_by_variant)

    output_dir = EVAL_RUNS_DIR / "aggregate"
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"missing_scores_analysis_{ts}.md"
    output_path.write_text(report, encoding="utf-8")
    logger.info("Bericht geschrieben: %s", output_path)

    # Kurzzusammenfassung in Konsole
    total_missing = sum(
        len(s["missing_by_metric"][key])
        for s in stats_by_variant
        for key, _ in METRICS
    )
    logger.info("Gesamt fehlende Score-Einträge: %d", total_missing)


if __name__ == "__main__":
    main()

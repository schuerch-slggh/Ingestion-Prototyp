"""Reporter: Aggregiert RAGAS-Scores zu einer Markdown-Summary."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_CATEGORY_ORDER = ["Chunking", "Recency", "Visuals", "CrossSource"]


@dataclass
class CategoryAggregate:
    """Aggregat-Metriken für eine Kategorie (oder ALL)."""

    category: str
    n: int
    faithfulness_mean: float | None
    answer_relevance_mean: float | None
    context_precision_mean: float | None


@dataclass
class VariantSummary:
    """Vollständige Zusammenfassung für eine Variante."""

    variant: str
    n_total: int
    n_scored: int
    overall: CategoryAggregate
    by_category: list[CategoryAggregate]
    bundle_path: Path
    scores_path: Path


def build_summary(scores_path: Path, variant: str) -> VariantSummary:
    """Aggregiert RAGAS-Scores zu einer VariantSummary.

    Args:
        scores_path: Pfad zur ragas_<ts>.json.
        variant:     Variant-Identifier.

    Returns:
        VariantSummary mit Gesamt- und Kategorie-Mittelwerten.

    Notes:
        None-Scores werden bei der Mittelwertberechnung ausgeschlossen
        (nicht als 0 gewertet).
    """
    payload = json.loads(scores_path.read_text(encoding="utf-8"))
    meta = payload["metadata"]
    raw_scores = payload["scores"]

    bundle_path = Path(meta["bundle_path"])
    n_total = meta["n_total"]

    # Group by category
    groups: dict[str, list[dict]] = {}
    for s in raw_scores:
        groups.setdefault(s["category"], []).append(s)

    def _agg(entries: list[dict], label: str) -> CategoryAggregate:
        faiths = [e["faithfulness"] for e in entries]
        relevs = [e["answer_relevance"] for e in entries]
        precs = [e["context_precision"] for e in entries]
        return CategoryAggregate(
            category=label,
            n=len(entries),
            faithfulness_mean=_mean_excluding_none(faiths),
            answer_relevance_mean=_mean_excluding_none(relevs),
            context_precision_mean=_mean_excluding_none(precs),
        )

    overall = _agg(raw_scores, "ALL")

    by_category: list[CategoryAggregate] = []
    for cat in _CATEGORY_ORDER:
        if cat in groups:
            by_category.append(_agg(groups[cat], cat))

    logger.info(
        "Summary gebaut: %s | %d/%d gescort | faith=%.3f arel=%.3f cprec=%.3f",
        variant,
        len(raw_scores),
        n_total,
        overall.faithfulness_mean or 0,
        overall.answer_relevance_mean or 0,
        overall.context_precision_mean or 0,
    )

    return VariantSummary(
        variant=variant,
        n_total=n_total,
        n_scored=len(raw_scores),
        overall=overall,
        by_category=by_category,
        bundle_path=bundle_path,
        scores_path=scores_path,
    )


def write_markdown(summary: VariantSummary, output_path: Path) -> Path:
    """Schreibt VariantSummary als Markdown-Datei.

    Args:
        summary:     VariantSummary-Instanz.
        output_path: Pfad zur summary_<ts>.md.

    Returns:
        Pfad zur erzeugten Datei.
    """
    def _fmt(v: float | None) -> str:
        return f"{v:.3f}" if v is not None else "–"

    lines: list[str] = []
    ts = summary.scores_path.stem.replace("ragas_", "")
    lines.append(f"# Evaluation {summary.variant.upper()} – {ts}")
    lines.append("")
    lines.append(f"**Bundle:** `{summary.bundle_path}`")
    lines.append(f"**Scores:** `{summary.scores_path}`")
    lines.append(f"**Anzahl Fragen:** {summary.n_total} ({summary.n_scored} erfolgreich gescort)")
    lines.append("")

    lines.append("## Gesamtergebnis")
    lines.append("")
    lines.append("| Metrik | Mittelwert | n |")
    lines.append("|---|---|---|")
    o = summary.overall
    lines.append(f"| Faithfulness | {_fmt(o.faithfulness_mean)} | {o.n} |")
    lines.append(f"| Answer Relevance | {_fmt(o.answer_relevance_mean)} | {o.n} |")
    lines.append(f"| Context Precision | {_fmt(o.context_precision_mean)} | {o.n} |")
    lines.append("")

    if summary.by_category:
        lines.append("## Pro Kategorie")
        lines.append("")
        lines.append(
            "| Kategorie | n | Faithfulness | Answer Relevance | Context Precision |"
        )
        lines.append("|---|---|---|---|---|")
        for cat in summary.by_category:
            lines.append(
                f"| {cat.category} | {cat.n} "
                f"| {_fmt(cat.faithfulness_mean)} "
                f"| {_fmt(cat.answer_relevance_mean)} "
                f"| {_fmt(cat.context_precision_mean)} |"
            )
        lines.append("")

    none_counts = {
        "Faithfulness": sum(
            1 for s in summary.by_category if s.faithfulness_mean is None
        ),
        "Answer Relevance": sum(
            1 for s in summary.by_category if s.answer_relevance_mean is None
        ),
        "Context Precision": sum(
            1 for s in summary.by_category if s.context_precision_mean is None
        ),
    }
    missing = [k for k, v in none_counts.items() if v > 0]
    if missing:
        lines.append(
            f"> **Hinweis:** Für folgende Metriken fehlen Scores in "
            f"mindestens einer Kategorie: {', '.join(missing)}. "
            f"None-Werte wurden bei der Mittelwertberechnung ausgeschlossen."
        )
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Markdown-Summary geschrieben: %s", output_path)
    return output_path


def _mean_excluding_none(values: list[float | None]) -> float | None:
    """Berechnet Mittelwert, exkludiert None-Werte.

    Returns:
        Mittelwert über alle nicht-None-Werte, oder None falls keine
        nicht-None-Werte vorhanden sind.
    """
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None

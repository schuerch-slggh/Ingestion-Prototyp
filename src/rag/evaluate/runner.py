"""Runner: Führt die Pipeline über das Test-Set aus und persistiert ein Bundle."""

import dataclasses
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from rag.evaluate.testset import TestQuestion, iter_by_category
from rag.generate.pipeline import answer_query

logger = logging.getLogger(__name__)

# Stand Mai 2026 (https://openai.com/api/pricing/)
# Falls die Preise geändert werden müssen, sind die Stellen hier dokumentiert.
GPT_4_1_INPUT_COST_PER_MTOK: float = 2.00   # USD pro 1M Input-Tokens
GPT_4_1_OUTPUT_COST_PER_MTOK: float = 8.00  # USD pro 1M Output-Tokens
EMBEDDING_3_LARGE_COST_PER_MTOK: float = 0.13  # USD pro 1M Tokens (Retrieval)
ERROR_RATE_ABORT_THRESHOLD: float = 0.5  # >50% Fehler → Abbruch


@dataclass
class BundleEntry:
    """Ein Eintrag im Response-Bundle (eine Zeile JSONL)."""

    question_id: str
    category: str
    result: dict | None
    error: str | None


def run_testset(
    questions: list[TestQuestion],
    variant: str,
    output_path: Path,
) -> Path:
    """Führt die Pipeline einer Variante über alle Fragen aus.

    Schreibt zeilenweise ins Bundle. Persistiert auch bei Crash
    den bisherigen Stand.

    Args:
        questions: Liste validierter Test-Fragen aus testset.load_testset.
        variant: Pipeline-Variante (z. B. "v0").
        output_path: Vollständiger Pfad zur JSONL-Output-Datei.
                     Verzeichnis wird bei Bedarf erzeugt.

    Returns:
        Pfad zur erzeugten Bundle-Datei.

    Raises:
        RuntimeError: Wenn Fehlerquote ERROR_RATE_ABORT_THRESHOLD
                      überschreitet (Schutz gegen API-Probleme).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    entries: list[BundleEntry] = []

    with output_path.open("w", encoding="utf-8") as fh:
        for q in tqdm(questions, desc=f"Eval {variant}", unit="q"):
            logger.debug("Verarbeite %s: %s", q.id, q.question[:60])
            try:
                result = answer_query(q.question, variant)
                entry = BundleEntry(
                    question_id=q.id,
                    category=q.category,
                    result=result,
                    error=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fehler bei %s: %s", q.id, exc)
                entry = BundleEntry(
                    question_id=q.id,
                    category=q.category,
                    result=None,
                    error=str(exc),
                )

            fh.write(json.dumps(dataclasses.asdict(entry), ensure_ascii=False))
            fh.write("\n")
            fh.flush()
            entries.append(entry)

            n_processed = len(entries)
            n_errors = sum(1 for e in entries if e.error is not None)
            if n_processed >= 5 and n_errors / n_processed > ERROR_RATE_ABORT_THRESHOLD:
                raise RuntimeError(
                    f"Abbruch: Fehlerquote {n_errors}/{n_processed} übersteigt "
                    f"{ERROR_RATE_ABORT_THRESHOLD:.0%}. Letzter Fehler: "
                    f"{entry.error}"
                )

    stats = _aggregate_stats(entries)
    logger.info(
        "Eval abgeschlossen: %d/%d erfolgreich | %d Fehler | "
        "%.1f s | ~%.4f USD",
        stats["n_success"],
        stats["n_total"],
        stats["n_error"],
        stats["total_duration_s"],
        stats["estimated_cost_usd"],
    )
    logger.info("Bundle: %s", output_path)
    return output_path


def _aggregate_stats(entries: list[BundleEntry]) -> dict:
    """Berechnet Aggregate über das Bundle für die Schluss-Logging-Ausgabe.

    Returns:
        Dict mit: n_total, n_success, n_error, total_duration_s,
                  total_input_tokens, total_output_tokens,
                  estimated_cost_usd.
    """
    n_success = 0
    n_error = 0
    total_duration_s = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    for entry in entries:
        if entry.error is not None:
            n_error += 1
            continue
        n_success += 1
        meta = entry.result.get("metadata", {})  # type: ignore[union-attr]
        total_duration_s += meta.get("duration_seconds", 0.0)
        total_input_tokens += meta.get("input_tokens", 0)
        total_output_tokens += meta.get("output_tokens", 0)

    llm_cost = (
        total_input_tokens / 1_000_000 * GPT_4_1_INPUT_COST_PER_MTOK
        + total_output_tokens / 1_000_000 * GPT_4_1_OUTPUT_COST_PER_MTOK
    )

    return {
        "n_total": len(entries),
        "n_success": n_success,
        "n_error": n_error,
        "total_duration_s": total_duration_s,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "estimated_cost_usd": llm_cost,
    }


def _select_dry_run_subset(questions: list[TestQuestion]) -> list[TestQuestion]:
    """Selektiert 5 Fragen für den Dry-Run, stratifiziert nach Kategorie.

    Strategie: erste Frage jeder Kategorie (4 Stück) plus zweite
    Chunking-Frage. Deterministisch.

    Returns:
        Liste von 5 TestQuestion-Objekten in fester Reihenfolge:
        Q001 (1. Chunking), Q002 (2. Chunking), 1. Recency,
        1. Visuals, 1. CrossSource.
    """
    subset: list[TestQuestion] = []
    chunking_added = 0

    for category, group in iter_by_category(questions):
        if category == "Chunking":
            n = min(2, len(group))
            subset_chunking = list(group[:n])
            chunking_added = n
            if n < 2:
                logger.warning(
                    "Dry-Run: Kategorie Chunking hat nur %d Frage(n), "
                    "erwartet 2.",
                    n,
                )
        else:
            if not group:
                logger.warning(
                    "Dry-Run: Kategorie %s hat keine Fragen – wird übersprungen.",
                    category,
                )
                continue
            subset.append(group[0])

    # Chunking-Fragen vorne einsetzen
    result = (subset_chunking if chunking_added else []) + subset
    return result

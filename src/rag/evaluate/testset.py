"""Test-Set-Loader und Validator für die RAGAS-Evaluation."""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from rag.config import TESTSET_PATH

logger = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset({
    "Chunking",
    "Recency",
    "Visuals",
    "CrossSource",
})

ID_PATTERN = re.compile(r"^Q\d{3}$")

# Canonical display order for reports
_CATEGORY_ORDER = ["Chunking", "Recency", "Visuals", "CrossSource"]


@dataclass(frozen=True)
class TestQuestion:
    """Ein einzelner Test-Set-Eintrag."""

    id: str
    question: str
    category: str
    ground_truth: str = ""


def load_testset(path: Path | None = None) -> list[TestQuestion]:
    """Lädt das Test-Set aus einer JSONL-Datei.

    Args:
        path: Pfad zur JSONL-Datei. Falls None, wird TESTSET_PATH aus
              config.py verwendet.

    Returns:
        Liste validierter TestQuestion-Objekte in der Reihenfolge
        der Datei.

    Raises:
        FileNotFoundError: Wenn die Datei nicht existiert.
        ValueError: Wenn ein Eintrag das Schema verletzt
                    (mit Zeilennummer in der Fehlermeldung).
    """
    resolved = path or TESTSET_PATH
    if not resolved.exists():
        raise FileNotFoundError(
            f"Test-Set nicht gefunden: {resolved}. "
            "Bitte Schritt 1 aus AP-4.1 ausführen und die Datei ablegen."
        )

    questions: list[TestQuestion] = []
    with resolved.open(encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSON-Parsing-Fehler in Zeile {line_number}: {exc}"
                ) from exc
            questions.append(validate_entry(entry, line_number=line_number))

    _check_consistency(questions)
    return questions


def validate_entry(entry: dict, line_number: int | None = None) -> TestQuestion:
    """Validiert einen einzelnen Test-Set-Eintrag und konvertiert ihn
    in eine TestQuestion.

    Args:
        entry: Roh-Dictionary aus JSON-Parsing.
        line_number: Optionale Zeilennummer für Fehlermeldungen.

    Returns:
        Validierte TestQuestion-Instanz.

    Raises:
        ValueError: Bei Schema-Verletzung. Die Fehlermeldung enthält
                    den Eintrag-ID (falls vorhanden) und die
                    Zeilennummer (falls übergeben).
    """
    loc = f" (Zeile {line_number})" if line_number is not None else ""
    entry_id = entry.get("id", "<unbekannt>")

    for field in ("id", "question", "category"):
        if field not in entry:
            raise ValueError(
                f"Pflichtfeld '{field}' fehlt in Eintrag {entry_id}{loc}"
            )

    if not ID_PATTERN.match(entry["id"]):
        raise ValueError(
            f"Ungültiges ID-Format '{entry['id']}'{loc}: "
            "erwartet Q\\d{{3}} (z. B. Q001)"
        )

    if not isinstance(entry["question"], str) or not entry["question"].strip():
        raise ValueError(
            f"Feld 'question' ist leer oder kein String in Eintrag {entry_id}{loc}"
        )

    if entry["category"] not in VALID_CATEGORIES:
        allowed = ", ".join(sorted(VALID_CATEGORIES))
        raise ValueError(
            f"Ungültige Kategorie '{entry['category']}' in Eintrag {entry_id}{loc}. "
            f"Erlaubt: {allowed}"
        )

    ground_truth = entry.get("ground_truth", "")
    if not isinstance(ground_truth, str):
        raise ValueError(
            f"Feld 'ground_truth' muss ein String sein in Eintrag {entry_id}{loc}, "
            f"got {type(ground_truth).__name__}"
        )

    return TestQuestion(
        id=entry["id"],
        question=entry["question"],
        category=entry["category"],
        ground_truth=ground_truth,
    )


def iter_by_category(
    questions: list[TestQuestion],
) -> Iterator[tuple[str, list[TestQuestion]]]:
    """Gruppiert das Test-Set nach Kategorie.

    Yields:
        Tupel (kategorie, fragen) in der Reihenfolge:
        Chunking, Recency, Visuals, CrossSource.
        Kategorien ohne Einträge werden übersprungen.
    """
    groups: dict[str, list[TestQuestion]] = {cat: [] for cat in _CATEGORY_ORDER}
    for q in questions:
        groups.setdefault(q.category, []).append(q)

    for cat in _CATEGORY_ORDER:
        bucket = groups.get(cat, [])
        if bucket:
            yield cat, bucket


def _check_consistency(questions: list[TestQuestion]) -> None:
    """Loggt Warnungen zu Test-Set-Konsistenzproblemen, ohne abzubrechen."""
    if not questions:
        logger.warning("Test-Set ist leer – keine Einträge geladen.")
        return

    ids = [q.id for q in questions]

    # Duplicate IDs
    seen: set[str] = set()
    duplicates: list[str] = []
    for qid in ids:
        if qid in seen:
            duplicates.append(qid)
        seen.add(qid)
    if duplicates:
        logger.warning("Duplikat-IDs im Test-Set: %s", duplicates)

    # ID gaps (assumes Q-format already validated)
    numeric = sorted(int(qid[1:]) for qid in seen if ID_PATTERN.match(qid))
    if numeric:
        expected = set(range(numeric[0], numeric[-1] + 1))
        missing = expected - set(numeric)
        if missing:
            missing_ids = [f"Q{n:03d}" for n in sorted(missing)]
            logger.warning("Lücken in ID-Sequenz: %s", missing_ids)

    # Ground-Truth coverage
    empty_gt = sum(1 for q in questions if not q.ground_truth.strip())
    if empty_gt > 0:
        logger.warning(
            "Test-Set: %d von %d Fragen haben kein ground_truth gesetzt. "
            "Referenz-basierte Metriken (LLMContextRecall, FactualCorrectness) "
            "können für diese Fragen nicht berechnet werden.",
            empty_gt,
            len(questions),
        )

    # Category distribution (INFO)
    from collections import Counter
    dist = Counter(q.category for q in questions)
    logger.info(
        "Test-Set geladen: %d Fragen | %s",
        len(questions),
        " | ".join(f"{cat}: {dist.get(cat, 0)}" for cat in _CATEGORY_ORDER),
    )

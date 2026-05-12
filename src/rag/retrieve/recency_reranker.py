"""V3 Recency-Re-Ranking nach Grofsky (2025).

Berechnet pro Chunk einen Recency-Score und kombiniert ihn mit dem
RRF-Score zu einem finalen Score:

    final_score = α · rrf_score + (1 - α) · recency_score

mit:
    recency_score(c) = exp(-Δt / decay_rate)  falls c datiert ist
    recency_score(c) = 1.0                    sonst

Δt ist die Differenz in Tagen zwischen dem Chunk-Datum und dem aktuellen
Tag (date.today()).
"""

import logging
import math
from datetime import date
from typing import Iterable

from rag.config import (
    V3_ALPHA,
    V3_DECAY_RATE,
    V3_RECENCY_DATE_FIELDS,
)

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date | None:
    """Parst ISO-Date-String (YYYY-MM-DD) zu date oder None bei Fehler."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str.strip()[:10])
    except (ValueError, TypeError):
        logger.warning("Ungültiges Datumsformat: %r", date_str)
        return None


def _compute_recency_score(
    chunk: dict,
    today: date,
    decay_rate: float = V3_DECAY_RATE,
) -> float:
    """Berechnet Recency-Score für einen Chunk.

    Datierte Chunks (Forum, Ticket) erhalten exp(-Δt/decay_rate).
    Nicht-datierte Chunks erhalten 1.0.

    Args:
        chunk: Chunk-Dict mit `metadata`.
        today: Referenzdatum.
        decay_rate: Decay-Rate (Default V3_DECAY_RATE).

    Returns:
        Recency-Score im Intervall (0, 1].
    """
    metadata = chunk.get("metadata", {})
    source_type = metadata.get("source_type", "")
    date_field = V3_RECENCY_DATE_FIELDS.get(source_type)

    if not date_field:
        return 1.0

    date_value = metadata.get(date_field)
    chunk_date = _parse_date(date_value) if date_value else None

    if chunk_date is None:
        return 1.0

    delta_days = (today - chunk_date).days
    if delta_days < 0:
        return 1.0

    return math.exp(-delta_days * decay_rate)


def apply_recency_reranking(
    chunks: Iterable[dict],
    today: date | None = None,
    alpha: float = V3_ALPHA,
    decay_rate: float = V3_DECAY_RATE,
    top_k: int = 5,
) -> list[dict]:
    """Wendet Recency-Re-Ranking auf eine Liste von Chunks an.

    Erwartet, dass jeder Chunk ein Feld `rrf_score` (float) hat.
    Berechnet pro Chunk:
        recency_score = exp(-Δt/decay_rate) bei datierten Chunks, sonst 1.0
        final_score = α · rrf_score + (1-α) · recency_score
    Sortiert nach final_score absteigend und gibt die top_k zurück.

    Args:
        chunks: Chunks mit `rrf_score`.
        today: Referenzdatum. Default: date.today().
        alpha: Gewichtung des RRF-Scores.
        decay_rate: Decay-Rate für Recency-Berechnung.
        top_k: Anzahl der finalen Chunks.

    Returns:
        Liste der Top-K Chunks nach final_score, mit zusätzlichen Feldern
        `recency_score` und `final_score`.
    """
    if today is None:
        today = date.today()

    chunks_list = list(chunks)

    for chunk in chunks_list:
        rrf_score = chunk.get("rrf_score", 0.0)
        recency = _compute_recency_score(chunk, today, decay_rate)
        chunk["recency_score"] = recency
        chunk["final_score"] = alpha * rrf_score + (1.0 - alpha) * recency

    chunks_list.sort(key=lambda c: c["final_score"], reverse=True)

    return chunks_list[:top_k]

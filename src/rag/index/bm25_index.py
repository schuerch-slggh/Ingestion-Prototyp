"""BM25-Index für V2 Hybrid-Retrieval.

Verwendet rank_bm25 (BM25Okapi). Index wird aus den Schlüsselwörtern aller
Chunks aufgebaut und serialisiert in V2_BM25_INDEX_PATH gespeichert.
"""

import logging
import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Einfache Tokenisierung: lowercase, alphanumerische Tokens inkl. Umlaute."""
    return re.findall(r"[a-zäöüß0-9]+", text.lower())


def build_bm25_index(chunks: list[dict], output_path: Path) -> None:
    """Baut BM25-Index aus den Schlüsselwörtern der Chunks und speichert ihn.

    Pro Chunk werden die Schlüsselwörter (kommagetrennter String aus
    metadata["keywords"]) zu einer Token-Liste konvertiert und als
    Dokument im Index verwendet.

    Args:
        chunks: Chunks mit metadata["keywords"] (kommagetrennter String).
        output_path: Pfad zur .pkl-Ausgabedatei.
    """
    documents: list[list[str]] = []
    chunk_ids: list[str] = []

    for chunk in chunks:
        kw_string = chunk["metadata"].get("keywords", "")
        kw_list = [k.strip() for k in kw_string.split(",") if k.strip()]
        tokens = _tokenize(" ".join(kw_list))
        documents.append(tokens)
        chunk_ids.append(chunk["id"])

    bm25 = BM25Okapi(documents)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": chunk_ids}, f)

    logger.info(
        "BM25-Index erstellt: %d Chunks → %s", len(chunks), output_path
    )


def search_bm25(
    query: str, index_path: Path, top_k: int = 5
) -> list[dict]:
    """Sucht im BM25-Index nach Top-K-Treffern.

    Args:
        query: Anfrage-String.
        index_path: Pfad zur .pkl-Datei.
        top_k: Anzahl der Treffer.

    Returns:
        Liste von dicts mit 'chunk_id', 'rank' (1-indexiert), 'score'.
        Chunks mit Score 0 werden ausgeschlossen. Leere Liste wenn
        Index-Datei nicht vorhanden.
    """
    if not index_path.exists():
        logger.warning("BM25-Index nicht gefunden: %s", index_path)
        return []

    with index_path.open("rb") as f:
        data = pickle.load(f)

    bm25: BM25Okapi = data["bm25"]
    chunk_ids: list[str] = data["chunk_ids"]

    query_tokens = _tokenize(query)
    scores = bm25.get_scores(query_tokens)

    top_indices = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    return [
        {
            "chunk_id": chunk_ids[i],
            "rank": rank + 1,
            "score": float(scores[i]),
        }
        for rank, i in enumerate(top_indices)
        if scores[i] > 0
    ]

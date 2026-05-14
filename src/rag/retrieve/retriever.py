"""Retriever: Findet die relevantesten Chunks zu einer Benutzeranfrage.

V0/V1: Embedding-Suche (Cosine-Similarity via ChromaDB).
V2:    Hybrid-Suche (Embedding + BM25 + Reciprocal Rank Fusion).
V3:    V2-Hybrid + Recency-Re-Ranking nach Grofsky (2025).
"""

import logging

from rag.config import (
    TOP_K,
    V2_BM25_INDEX_PATH,
    V3_PRE_RERANK_TOP_K,
    V4_BM25_INDEX_PATH,
)
from rag.index.bm25_index import search_bm25
from rag.index.embeddings import embed_query
from rag.index.vectorstore import get_or_create_collection

logger = logging.getLogger(__name__)

RRF_K_CONSTANT: int = 60  # Glättungs-Parameter nach Cormack et al. (2009)


def retrieve_chunks(
    query: str, variant: str, top_k: int | None = None
) -> list[dict]:
    """Variantenspezifisches Retrieval.

    V0/V1: Embedding-Suche (Cosine-Similarity).
    V2:    Hybrid-Suche (Embedding + BM25 + RRF).

    Args:
        query: Anfrage-Text.
        variant: Pipeline-Variante (z. B. "v0", "v1", "v2").
        top_k: Anzahl abzurufender Chunks. Falls None, TOP_K aus config.py.

    Returns:
        Liste von Chunk-Dicts mit Schlüsseln 'id', 'text', 'metadata',
        'similarity'. V2 ergänzt 'rrf_score' und 'rrf_rank'.
        V3 ergänzt zusätzlich 'recency_score', 'final_score', 'final_rank'.
    """
    k = top_k if top_k is not None else TOP_K
    logger.info(
        "Retrieval: query='%s…', variant=%s, top_k=%d",
        query[:50],
        variant,
        k,
    )
    if variant == "v2":
        return _retrieve_hybrid(query, variant, k)
    if variant == "v3":
        return _retrieve_hybrid_with_recency(query, k)
    if variant == "v4":
        # V4 nutzt Hybrid-Suche wie V2, aber auf dem V4-Index
        return _retrieve_hybrid(query, variant, k)
    return _retrieve_embedding(query, variant, k)


# ── Embedding-Suche ───────────────────────────────────────────────────────────


def _retrieve_embedding(
    query: str, variant: str, top_k: int
) -> list[dict]:
    """Embedding-Suche via ChromaDB (V0/V1/V2-Fallback)."""
    query_embedding = embed_query(query)
    collection = get_or_create_collection(variant)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        chunks.append(
            {
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": round(1.0 - distance, 6),
            }
        )

    if chunks:
        logger.info(
            "%d Chunks abgerufen (top similarity: %.4f)",
            len(chunks),
            chunks[0]["similarity"],
        )
    return chunks


def _load_chunk_by_id(chunk_id: str, variant: str) -> dict:
    """Lädt einen einzelnen Chunk aus ChromaDB anhand der ID.

    Wird für BM25-only-Treffer im Hybrid-Retrieval benötigt.
    """
    collection = get_or_create_collection(variant)
    results = collection.get(
        ids=[chunk_id],
        include=["documents", "metadatas"],
    )
    if not results["ids"]:
        logger.warning("Chunk-ID nicht in ChromaDB gefunden: %s", chunk_id)
        return {
            "id": chunk_id,
            "text": "",
            "metadata": {},
            "similarity": 0.0,
        }
    return {
        "id": results["ids"][0],
        "text": results["documents"][0],
        "metadata": results["metadatas"][0],
        "similarity": 0.0,
    }


# ── Hybrid-Suche (V2) ─────────────────────────────────────────────────────────


def _retrieve_hybrid(
    query: str, variant: str, top_k: int
) -> list[dict]:
    """Hybrid-Retrieval: Embedding + BM25 mit Reciprocal Rank Fusion.

    Führt parallel eine Embedding-Suche (ChromaDB) und eine BM25-Suche aus,
    fusioniert die Resultate über RRF (k=60) und gibt Top-K Chunks zurück.
    """
    # 1. Embedding-Suche
    embed_results = _retrieve_embedding(query, variant, top_k)

    # 2. BM25-Suche (V4 hat eigenen Index, alle anderen nutzen V2-Index)
    bm25_path = V4_BM25_INDEX_PATH if variant == "v4" else V2_BM25_INDEX_PATH
    bm25_results = search_bm25(query, bm25_path, top_k=top_k)

    # 3. RRF-Fusion
    embed_rank_by_id = {r["id"]: i + 1 for i, r in enumerate(embed_results)}
    bm25_rank_by_id = {r["chunk_id"]: r["rank"] for r in bm25_results}

    all_ids = set(embed_rank_by_id) | set(bm25_rank_by_id)

    rrf_scores: dict[str, float] = {}
    for cid in all_ids:
        score = 0.0
        if cid in embed_rank_by_id:
            score += 1.0 / (RRF_K_CONSTANT + embed_rank_by_id[cid])
        if cid in bm25_rank_by_id:
            score += 1.0 / (RRF_K_CONSTANT + bm25_rank_by_id[cid])
        rrf_scores[cid] = score

    # 4. Top-K nach RRF-Score sortieren
    sorted_ids = sorted(
        rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True
    )[:top_k]

    # 5. Chunks zusammenstellen
    embed_lookup = {r["id"]: r for r in embed_results}

    final_chunks: list[dict] = []
    for rank, cid in enumerate(sorted_ids, start=1):
        if cid in embed_lookup:
            chunk = dict(embed_lookup[cid])
        else:
            chunk = _load_chunk_by_id(cid, variant)
        chunk["rrf_score"] = rrf_scores[cid]
        chunk["rrf_rank"] = rank
        final_chunks.append(chunk)

    logger.info(
        "%d Chunks via Hybrid-Retrieval (embed=%d, bm25=%d)",
        len(final_chunks),
        len(embed_results),
        len(bm25_results),
    )
    return final_chunks


# ── V3: Hybrid + Recency-Re-Ranking ──────────────────────────────────────────


def _retrieve_hybrid_with_recency(
    query: str,
    top_k: int,
) -> list[dict]:
    """V3-Retrieval: V2-Hybrid + Recency-Re-Ranking nach Grofsky (2025).

    Holt einen erweiterten Pool (V3_PRE_RERANK_TOP_K) aus dem V2-Hybrid-
    Retriever und re-ranked nach:
        final_score = α · rrf_score + (1-α) · recency_score.

    Args:
        query: Anfrage-Text.
        top_k: Anzahl der finalen Chunks nach Re-Ranking.

    Returns:
        Top-K Chunks nach final_score, mit 'recency_score', 'final_score'
        und 'final_rank'.
    """
    from rag.retrieve.recency_reranker import apply_recency_reranking

    pre_rerank_k = max(V3_PRE_RERANK_TOP_K, top_k)
    candidates = _retrieve_hybrid(query, "v2", pre_rerank_k)

    final_chunks = apply_recency_reranking(candidates, top_k=top_k)

    for rank, chunk in enumerate(final_chunks, start=1):
        chunk["final_rank"] = rank

    logger.info(
        "%d Chunks nach V3-Recency-Re-Ranking (Pool: %d)",
        len(final_chunks),
        len(candidates),
    )
    return final_chunks

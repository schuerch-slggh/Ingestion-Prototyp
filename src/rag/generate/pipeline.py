"""Pipeline: Orchestriert den gesamten Query-Ablauf (Retrieve → Generate).

Verantwortung:
- Retrieval aufrufen
- Prompt bauen
- LLM aufrufen
- Ergebnis mit Metadaten zurückgeben
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from rag.config import EMBEDDING_MODEL, INDEX_DIR, LLM_MODEL, TOP_K
from rag.generate.llm import call_llm
from rag.generate.prompts import build_prompt
from rag.index.embeddings import embed_texts
from rag.index.vectorstore import load_index
from rag.retrieve.retriever import retrieve

logger = logging.getLogger(__name__)


def run_query(query: str, index_dir: Path | None = None) -> dict:
    """Führt eine vollständige RAG-Query aus.

    Gibt ein dict mit query, answer, contexts, retrieved_chunks,
    prompt, timestamp und config zurück.
    """
    logger.info("Pipeline-Query: '%s'", query[:80])

    resolved_index_dir = index_dir if index_dir is not None else INDEX_DIR

    # 1. Index laden
    collection = load_index(resolved_index_dir)

    # 2. Query-Embedding berechnen
    query_embedding = embed_texts([query], EMBEDDING_MODEL)[0]

    # 3. Retrieval
    retrieved = retrieve(query_embedding, collection, TOP_K)

    # 4. Prompt bauen
    context_texts = [r["text"] for r in retrieved]
    messages = build_prompt(query, context_texts)

    # 5. LLM aufrufen
    answer = call_llm(messages, LLM_MODEL)

    # 6. Ergebnis zusammenstellen
    return {
        "query": query,
        "answer": answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contexts": context_texts,
        "retrieved_chunks": [
            {
                "text": r["text"],
                "metadata": r["metadata"],
                "score": r["score"],
            }
            for r in retrieved
        ],
        "prompt": messages,
        "config": {
            "llm_model": LLM_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "top_k": TOP_K,
        },
    }

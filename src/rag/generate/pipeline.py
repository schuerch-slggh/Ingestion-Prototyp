"""Pipeline: Orchestriert Retrieval und Generation für eine Query."""

import logging
from datetime import datetime, timezone

from rag.config import EMBEDDING_MODEL, LLM_MODEL, TOP_K
from rag.generate.llm import call_llm
from rag.generate.prompts import build_messages
from rag.retrieve.retriever import retrieve_chunks

logger = logging.getLogger(__name__)


def answer_query(query: str, variant: str = "v0") -> dict:
    """Vollständige V0-End-to-End-Antwortgenerierung.

    Args:
        query: Anfrage des Nutzers.
        variant: Pipeline-Variante.

    Returns:
        Vollständiges Result-Dict im JSON-Output-Schema.
    """
    logger.info("answer_query: variant=%s, query='%s…'", variant, query[:60])

    chunks = retrieve_chunks(query, variant)
    messages = build_messages(query, chunks)
    answer, stats = call_llm(messages, LLM_MODEL)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "variant": variant,
        "query": query,
        "retrieved_chunks": [
            {
                "id": c["id"],
                "text": c["text"],
                "metadata": c["metadata"],
                "similarity": c["similarity"],
            }
            for c in chunks
        ],
        "answer": answer,
        "metadata": {
            "model": LLM_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "top_k": TOP_K,
            "temperature": 0.0,
            "duration_seconds": stats["duration_seconds"],
            "input_tokens": stats["input_tokens"],
            "output_tokens": stats["output_tokens"],
        },
    }

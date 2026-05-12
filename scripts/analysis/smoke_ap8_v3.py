"""Smoke-Test: V3 Recency-Re-Ranking (AP-8)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.retrieve.retriever import retrieve_chunks

result = retrieve_chunks(
    "Probleme mit dem Tagesabschluss",
    variant="v3",
    top_k=5,
)
print("V3 Top-5:")
for c in result:
    m = c["metadata"]
    src = m.get("source_type", "?")
    d = m.get("post_date") or m.get("processed_date") or "-"
    rank = c["final_rank"]
    rrf = c.get("rrf_score", 0)
    rec = c.get("recency_score", 0)
    fin = c.get("final_score", 0)
    print(f"  Rang {rank}: {c['id']}")
    print(f"    Source: {src}, Datum: {d}")
    print(f"    RRF: {rrf:.4f}, Recency: {rec:.4f}, Final: {fin:.4f}")

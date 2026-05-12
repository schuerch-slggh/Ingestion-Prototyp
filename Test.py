from rag.retrieve.retriever import retrieve_chunks

result = retrieve_chunks('Wie konfiguriere ich die Mehrwertsteuer?', variant='v2', top_k=5)
print(f'Anzahl Chunks: {len(result)}')
for c in result[:3]:
    print(f'  ID: {c["id"]}')
    print(f'  RRF-Rank: {c.get("rrf_rank", "-")}')
    print(f'  RRF-Score: {c.get("rrf_score", 0):.6f}')
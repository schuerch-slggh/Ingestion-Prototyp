"""AP-6.1d smoke test: 10 chunks, retry logic should not trigger."""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rag.index.chunking_v1 import chunk_documents_v1
from rag.index.chunking_v2 import _enrich_with_metadata
from rag.index.keyword_generator import enrich_with_keywords

samples = [
    json.loads(line)
    for line in Path("data/gold/forum.jsonl").open(encoding="utf-8").readlines()[:3]
]
chunks = chunk_documents_v1(samples)[:10]
chunks = _enrich_with_metadata(chunks, samples)
enrich_with_keywords(chunks)

for c in chunks:
    kws = c["metadata"].get("keywords", "")
    print(f"{c['id']}: {kws[:80]}")

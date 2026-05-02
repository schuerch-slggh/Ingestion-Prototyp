"""Tests für Retrieval und Prompt-Aufbau (AP-3.1)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.generate.prompts import build_messages, _SYSTEM_MESSAGE


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _make_chunks(n: int = 5) -> list[dict]:
    """Erstellt n synthetische Chunk-Dicts."""
    return [
        {
            "id": f"handbuch__doc_chunk_{i:04d}",
            "text": f"Dies ist der Inhalt von Chunk {i}.",
            "metadata": {
                "source_type": "handbuch",
                "source_file": f"Handbuch_{i}.pdf",
                "chunk_index": i,
            },
            "similarity": 0.9 - i * 0.05,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_messages_includes_all_chunks() -> None:
    """Alle übergebenen Chunks müssen im User-Content erscheinen."""
    chunks = _make_chunks(5)
    messages = build_messages("Testfrage?", chunks)

    assert len(messages) == 2
    user_content = messages[1]["content"]

    for chunk in chunks:
        assert chunk["text"] in user_content, (
            f"Chunk-Text fehlt im User-Content: {chunk['text'][:40]}"
        )


def test_build_messages_chunk_headers_present() -> None:
    """Jeder Chunk muss mit korrektem Metadaten-Header erscheinen."""
    chunks = _make_chunks(3)
    messages = build_messages("Testfrage?", chunks)
    user_content = messages[1]["content"]

    for chunk in chunks:
        source_file = chunk["metadata"]["source_file"]
        chunk_index = chunk["metadata"]["chunk_index"]
        expected_header = f"[source_file: {source_file}, chunk_index: {chunk_index}]"
        assert expected_header in user_content, (
            f"Metadaten-Header fehlt: {expected_header}"
        )


def test_build_messages_includes_query_at_end() -> None:
    """Die Frage muss nach dem Kontext-Block im User-Content stehen."""
    query = "Wie konfiguriere ich die Mehrwertsteuer?"
    chunks = _make_chunks(2)
    messages = build_messages(query, chunks)
    user_content = messages[1]["content"]

    last_chunk_text = chunks[-1]["text"]
    query_pos = user_content.find(f"Frage: {query}")
    last_chunk_pos = user_content.find(last_chunk_text)

    assert query_pos > -1, "Frage fehlt im User-Content"
    assert query_pos > last_chunk_pos, (
        "Die Frage muss nach dem letzten Chunk stehen"
    )


def test_build_messages_system_includes_citation_instruction() -> None:
    """Die System-Message muss die Anweisung zur Quellenzitation enthalten."""
    messages = build_messages("Testfrage?", _make_chunks(1))

    assert messages[0]["role"] == "system"
    system_content = messages[0]["content"]

    assert "Quelle" in system_content, "Zitations-Anweisung fehlt in System-Message"
    assert "source_file" in system_content, "'source_file' fehlt in Zitations-Format"
    assert "chunk_index" in system_content, "'chunk_index' fehlt in Zitations-Format"


def test_retrieve_chunks_returns_top_k() -> None:
    """Integration-Test: retrieve_chunks gibt TOP_K Chunks zurück (Index nötig)."""
    pytest.importorskip("chromadb")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

    from rag.config import TOP_K, get_variant_index_dir
    index_dir = get_variant_index_dir("v0")

    if not index_dir.exists():
        pytest.skip("V0-Index nicht vorhanden – Test wird übersprungen.")

    from rag.retrieve.retriever import retrieve_chunks
    results = retrieve_chunks("Wie lege ich einen Kunden an?", "v0")

    assert len(results) == TOP_K, f"Erwartet {TOP_K} Chunks, erhalten {len(results)}"
    for r in results:
        assert "id" in r
        assert "text" in r
        assert "metadata" in r
        assert "similarity" in r
        assert 0.0 <= r["similarity"] <= 1.0

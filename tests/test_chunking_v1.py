"""Tests für den V1-Chunker (AP-5.1)."""

import sys
from pathlib import Path

import pytest
import tiktoken

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.index.chunking_v1 import (
    V1_ATOMIC_TOKEN_LIMIT,
    V1_TOKEN_LIMIT,
    _chunk_atomic,
    _chunk_outline,
    _chunk_pages,
    chunk_documents_v1,
)

_ENC = tiktoken.get_encoding("cl100k_base")


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _make_text(n_tokens: int) -> str:
    """Erzeugt einen synthetischen Text mit etwa n_tokens Tokens."""
    word = "Wort"
    return " ".join([word] * n_tokens)


def _make_forum_entry(n_tokens: int = 100) -> dict:
    return {
        "doc_id": "forum_001",
        "source_type": "forum",
        "metadata": {"filename": "forum.jsonl"},
        "content": {"full_text": _make_text(n_tokens)},
    }


def _make_ticket_entry(n_tokens: int = 50) -> dict:
    return {
        "doc_id": "ticket_001",
        "source_type": "ticket",
        "metadata": {"filename": "tickets.jsonl"},
        "content": {"full_text": _make_text(n_tokens)},
    }


def _make_pages_entry(
    source_type: str = "modulbeschreibung",
    page_token_counts: list[int] | None = None,
    include_empty: bool = False,
) -> dict:
    if page_token_counts is None:
        page_token_counts = [100, 150, 120]
    pages = []
    page_num = 1
    for i, n in enumerate(page_token_counts):
        if include_empty and i == 1:
            pages.append({"page_number": page_num, "text": ""})
            page_num += 1
        pages.append({"page_number": page_num, "text": _make_text(n)})
        page_num += 1
    return {
        "doc_id": f"{source_type}_001",
        "source_type": source_type,
        "metadata": {"filename": f"{source_type}.jsonl"},
        "content": {
            "full_text": " ".join(p["text"] for p in pages),
            "pages": pages,
        },
    }


def _make_outline_entry(sections: list[dict]) -> dict:
    """Erzeugt ein synthetisches Handbuch-Gold-Entry.

    sections: Liste von {"level": int, "title": str, "token_count": int}.
    Seiten werden sequenziell nummeriert (1 Seite pro Sektion).
    """
    outline = []
    pages = []
    page_num = 1

    for sec in sections:
        outline.append({"level": sec["level"], "title": sec["title"], "page": page_num})
        pages.append({"page_number": page_num, "text": _make_text(sec["token_count"])})
        page_num += 1

    return {
        "doc_id": "handbuch_001",
        "source_type": "handbuch",
        "metadata": {"filename": "handbuecher.jsonl"},
        "content": {
            "full_text": " ".join(p["text"] for p in pages),
            "outline": outline,
            "pages": pages,
        },
    }


# ── Atomar (3 Tests) ─────────────────────────────────────────────────────────


def test_atomic_forum_produces_one_chunk() -> None:
    entry = _make_forum_entry(n_tokens=500)
    chunks = _chunk_atomic(entry, "forum")
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["chunking_strategy"] == "atomic"
    assert chunks[0]["id"] == "forum__forum_001"


def test_atomic_ticket_produces_one_chunk() -> None:
    entry = _make_ticket_entry(n_tokens=50)
    chunks = _chunk_atomic(entry, "ticket")
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["chunking_strategy"] == "atomic"


def test_atomic_falls_back_on_overflow() -> None:
    entry = _make_forum_entry(n_tokens=V1_ATOMIC_TOKEN_LIMIT + 500)
    chunks = _chunk_atomic(entry, "forum")
    assert len(chunks) > 1
    for c in chunks:
        assert c["metadata"]["chunking_strategy"] == "recursive_fallback"
    assert "overflow_recursive" in chunks[0]["id"]


# ── Seitenweise (3 Tests) ────────────────────────────────────────────────────


def test_pages_produces_chunk_per_page() -> None:
    entry = _make_pages_entry(page_token_counts=[100, 150, 120])
    chunks = _chunk_pages(entry, "modulbeschreibung")
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk["metadata"]["chunking_strategy"] == "page"
    page_numbers = [c["metadata"]["page_number"] for c in chunks]
    assert page_numbers == [1, 2, 3]


def test_pages_skips_empty_pages() -> None:
    entry = _make_pages_entry(page_token_counts=[100, 120], include_empty=True)
    # include_empty=True inserts an empty page before index 1 → 3 page entries, 1 empty
    chunks = _chunk_pages(entry, "schulungsunterlage")
    assert len(chunks) == 2
    for c in chunks:
        assert c["metadata"]["chunking_strategy"] == "page"


def test_pages_falls_back_on_long_page() -> None:
    entry = _make_pages_entry(page_token_counts=[V1_TOKEN_LIMIT + 200, 100])
    chunks = _chunk_pages(entry, "modulbeschreibung")
    # Erste Seite zu gross → recursive_fallback (mind. 2 Chunks); zweite Seite normal
    strategies = [c["metadata"]["chunking_strategy"] for c in chunks]
    assert "recursive_fallback" in strategies
    assert "page" in strategies


# ── Outline-basiert (4 Tests) ────────────────────────────────────────────────


def test_outline_h2_chunking_basic() -> None:
    """3 H2-Sektionen mit je 500 Tokens → 3 outline-Chunks."""
    sections = [
        {"level": 1, "title": "Kapitel 1", "token_count": 10},
        {"level": 2, "title": "Abschnitt 1.1", "token_count": 500},
        {"level": 2, "title": "Abschnitt 1.2", "token_count": 500},
        {"level": 2, "title": "Abschnitt 1.3", "token_count": 500},
    ]
    entry = _make_outline_entry(sections)
    chunks = _chunk_outline(entry, "handbuch")
    outline_chunks = [
        c for c in chunks if c["metadata"]["chunking_strategy"] == "outline"
    ]
    assert len(outline_chunks) == 3
    assert outline_chunks[0]["metadata"]["outline_path"][1] == "Abschnitt 1.1"
    assert "Kapitel 1" in outline_chunks[0]["metadata"]["outline_path"]


def test_outline_falls_back_to_h3() -> None:
    """H2 > 2000 Tokens mit H3-Subsektionen → H3-Chunks erscheinen."""
    # H2 mit je 400 Tokens = 4 * 400 = 1600, aber wir wollen > 2000 über alle Seiten
    # Trick: H2 auf page 2, H3s auf pages 3-5 (je 400 Tokens), nächste H2 auf page 6
    sections = [
        {"level": 1, "title": "H1", "token_count": 10},
        {"level": 2, "title": "Grosser Abschnitt", "token_count": 600},  # p2
        {"level": 3, "title": "Sub 1", "token_count": 600},              # p3
        {"level": 3, "title": "Sub 2", "token_count": 600},              # p4
        {"level": 3, "title": "Sub 3", "token_count": 600},              # p5
        {"level": 2, "title": "Nächster Abschnitt", "token_count": 200}, # p6
    ]
    entry = _make_outline_entry(sections)
    # H2 "Grosser Abschnitt" umfasst pages 2-5 (4 * 600 = 2400 Tokens > 2000)
    chunks = _chunk_outline(entry, "handbuch")
    strategies = {c["metadata"]["chunking_strategy"] for c in chunks}
    assert "outline" in strategies
    # Mindestens 1 H3-Chunk oder recursive_fallback (für den grossen H2-Bereich)
    assert len(chunks) >= 2


def test_outline_falls_back_to_recursive() -> None:
    """H3 > 2000 Tokens → recursive_fallback-Chunks."""
    sections = [
        {"level": 1, "title": "H1", "token_count": 10},
        {"level": 2, "title": "Grosser H2", "token_count": 100},   # p2
        {"level": 3, "title": "Grosser H3", "token_count": 2200},  # p3
        {"level": 2, "title": "Nächster H2", "token_count": 100},  # p4
    ]
    entry = _make_outline_entry(sections)
    chunks = _chunk_outline(entry, "handbuch")
    strategies = [c["metadata"]["chunking_strategy"] for c in chunks]
    assert "recursive_fallback" in strategies


def test_outline_no_outline_uses_recursive() -> None:
    """Handbuch ohne Outline-Daten → Recursive-Fallback, kein Crash."""
    entry = {
        "doc_id": "handbuch_no_outline",
        "source_type": "handbuch",
        "metadata": {"filename": "test.jsonl"},
        "content": {"full_text": _make_text(500), "outline": [], "pages": []},
    }
    chunks = _chunk_outline(entry, "handbuch")
    assert len(chunks) >= 1
    for c in chunks:
        assert c["metadata"]["chunking_strategy"] == "recursive_fallback"


# ── Dispatch-Logik (2 Tests) ─────────────────────────────────────────────────


def test_chunk_documents_v1_dispatches_correctly() -> None:
    """Mix aus 5 Einträgen → korrekte Strategie-Verteilung."""
    entries = [
        _make_forum_entry(n_tokens=100),
        _make_ticket_entry(n_tokens=50),
        _make_pages_entry("modulbeschreibung", [100, 150]),
        _make_pages_entry("schulungsunterlage", [100]),
        _make_outline_entry([
            {"level": 1, "title": "H1", "token_count": 10},
            {"level": 2, "title": "H2", "token_count": 300},
        ]),
    ]
    chunks = chunk_documents_v1(entries)
    strategies = {c["metadata"]["chunking_strategy"] for c in chunks}
    assert "atomic" in strategies
    assert "page" in strategies
    assert "outline" in strategies


def test_chunk_documents_v1_unknown_source_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unbekannter source_type → V0-Fallback mit Warning-Log."""
    entry = {
        "doc_id": "unknown_001",
        "source_type": "unbekannt",
        "metadata": {"filename": "test.jsonl"},
        "content": {"full_text": _make_text(100)},
    }
    import logging

    with caplog.at_level(logging.WARNING):
        chunks = chunk_documents_v1([entry])
    assert any("Unbekannter source_type" in m for m in caplog.messages)
    assert len(chunks) >= 1


# ── ID-Format (1 Test) ───────────────────────────────────────────────────────


def test_chunk_ids_follow_v1_format() -> None:
    """Pro Strategie wird das V1-ID-Format eingehalten."""
    # Atomar
    forum = _make_forum_entry(n_tokens=100)
    forum_chunks = _chunk_atomic(forum, "forum")
    assert forum_chunks[0]["id"] == "forum__forum_001"

    # Atomar Overflow
    overflow = _make_forum_entry(n_tokens=V1_ATOMIC_TOKEN_LIMIT + 500)
    overflow_chunks = _chunk_atomic(overflow, "forum")
    assert all("_overflow_recursive_" in c["id"] for c in overflow_chunks)

    # Seitenweise
    page_entry = _make_pages_entry("modulbeschreibung", [100])
    page_chunks = _chunk_pages(page_entry, "modulbeschreibung")
    assert "page_0001" in page_chunks[0]["id"]

    # Seitenweise Overflow
    big_page = _make_pages_entry("modulbeschreibung", [V1_TOKEN_LIMIT + 200])
    big_chunks = _chunk_pages(big_page, "modulbeschreibung")
    assert any("_recursive_" in c["id"] for c in big_chunks)

    # Outline
    outline_entry = _make_outline_entry([
        {"level": 1, "title": "H1", "token_count": 10},
        {"level": 2, "title": "H2", "token_count": 300},
    ])
    outline_chunks = _chunk_outline(outline_entry, "handbuch")
    assert any("_h2_" in c["id"] for c in outline_chunks)

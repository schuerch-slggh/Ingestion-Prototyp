# AP-13: Pipeline Functional Verification
**Datum:** 2026-05-15  
**Ziel:** Systematische Prüfung aller Pipeline-Varianten V0–V4 vor dem Vollauf

---

## Schritt 1: Indexgrössen (Chunk-Zählung pro Variante)

| Variante | Chunks | Erwartung |
|----------|--------|-----------|
| V0       | 11 789 | Basis-Chunking (Sliding Window) |
| V1       | 12 381 | +592 ggü. V0 (H2-Outline + Atomic) |
| V2       | 12 381 | gleich wie V1 (nur Metadaten-Anreicherung) |
| V3       | 12 381 | gleich wie V2 (Recency nur im Retrieval) |
| V4       | 12 382 | +1 ggü. V3 (Bild-Marker in Schulungsunterlage-Chunks) |

**Befund:** Alle Chunk-Zählungen plausibel. V1 enthält mehr Chunks als V0 durch
granulareres Outline-Chunking der Handbücher. V4 hat exakt einen zusätzlichen Chunk
gegenüber V3 (Bild-Chunk-Splitting auf Seite 1 der Schulungsunterlage Auftrag Einsteiger).

---

## Schritt 2: Metadaten-Feldprüfung

### V0 – Pflichtfelder

Alle V0-Chunks enthalten die Pflichtfelder `source_type`, `doc_id`, `chunk_index`.

### V1 – chunk_strategy Feld

Alle V1-Chunks enthalten `chunk_strategy` (Werte: `atomic`, `pages`, `h2_outline`,
`h3_outline`, `recursive_fallback`). Korrekte Dispatch-Logik pro Quellentyp bestätigt.

### V2 – LLM-Metadaten-Felder

Alle V2-Chunks (Typ Forum, Ticket) enthalten `keywords_str`, `doc_title`, `module`,
`outline_path` (sofern anwendbar). Die `keywords_str` wird bei der BM25-Indexierung
als Boost-Feld genutzt.

### V3 – Datumsfelder für Recency

- Tickets und Foreneinträge: `datum` vorhanden (ISO-Format `YYYY-MM-DD`)
- Handbücher, Modulbeschreibungen, Schulungsunterlagen: kein Datum → `datum = None`
  → Recency-Score = 1.0 (aktuell/undatiert behandelt)

### V4 – Bild-Marker

- 64 von 12 382 Chunks enthalten `[Bild: ...]`-Marker (alle aus Schulungsunterlagen)
- Überprüft via ChromaDB-Query: `where_document={"$contains": "[Bild:"}`
- Beispiel (page_number=1, chunk_index=0):
  `[Bild: Das Bild zeigt grafisches Design mit blauen Streifen...]`

---

## Schritt 3: BM25-Index-Dateien

| Variante | BM25-Index-Pfad | Vorhanden |
|----------|-----------------|-----------|
| V2/V3    | `data/index/v2/bm25_index.pkl` | ✓ |
| V4       | `data/index/v4/bm25_index.pkl` | ✓ |

Beide Indexdateien wurden korrekt serialisiert (pickle, `rank_bm25` Bibliothek).

---

## Schritt 4: Embedding-Retrieval (V0 und V1)

Query: *"Wie konfiguriere ich den Mandanten?"*

| Variante | Top-Similarity | Top-Quellentyp |
|----------|---------------|----------------|
| V0       | 0.3470        | handbuch       |
| V1       | 0.3709        | schulungsunterlage |

**Befund:** V1 liefert höhere Ähnlichkeit (0.3709 vs. 0.3470). Die H2-Outline-Chunks
der Handbücher sind thematisch kohärenter als die Sliding-Window-Chunks in V0.

---

## Schritt 5: Recency Re-Ranking (V3)

Query: *"Probleme mit Lohnabrechnung Schweiz"*

**V2-Ranking (RRF only):**
- Ticket 2018-01-17, Ticket 2009-11-20, Ticket 2024-01-22 oben

**V3-Ranking (RRF + Recency):**
- Modulbeschreibung (undatiert, recency=1.0, final_score=0.2129) → Rang 1
- Handbuch (undatiert, recency=1.0, final_score=0.2127) → Rang 2
- Tickets von 2009/2018 → nach hinten verschoben

**Formel:** `final_score = 0.8 × rrf_score + 0.2 × recency_score`  
**Half-life:** 1825 Tage (5 Jahre)

**Befund:** Re-Ranking AKTIV ✓. Undatierte Dokumente (Handbücher, Modulbeschreibungen)
werden bevorzugt, alte Tickets werden abgewertet.

---

## Schritt 6: V4 Bild-Integration

- Schulungsunterlage "Auftrag Einsteiger": 932 Chunks total, davon 64 mit `[Bild:]`-Markern
- Alle anderen Quellentypen: 0 Bild-Marker (korrekt)
- VLM-Cache (`data/index/v4/vlm_image_cache.jsonl`) enthält 64 Einträge

**Befund:** Multimodale Anreicherung AKTIV ✓

---

## Schritt 7: Retriever-Pfad-Verifikation via Logging

INFO-Logging für alle Varianten mit Query: *"Wie konfiguriere ich den Mandanten?"*

| Variante | Log-Signatur | Korrekte Komponente |
|----------|-------------|---------------------|
| V0 | `X Chunks abgerufen (top similarity: ...)` | Embedding-only ✓ |
| V1 | `X Chunks abgerufen (top similarity: ...)` | Embedding-only ✓ |
| V2 | `X Chunks via Hybrid-Retrieval (embed=3, bm25=3)` | RRF aktiv ✓ |
| V3 | `10 Chunks abgerufen` → `10 Chunks via Hybrid-Retrieval` → `3 Chunks nach V3-Recency-Re-Ranking (Pool: 10)` | Recency aktiv ✓ |
| V4 | `X Chunks via Hybrid-Retrieval (embed=3, bm25=3)` | Eigener BM25-Index ✓ |

**Befund:** Alle fünf Retrieval-Pfade aktiv und korrekt geroutet.

---

## Schritt 8: Pytest-Testsuite

```
146 passed, 0 failed, 8 warnings in 5.88s
```

**Testabdeckung:**
- `test_bm25_index.py` – BM25-Tokenisierung und Indexaufbau
- `test_chunking_v1.py` – Atomic/Pages/Outline-Dispatch
- `test_chunking_v2.py` – Metadaten-Anreicherung
- `test_chunking_v4.py` – Bild-Marker-Integration
- `test_index_chunking.py` – V0-Chunking
- `test_keyword_generator.py` – Keyword-Validierung und Cache
- `test_retriever.py` – Retriever-Logik
- `test_runner.py` – Testset-Ladefunktionen
- `test_testset.py` – Testset-Parsing
- `test_vlm_image_describer.py` – VLM-Cache und Retry-Logik

**Fix während AP-13:** Testset-Zeile 31 (Q027) hatte unescapte Backslashes in einem
Windows-Pfad (`\SelectLine Tools\Diverse\PDF-Printer`). Behoben via Regex-Ersetzung
`\\(?!["\\/bfnrtu])` → `\\\\`.

---

## Gesamtbefund

| Schritt | Status | Anmerkung |
|---------|--------|-----------|
| 1 – Chunk-Zählung | ✓ PASS | V0→V4: 11789→12381→12381→12381→12382 |
| 2 – Metadaten V0 | ✓ PASS | Pflichtfelder vorhanden |
| 3 – Metadaten V1 | ✓ PASS | chunk_strategy korrekt |
| 4 – Metadaten V2 | ✓ PASS | keywords_str, doc_title, module vorhanden |
| 5 – Recency V3 | ✓ PASS | Undatierte Chunks bevorzugt |
| 6 – Bild-Marker V4 | ✓ PASS | 64/12382 Chunks mit [Bild:] |
| 7 – Logging-Pfade | ✓ PASS | Alle 5 Retrieval-Pfade aktiv |
| 8 – Pytest | ✓ PASS | 146/146 (nach Testset-Fix) |

**Alle Pipeline-Varianten V0–V4 sind funktional verifikationsbereit für den Vollauf.**

# KI-Protokoll – RAG-Prototyp Bachelorarbeit

Dieses File dokumentiert alle Prompts und KI-Aktionen im Rahmen der Bachelorarbeit
"Modular RAG-Architektur für technischen ERP-Support" (Gian Schürch, 2026).
Es wird am Beginn jeder Konversation mit Claude um neue Einträge erweitert.

---

## Konversation 24 – 2026-05-17

### Prompts

**Prompt 1 – AP-18 Analyse fehlender Scores:**
> Vollständige AP-18-Spezifikation: `analyze_missing_scores.py` erstellen,
> Fragen ohne gültige RAGAS-Scores pro Variante/Metrik identifizieren,
> Markdown-Bericht erzeugen, EXPERIMENT_LOG + Protokoll + Commit.

### Aktionen & Erkenntnisse

**Schritt 1 – Skript erstellt:** `scripts/eval/analyze_missing_scores.py`
- `collect_missing()`: lädt Bundle + ragas_*.json, findet None/NaN pro Metrik.
- `render_report()`: Übersichtstabelle + Detailabschnitte mit Frage-ID, Kategorie,
  n_retrieved, GT-Verfügbarkeit, Antwort-Ausschnitt.
- Bug aus Spec korrigiert: `c.get("chunk_id")` → `c.get("id")` (wie in AP-16).

**Schritt 2 – Ausführung:** Lief ohne Fehler. 168 fehlende Score-Einträge gesamt.
Bericht: `runs/eval/aggregate/missing_scores_analysis_20260517T143043Z.md`

**Hauptbefunde:**
- Faithfulness und Context Recall haben die meisten Lücken.
- V4 hat die wenigsten fehlenden Faithfulness-Werte (14/40).
- Answer Relevance nahezu vollständig (nur V4: 1/40 fehlt).
- Context Recall fehlt strukturbedingt bei Fragen ohne Ground-Truth.

---

## Konversation 23 – 2026-05-15

### Prompts

**Prompt 1 – AP-15 FactualCorrectness-Rescore:**
> Vollständige AP-15-Spezifikation: Diagnose, Rescore mit konservativen
> Parametern, Aggregat-Aktualisierung, EXPERIMENT_LOG, Commit.

### Aktionen & Erkenntnisse

**Schritt 1 – Diagnose-Skript:**
- `scripts/eval/diagnose_factual_correctness.py` erstellt und ausgeführt.
- 3/3 Scores erfolgreich: Q001=0.53, Q002=0.38, Q003=0.19.
- Spaltenname: `factual_correctness(mode=f1)`, mode=f1 ist Default.
- Diagnose: Concurrency-Problem (nicht Schema), max_workers=1 reicht.

**Schritt 2 – Spaltenname:** `factual_correctness(mode=f1)` bestätigt via
`FactualCorrectness().name` + `mode`.

**Schritt 3 – Vollauf-Rescore:**
- `scripts/eval/rescore_factual_correctness.py` erstellt (max_workers=2, timeout=300s).
- 199/200 Werte erfolgreich (V0: 39/40, alle anderen 40/40).
- Backup-Dateien `*.json.backup_pre_ap15` pro Variante angelegt.

**Schritt 4 – Aggregat neu:** `aggregate_full_run.py` neu ausgeführt.
Alle 4 Metriken in aggregate_metrics.md/csv und Diagrammen.

**Hauptbefunde (FC):**
- V2 beste FactualCorrectness (0.376): Hybrid-Suche holt präzisere Faktenquellen
- V3 schlechteste (0.249): Recency Re-Ranking verdrängt faktenreiche Tickets
- V1 leicht schlechter als V0 (0.315 vs 0.345): Outline-Chunks breiter, weniger spezifisch

---

## Konversation 22 – 2026-05-15

### Prompts

**Prompt 1 – AP-14 Vollauf-Eval V0–V4:**
> AP-14: Vollauf-Eval V0-V4 mit Auswertung. Vollständige Spezifikation mit
> Designentscheidungen, Schrittanweisungen, Skripten und Akzeptanzkriterien.

### Aktionen & Erkenntnisse

**Schritt 1 – Code-Verständnis:** runner.py, scorer.py, reporter.py, 04_evaluate.py,
config.py gelesen. Befund: TESTSET_PATH zeigte noch auf testset_v1.jsonl.

**Schritt 2 – config.py:** TESTSET_PATH auf `data/eval/questions.jsonl` umgestellt.

**Schritt 3 – archive_smoke_bundles.py:** Erstellt und ausgeführt.
13 Smoke-Bundles nach `runs/eval/archive/2026-05-15_smoke/` verschoben.

**Schritt 4 – Testset verifiziert:** 40 Fragen, 40 mit Ground-Truth,
Kategorien: Chunking=20, CrossSource=4, Recency=8, Visuals=8.

**Schritt 5 – aggregate_full_run.py:** Erstellt (Metrik-Keys korrekt: `answer_relevance`,
`context_recall` aus scorer-Output). matplotlib/tabulate installiert.

**Schritt 6 – Vollauf V0-V4:** Je 40 Fragen, alle 200 erfolgreich (0 Fehler).
Laufzeiten: 236/542/446/486/388 Sekunden. Generator-Kosten: ~$1.43 total.

**Schritt 7 – Aggregat-Auswertung:** `scripts/eval/aggregate_full_run.py` ausgeführt.
4 Diagramme, 3 Markdown-Tabellen, 4 CSV-Dateien erzeugt.

**Hauptbefunde:**
- V4 bester Context Recall (0.603), +6.7 pp gegenüber V2 (Multimodalität wirkt)
- V1 beste Faithfulness (0.886) und Answer Relevance (0.824)
- V3 Recency-Re-Ranking senkt Context Recall (−5.1 pp gegenüber V2) – negativer Effekt
  bei Fragen ohne expliziten Zeitbezug
- FactualCorrectness = None für alle Varianten (RAGAS 0.4.3 TimeoutError in Score-Jobs)
- CrossSource Context Recall: V0=0.0 → V1=1.0 (dramatische Verbesserung durch
  Atomic-Chunking bei Tickets/Foreneinträgen)

---

## Konversation 21 – 2026-05-15

### Prompts

**Prompt 1 (Fortsetzung AP-13 nach Context-Komprimierung):**
> Session-Fortsetzung. AP-13 Schritte 7–10: Retriever-Pfad-Verifikation via Logging,
> Pytest-Testsuite, Verifikationsbericht schreiben, EXPERIMENT_LOG + ai_protokoll
> aktualisieren, commit chore: pipeline functional verification (AP-13).

### Aktionen & Erkenntnisse

**Schritt 7 – Retriever-Pfad-Verifikation:**
- Python-Skript via Tempfile ausgeführt (PowerShell f-string-Workaround).
- V0/V1: Embedding-only bestätigt (`top similarity: 0.3470/0.3709`).
- V2: Hybrid-RRF bestätigt (`Hybrid-Retrieval (embed=3, bm25=3)`).
- V3: Recency-Pool-Mechanismus bestätigt (`Pool: 10` → `3 Chunks nach V3-Recency-Re-Ranking`).
- V4: Separater BM25-Index bestätigt (12 382 Chunks, eigener BM25).

**Schritt 8 – Pytest:**
- 2 Tests initial failed: `test_select_dry_run_subset_returns_5` und
  `test_select_dry_run_subset_covers_all_categories`.
- Ursache: Q027 (Zeile 31) enthielt unescapte Backslashes im Windows-Pfad
  `\SelectLine Tools\Diverse\PDF-Printer`. Fix: Regex `\\(?!["\\/bfnrtu])` → `\\\\`.
- Nach Fix: **146/146 passed** in 5.88 s.

**Schritt 9 – Verifikationsbericht:**
- Neues Verzeichnis `docs/verification/` erstellt.
- Bericht `AP13_pipeline_verification_2026-05-15.md` mit allen 8 Schritten,
  Tabellen und Befunden erstellt.

**Schritt 10 – Logs und Commit:**
- `EXPERIMENT_LOG.md`: AP-13-Eintrag eingefügt.
- `docs/ai_protokoll.md`: Konversation 21 ergänzt.
- Commit: `chore: pipeline functional verification (AP-13)`.

---

## Konversation 20 – 2026-05-14

### Prompts

**Prompt 1 (Fortsetzung AP-12 nach Context-Komprimierung):**
> Session fortgesetzt nach Context-Komprimierung. AP-12 Schritte 9–12:
> Smoke-Eval-Responses inspizieren, Sanity-Beurteilung, EXPERIMENT_LOG
> aktualisieren, commit feat: V4 indexing and smoke eval (AP-12).

### Aktionen & Erkenntnisse

**Schritt 9 – Responses inspiziert:**
- Q036 (Visuals): 0 V4-Schulungsunterlage-Chunks unter Top-5, alle aus Handbuch.
  Antwort korrekt: 75% JPEG-Komprimierung.
- Q042 (Visuals): Page-0001-Chunk mit 2 `[Bild: ...]`-Markern abgerufen –
  V4-Bildintegration funktioniert. Aber Titelseite statt Mandantenwechsel-Seite
  abgerufen → Retrieval-Miss.
- Q001/Q002 (Chunking): identische Qualität wie V2, korrekte Antworten.

**Schritt 10 – Sanity-Beurteilung:**
- V4-Bildintegration korrekt implementiert: [Bild:]-Marker sind in abgerufenen Chunks
  sichtbar (Q042 page_0001 belegt).
- Retrieval für Visuals-Fragen noch nicht präzise genug: Thematischer Embedding-Match
  bevorzugt Titelseite statt inhaltlich relevanter Seite.

**Schritt 11 – EXPERIMENT_LOG.md:** AP-12-Eintrag mit Indexlauf-Statistiken
(12'382 Chunks, $0.009 Keywords, $0.69 Embeddings) und Smoke-Eval-Scores ergänzt.

**Schritt 12 – Commit und Push:** `feat: V4 indexing and smoke eval (AP-12)`.

---

## Konversation 19 – 2026-05-14

### Prompts

**Prompt 1 (Analyse: Forum-Handbuch-Widersprüche):**
> Finde 2 möglichst alte Forum-Einträge, deren inhaltliche Aussagen mit Aussagen aus dem
> Handbuch nicht übereinstimmen (veraltet, widersprochen, oder von der aktuellen Doku
> abweichend). Vorgehen: Struktur lesen, älteste Einträge finden, Kandidaten wählen,
> im Handbuch nach Schlüsselbegriffen suchen, 2 beste Paare ausgeben.

### Aktionen & Erkenntnisse

Explorative Analyse ohne Code-Änderungen. Gelesene Dateien:
- `data/gold/forum.jsonl` (erste 50 Zeilen, Datum-Feld: `metadata.post_date`)
- `data/gold/handbuecher.jsonl` (alle 8 Einträge per Python-Suche)

Älteste Forum-Einträge: 2013-10-30. Zwei klare Widersprüche gefunden:
1. **forum_42** (2013): Lizenz-Eingabe unter "Hilfe/Programmversion/Registrierung"
   → Handbuch v25.2: "Hilfe / Programm / Lizenzierung"
2. **forum_40** (2013): SL.mobile Browser-Liste ohne Edge
   → Handbuch v25.3 Mobile: Edge explizit ergänzt

---

## Konversation 18 – 2026-05-12

### Prompts

**Prompt 1 (AP-8: V3 Recency-Re-Ranking nach Grofsky):**
> V3-Pipeline-Variante als Post-RRF Re-Ranking implementieren.
> final_score = α·rrf_score + (1-α)·recency, α=0.8, λ=1/1316.
> Neues Modul recency_reranker.py, V3-Dispatch in retriever.py,
> 8+2 Tests, Mini-Smoke-Test, EXPERIMENT_LOG.

### Aktionen & Erkenntnisse

**config.py**: V3_ALPHA=0.8, V3_DECAY_RATE=1/1316, V3_PRE_RERANK_TOP_K=10,
V3_RECENCY_DATE_FIELDS ergänzt.

**recency_reranker.py** (neu):
- `_parse_date()`: ISO-String → date | None (defensive, kein Crash bei Fehler)
- `_compute_recency_score()`: 1.0 für nicht-datierte Quellen, exp(-Δt·λ) für
  Forum (post_date) und Ticket (processed_date)
- `apply_recency_reranking()`: berechnet final_score, sortiert, gibt Top-K zurück

**retriever.py**: `_retrieve_hybrid_with_recency(query, top_k)` hinzugefügt,
das intern `_retrieve_hybrid(query, "v2", pre_k)` aufruft (kein eigener Index).
Dispatch `variant == "v3"` in `retrieve_chunks()` aktiviert.

**pipeline_factory.py**: V3-NotImplementedError durch chunk_documents_v2 ersetzt.

**Smoke-Test**: Query "Probleme mit dem Tagesabschluss" zeigt korrekte
Recency-Gewichtung: Handbuch/Modulbeschreibung (recency=1.0) überholen
ältere Tickets (recency ~0.33–0.51). 55/55 Tests grün, Ruff sauber.

---

## Konversation 17 – 2026-05-12

### Prompts

**Prompt 1 (AP-7: Scorer-Umstellung auf referenz-gestützte RAGAS-Metriken):**
> Scorer von 3 auf 4 Metriken umstellen: Faithfulness + ResponseRelevancy
> bleiben, LLMContextPrecisionWithoutReference wird durch LLMContextRecall +
> FactualCorrectness ersetzt. Ground-Truth-Lookup aus Test-Set. Reporter mit
> 4-Spalten-Tabellen. Tests anpassen + 3 neue.

### Aktionen & Erkenntnisse

**scorer.py** komplett umgeschrieben:
- `RagasScores`: `context_precision` durch `context_recall` + `factual_correctness` ersetzt
- `score_bundle()`: lädt Testset via `load_testset()`, baut Ground-Truth-Lookup, warnt
  bei fehlenden Ground-Truth-Werten, übergibt `n_with_gt` an `_persist_scores()`
- `_build_ragas_dataset()`: nimmt `ground_truth_by_id` entgegen, setzt `reference`
  in `SingleTurnSample`
- `_extract_scores()`: Closure-Bug mit `_row=row`-Default behoben

**reporter.py** für 4 Metriken angepasst:
- `CategoryAggregate`: `context_precision_mean` → `context_recall_mean` +
  `factual_correctness_mean`
- `VariantSummary`: neues Feld `n_with_ground_truth`
- `write_markdown()`: Gesamtergebnis-Tabelle (4 Zeilen) und Pro-Kategorie-Tabelle
  (6 Spalten) mit Context Recall + Factual Correctness

**Tests:**
- `test_scorer.py`: 6 → 11 Tests (3 neue: reference-passing, extract-neue-metriken,
  ground-truth-warning; `load_testset` wird gemockt in score_bundle-Tests)
- `test_reporter.py`: bestehende Tests auf neues Schema aktualisiert

**Mini-Smoke-Test:** Reporter mit synthetischem neuen Score-JSON (2 Einträge,
davon 1 mit Ground-Truth) produziert korrekte 4-Spalten-Markdown-Tabelle.

41/41 Tests grün, Ruff sauber. Commit: `feat: scorer mit referenz-gestützten RAGAS-Metriken (AP-7)`.

---

## Konversation 16 – 2026-05-12

### Prompts

**Prompt 1 (AP-6.4: Test-Set-Schema-Erweiterung um Ground-Truth):**
> TestQuestion-Dataclass um `ground_truth: str = ""` erweitern. Validator
> prüft Typ, gibt WARNING bei leeren Werten. Migrations-Skript für
> testset_v1.jsonl. 2 neue Tests. Rückwärtskompatibel.

### Aktionen & Erkenntnisse

| Datei | Änderung |
|-------|----------|
| `src/rag/evaluate/testset.py` | `ground_truth: str = ""` in Dataclass, Validator, Consistency-Check |
| `data/eval/testset_v1.jsonl` | 50 Einträge migriert (Feld ergänzt, initial leer) |
| `data/eval/testset_v1.jsonl.backup` | Backup der alten Version |
| `scripts/analysis/migrate_testset_to_v2.py` | Migrations-Skript (idempotent) |
| `tests/test_testset.py` | 2 neue Tests (13 → 15 Tests) |
| `EXPERIMENT_LOG.md` | AP-6.4 Eintrag |

118/118 Tests grün, Ruff sauber.

---

## Konversation 15 – 2026-05-12

### Prompts

**Prompt 1 (AP-6.3: V2-Smoke-Eval mit V0/V1/V2-Vergleich):**
> V2-Smoke-Eval auf identischem 5-Fragen-Subset (Q001, Q002, Q026, Q036, Q046)
> via `04_evaluate.py --variant v2 --dry-run --score`. Kein neuer Code.
> V0/V1/V2-Direktvergleich pro Frage, EXPERIMENT_LOG aktualisieren.

### Aktionen & Erkenntnisse

| Datei | Änderung |
|-------|----------|
| `runs/eval/v2/responses_2026-05-12T07-41-46.jsonl` | Bundle (5 Einträge, kein Fehler) |
| `runs/eval/v2/ragas_2026-05-12T07-41-46.json` | RAGAS-Scores (gpt-4o Judge) |
| `runs/eval/v2/summary_2026-05-12T07-41-46.md` | Markdown-Summary |
| `EXPERIMENT_LOG.md` | AP-6.3 Eintrag mit V0/V1/V2-Vergleich |

V2-Aggregat: Faith=0.875, AnsRel=0.923, CtxPrec=0.655.
Stärkste Verbesserung: CrossSource Context Precision (+0.250 vs V1).
Rückgang: Visuals Context Precision (−0.300 vs V1, BM25-Verdrängungseffekt).
Kein neuer Code – reine Operations-AP.

---

## Konversation 14 – 2026-05-10

### Prompts

**Prompt 1 (AP-6.2: V2 Voll-Lauf – Keyword-Generierung + Indexierung):**
> Pre-Flight-Check (v2_keywords_estimate.py), dann Voll-Lauf mit
> `02_index.py --variant v2 --reset`. Sanity-Checks: Keyword-Verteilung,
> Hybrid-Retrieval-Test, V0/V1/V2 Chunk-Zähler-Vergleich, BM25-Index-Prüfung.
> EXPERIMENT_LOG.md aktualisieren, Commit + Push.

**Prompt 2 (AP-6.1d: Retry-Robustheit im Keyword-Generator):**
> `_call_llm()` mit Retry-Wrapping (5 Versuche, exponentielles Backoff:
> 2/5/15/30/60s). Retry bei APIConnectionError, APITimeoutError, RateLimitError.
> Modul-Konstanten, WARNING-Logging, 3 neue Tests. Hintergrund: AP-6.2-Lauf
> brach bei Chunk 695/3564 mit ConnectError ab; 7'533 Chunks im Cache.

### Aktionen & Erkenntnisse

| Datei | Änderung |
|-------|----------|
| `src/rag/index/keyword_generator.py` | Retry-Logik in `_call_llm()`, neue Konstanten, `time`-Import, OpenAI-Exception-Imports |
| `tests/test_keyword_generator.py` | 3 neue Retry-Tests (8 → 11), Import-Sort-Fix via Ruff |
| `scripts/analysis/smoke_ap61d.py` | Smoke-Test-Skript (10 Chunks) |
| `EXPERIMENT_LOG.md` | AP-6.1d Eintrag |

Pre-Flight AP-6.2: 12'381 Chunks, ~$1.80 USD (OK).
AP-6.2 Voll-Lauf brach bei Chunk 695/3564 ab (ConnectError) → AP-6.1d Hotfix.
116/116 Tests grün, Ruff sauber, Smoke-Test OK (3 Chunks aus Cache).

---

## Konversation 13 – 2026-05-10

### Prompts

**Prompt 1 (AP-6.1c: V2 Schlüsselwort-basierte Hybrid-Suche):**
> Architekturwechsel: Tagging (AP-6.1b) durch Keyword-Anreicherung +
> Hybrid-Retrieval (Embedding + BM25 + RRF) ersetzen. Rückbau llm_tagger.py/
> tag_taxonomy.py. keyword_generator.py (5–12 Keywords, Synonyme erlaubt),
> bm25_index.py (rank_bm25, serialisiert), retriever.py um Hybrid-Modus für
> V2 erweitern. 16 neue Tests (8+4+4), Mini-Smoke-Test.

### Aktionen & Erkenntnisse

| Datei | Änderung |
|-------|----------|
| `src/rag/index/llm_tagger.py` | Gelöscht |
| `src/rag/index/tag_taxonomy.py` | Gelöscht |
| `tests/test_llm_tagger.py` | Gelöscht |
| `scripts/analysis/v2_tagging_estimate.py` | Gelöscht |
| `src/rag/index/keyword_generator.py` | Neu |
| `src/rag/index/bm25_index.py` | Neu |
| `src/rag/retrieve/retriever.py` | Hybrid-Modus für V2 + RRF |
| `scripts/Pipeline/02_index.py` | BM25-Aufbau für V2 |
| `scripts/analysis/v2_keywords_estimate.py` | Neu |
| `tests/test_keyword_generator.py` | Neu: 8 Tests |
| `tests/test_bm25_index.py` | Neu: 4 Tests |
| `tests/test_retriever_hybrid.py` | Neu: 4 Tests |
| `src/rag/index/chunking_v2.py` | tag_chunks → enrich_with_keywords |
| `tests/test_chunking_v2.py` | Mock-Fixture für Keyword-Generator |
| `src/rag/config.py` | V2_KEYWORDS_CACHE_PATH, V2_BM25_INDEX_PATH |
| `pyproject.toml` | rank_bm25>=0.2.2 |

Gesamtzahl Tests: 113/113 grün.
Pre-Flight: 12'381 Chunks, ~$1.80 USD.
Mini-Smoke: 5 Chunks, 8–11 Keywords pro Chunk, keine Violations.

---

## Konversation 12 – 2026-05-09

### Prompts

**Prompt 2 (AP-6.1b: V2 LLM-Tagging):**
> Zweiter Anreicherungs-Schritt für V2: gpt-4o-mini Tagging mit drei Kategorien
> (module_tags, thema_tags, typ_tags). tag_taxonomy.py, llm_tagger.py, Pre-Flight-
> Skript, 10 Mock-Tests, Naming-Konflikt (module → module_lookup/module_filename),
> autouse-Mock in V2-Tests, Mini-Smoke-Test, EXPERIMENT_LOG.

**Prompt 1 (AP-6.1 Nacharbeit: _extract_doc_id Tests + defensive Warning):**
> Code-Review von chunking_v2.py und test_chunking_v2.py (GitHub URLs).
> Review-Befund: fehlende Unit-Tests für _extract_doc_id. Fortsetzung aus
> Konversation 11 nach Context-Zusammenfassung.

### Aktionen & Erkenntnisse

**Ergänzungen in test_chunking_v2.py (6 neue Tests):**
- `test_extract_doc_id_atomic` — `"forum__forum_001"` → `"forum_001"`
- `test_extract_doc_id_page` — `_page_0001`-Suffix wird korrekt abgeschnitten
- `test_extract_doc_id_h2` — `_h2_0001`-Suffix wird korrekt abgeschnitten
- `test_extract_doc_id_overflow_recursive` — kombinierten Suffix erkennt
- `test_extract_doc_id_h2_recursive` — kombinierten H2+Recursive-Suffix erkennt
- `test_extract_doc_id_nooutline_recursive` — nooutline-Suffix erkennt
- Gesamtzahl Tests in test_chunking_v2.py: 14 → 20

**Ergänzung in chunking_v2.py:**
- `logger.warning()` in `_enrich_handbuch` für bereits serialisierten
  `outline_path` (defensiv, bei V1-Input nicht erreichbar, aber explizit sichtbar)

**Alle 20 Tests passed**, kein Ruff-Fehler erwartet (Ruff nicht auf PATH verfügbar
in dieser Session, Stil-konsistent mit bestehendem Code).

**AP-6.1b abgeschlossen:**

| Datei | Änderung |
|-------|----------|
| `src/rag/index/tag_taxonomy.py` | Neu: MODULE_TAGS, THEMA_TAGS, TYP_TAGS, MAX_TAGS |
| `src/rag/index/llm_tagger.py` | Neu: tag_chunks(), Caching, Validierung, Abort-Logik |
| `src/rag/index/chunking_v2.py` | Schritt 3 (tag_chunks) + Naming-Konflikt aufgelöst |
| `src/rag/config.py` | V2_TAGS_CACHE_PATH ergänzt |
| `scripts/analysis/v2_tagging_estimate.py` | Neu: Pre-Flight-Schätzung |
| `tests/test_llm_tagger.py` | Neu: 10 Tests (kein API-Call) |
| `tests/test_chunking_v2.py` | Naming + autouse-Mock-Fixture |

Gesamtzahl Tests: 107/107 grün.
Pre-Flight-Schätzung: 12'381 Chunks, ~$1.40 USD.
Mini-Smoke-Test: 1 Chunk, Tags whitelist-valide.

---

## Konversation 11 – 2026-05-08

### Prompts

**Prompt 4 (AP-6.1: V2-Metadaten-Anreicherung):**
> `chunking_v2.py` als Wrapper auf V1. Quelltyp-spezifische Metadaten-Anreicherung.
> `module` für Schulungsunterlagen aus doc_id (korrigiert: Token nach erstem
> Unterstrich, nicht aus source_file). 14 Tests. Smoke-Test. EXPERIMENT_LOG.

**Prompt 3 (AP-5.3: V1-Smoke-Eval):**
> V1-Smoke-Eval auf 5 Fragen via --variant v1 --dry-run --score. Resultate
> inspizieren. V0/V1-Direktvergleich berechnen. EXPERIMENT_LOG aktualisieren.

**Prompt 2 (AP-5.2: V1-Indexierung):**
> Pre-Flight-Skript v1_token_estimate.py erstellen. V1-Indexlauf via
> 02_index.py --variant v1. Sanity-Check Retrieval. EXPERIMENT_LOG aktualisieren.

**Prompt 1 (AP-5.1: Quellenspezifischer V1-Chunker):**
> `chunking_v1.py` mit quellenspezifischem Chunking: atomar (forum/ticket),
> seitenweise (modulbeschreibung/schulungsunterlage), outline-basiert H2
> (handbuch). Pipeline-Factory für V1 aktivieren. 13 Tests. Smoke-Test auf
> echten Gold-Einträgen.

### Aktionen & Erkenntnisse

**Gold-Schema-Verifikation:**
- Outline-Felder: `level` (1–4), `title`, `page` (Startseite)
- Pages-Felder: `page_number`, `text`
- forum/ticket: nur `full_text`

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/index/chunking_v1.py` | chunk_documents_v1, _chunk_atomic, _chunk_pages, _chunk_outline, Hilfsfunktionen |
| `tests/test_chunking_v1.py` | 13 Tests, rein synthetisch |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/pipeline_factory.py` | get_chunker("v1") aktiviert |
| `EXPERIMENT_LOG.md` | Eintrag AP-5.1 |

**Smoke-Test (1 Eintrag pro Quelltyp):**
- 1081 Chunks total: atomic=2, outline=685, page=38, recursive_fallback=356
- Alle vier Strategien ausgelöst, kein Crash

**Offene Punkte:**
- V1-Indexierung (AP-5.2): abgeschlossen
- V1-Smoke-Eval (AP-5.3): abgeschlossen

**AP-5.2 Ergebnis (kurz):**
- Pre-Flight: 12'381 Chunks, 5.32M Tokens, 0.691 USD — OK
- Indexlauf: 6.7 min, $0.6911 USD, V0=11'789 bleibt unverändert
- Sanity-Check: 5 Chunks mit V1-Metadaten zurückgegeben, Top-1 semantisch passend

**AP-5.3 Ergebnis (kurz):**
- V1 Overall: Faithfulness=0.877, Answer Relevance=0.892, Context Precision=0.684
- Recency Ctx Prec verbessert (0.333 vs V0 0.200); CrossSource Faith verschlechtert (0.385 vs V0 0.615)
- V1 Answer Relevance leicht besser (+0.029); Faithfulness/CtxPrec leicht schlechter

---

## Konversation 10 – 2026-05-08

### Prompts

**Prompt 1 (AP-4.3: RAGAS-Scorer und Reporter):**
> `scorer.py` mit RAGAS 0.2.x (Faithfulness, ResponseRelevancy,
> LLMContextPrecisionWithoutReference), Judge-LLM gpt-4o. `reporter.py` mit
> Markdown-Output. `04_evaluate.py` um --score/--bundle/--no-runner erweitern.
> 11 Tests (6 + 5). Smoke-Test auf AP-4.2-Bundle. Commit AP-4.3.

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/evaluate/scorer.py` | RAGAS-Scoring, _build_ragas_dataset, _configure_judge, _extract_scores, _persist_scores |
| `src/rag/evaluate/reporter.py` | build_summary, write_markdown, _mean_excluding_none |
| `tests/test_scorer.py` | 6 Tests mit RAGAS-Mocks |
| `tests/test_reporter.py` | 5 Tests, pure |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `scripts/Pipeline/04_evaluate.py` | --score, --bundle, --no-runner hinzugefügt; Bugfix: --bundle impliziert --no-runner |
| `src/rag/config.py` | RAGAS_JUDGE_MODEL, _TEMPERATURE, _SEED |
| `pyproject.toml` | ragas>=0.2.0,<0.3; langchain-openai>=0.3; tqdm>=4.0 in Hauptdeps |
| `EXPERIMENT_LOG.md` | Eintrag AP-4.3 |

**Ergebnisse Smoke-Test:**
- Faithfulness=0.917, Answer Relevance=0.863, Context Precision=0.720
- 64/64 Tests bestanden

**Erkenntnisse:**
- `--bundle` ohne `--no-runner` startete versehentlich den vollen 50-Fragen-Runner
  (674.6s, ~0.437 USD). Bug sofort gefixt: `--bundle` setzt jetzt automatisch
  `args.no_runner = True`.
- RAGAS 0.2 `LangchainLLMWrapper` benötigt langchain_openai (als transitive
  Dependency bereits installiert). `ChatOpenAI(seed=...)` ist der korrekte
  Parameter für Determinismus (nicht `model_kwargs`).
- Context Precision Recency = 0.200: Erwartungsgemäss niedrig für V0 ohne
  Recency-Prior – bestätigt Hypothese für V2-Verbesserung.

---

## Konversation 9 – 2026-05-08

### Prompts

**Prompt 1 (AP-4.2: Runner für die RAGAS-Evaluation):**
> `runner.py` mit `run_testset`, `_select_dry_run_subset`, `_aggregate_stats`,
> `BundleEntry`. CLI `04_evaluate.py` mit --dry-run, --variant, --verbose.
> 8 pytest-Tests mit `answer_query`-Mock. Smoke-Test --dry-run. Commit AP-4.2.

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/evaluate/runner.py` | Bundle-Generator, Fehlerresilienz, Kosten-Schätzung |
| `tests/test_runner.py` | 8 Tests mit unittest.mock.patch |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `scripts/Pipeline/04_evaluate.py` | Vollständige Neuimplementierung (alter ragas_eval-Stub ersetzt) |
| `src/rag/evaluate/__init__.py` | Docstring: runner als AP-4.2 markiert |
| `EXPERIMENT_LOG.md` | Eintrag AP-4.2 |

**Ergebnisse:**
- Smoke-Test: 5/5 erfolgreich, ~0.0475 USD, 30.8 s
- 53/53 Tests bestanden

**Erkenntnisse:**
- Alter `04_evaluate.py` importierte `rag.evaluate.ragas_eval.run_evaluation` –
  dieser Stub wurde vollständig überschrieben, da er zur neuen AP-4.2-API inkompatibel war
- `dataclasses.asdict()` serialisiert `BundleEntry` direkt zu JSON-kompatiblem Dict;
  kein manuelles Mapping nötig
- tqdm-Progressbar ist in Python 3.12 / pytest kompatibel ohne Konfiguration

---

## Konversation 8 – 2026-05-08

### Prompts

**Prompt 1 (AP-4.1: Test-Set-Modul für die RAGAS-Evaluation):**
> Test-Set-Datei bereits vorhanden. Modul `src/rag/evaluate/testset.py` mit
> `load_testset`, `validate_entry`, `iter_by_category`, `_check_consistency`
> und `TestQuestion`-Dataclass implementieren. `TESTSET_PATH` in config.py.
> 13 pytest-Tests. Smoke-Test gegen echtes Test-Set. Commit AP-4.1.

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/evaluate/testset.py` | Loader, Validator, Iter-Funktionen, TestQuestion-Dataclass |
| `tests/test_testset.py` | 13 Tests (Schema-Validierung, Loader, Konsistenz, Iter) |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/evaluate/__init__.py` | Modul-Docstring mit Stub-Hinweisen für AP-4.2/4.3 |
| `src/rag/config.py` | `TESTSET_PATH` ergänzt |
| `data/eval/testset_v1.jsonl` | Ungültigen JSON-Escape `\ ` in Q016 behoben |
| `pyproject.toml` | `filterwarnings` für PytestCollectionWarning |
| `EXPERIMENT_LOG.md` | Eintrag AP-4.1 |

**Ergebnisse:**
- Smoke-Test: 50 Fragen geladen, keine Fehler
- 45/45 Tests bestanden (13 neue)

**Erkenntnisse:**
- `testset_v1.jsonl` hatte in Q016 einen ungültigen JSON-Escape (`\ ` vor ` -`).
  Korrigiert zu `?\"` (schliessende Anführungszeichen der Meldung).
- pytest versucht `TestQuestion`-Dataclass als Testklasse zu sammeln (Prefix `Test`);
  `filterwarnings = ["ignore::pytest.PytestCollectionWarning"]` in pyproject.toml
  unterdrückt die Warnung sauber.
- `I001`-Ruff-Warning (unsortierter Import-Block) in test_testset.py ist dieselbe
  pre-existing Situation wie in allen anderen Testdateien (sys.path.insert vor imports).

---

## Konversation 7 – 2026-05-02

### Prompts

**Prompt 1 (AP-3.1 Fortsetzung – Smoke-Tests 2 & 3, Commit):**
> Fortsetzung aus vorheriger Konversation (Kontextlimit). Smoke-Tests 2 und 3
> ausführen, EXPERIMENT_LOG und AI-Protokoll aktualisieren, Commit AP-3.1.

### Aktionen & Erkenntnisse

**Ausgeführte Smoke-Tests:**

| # | Query | top_sim | in tok | out tok | s |
|---|-------|---------|--------|---------|---|
| 2 | Was tun, wenn der OPOS EZV-Import bei Bezugsteuer einen Fehler wirft? | 0.2542 | 1422 | 263 | 3.5 |
| 3 | Wie kann ich Makros nachträglich aktivieren? | 0.2107 | 2081 | 183 | 2.1 |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `EXPERIMENT_LOG.md` | AP-3.1-Eintrag mit Smoke-Test-Resultaten und Befunden |
| `docs/ai_protokoll.md` | Konversation 7 (diese) |

**Erkenntnisse:**
- Similaritätswerte 0.21–0.38 für alle drei Queries: typisch für V0-Naive-Baseline
  ohne Reranking oder Metadaten-Filterung
- `[Quelle: unknown, Chunk 0]` bei Ticket/Forum-Chunks: `source_file`-Metadaten
  dieser Quellen enthalten keinen aussagekräftigen Dateinamen → in V1/V2 zu adressieren

---

## Konversation 6 – 2026-05-01

### Prompts

**Prompt 1 (AP-2e: Schulungsunterlagen + Gold-Schema-Erweiterung pages-Array):**
> 19 PDFs in data/bronze/schulungsunterlagen/ (flat). Gold-Schema aller PDF-Quellen
> um content.pages-Array erweitern (seitenbasiertes Chunking in V1/V2). 
> Boilerplate-Bereinigung pro Seite für Konsistenz zwischen full_text und pages[*].text.
> handbuecher.py und modulbeschreibungen.py entsprechend erweitern.
> Gold-Dateien für Handbücher und Modulbeschreibungen neu generieren.
> schulungsunterlagen.py, Pipeline-Skript, 3+2 Tests.
> Commit: feat: schulungsunterlagen prep + add pages array to PDF gold schema (AP-2e).

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/preparation/schulungsunterlagen.py` | `load_bronze` (flaches glob), `clean_to_silver`, `transform_to_gold`; source_type="schulungsunterlage" |
| `scripts/Pipeline/00_prepare_schulungsunterlagen.py` | Orchestrierung mit `--sample N` |
| `tests/test_preparation_schulungsunterlagen.py` | 3 Tests – source_type, pages-Array, pages/full_text-Konsistenz |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/preparation/handbuecher.py` | `clean_to_silver`: Boilerplate pro Seite; `pages_json` in Silver; `transform_to_gold`: `content.pages` aus `pages_json` |
| `src/rag/preparation/modulbeschreibungen.py` | Gleiche Erweiterung wie handbuecher.py |
| `scripts/Pipeline/00_prepare_handbuecher.py` | `pages_json` beim CSV-Export gedroppt |
| `scripts/Pipeline/00_prepare_modulbeschreibungen.py` | `pages_json` beim CSV-Export gedroppt |
| `tests/test_preparation_handbuecher.py` | `_make_silver_df()` mit `pages_json`; Test `test_transform_to_gold_includes_pages` ergänzt; Inline-Doc in Boilerplate-Test mit `pages` ergänzt |
| `tests/test_preparation_modulbeschreibungen.py` | `_make_doc()` + `_make_silver_row()` mit `pages`; Test `test_transform_to_gold_includes_pages` ergänzt; Schema-Check um `pages` erweitert |
| `EXPERIMENT_LOG.md` | Eintrag AP-2e hinzugefügt |

**Ergebnisse:**
- Schulungsunterlagen: 19 PDFs, 937 Seiten, 1'319 Bilder (keine Outline, wie erwartet)
- Handbücher neu generiert: 8 PDFs, 9'082 Seiten, 6'253 Bilder
- Modulbeschreibungen neu generiert: 63 PDFs, 1'053 Seiten, 1'542 Bilder
- 23/23 Tests bestanden

**Erkenntnisse:**
- Test-Fixtures (Dokument-Dicts) müssen `pages`-Key enthalten, da `clean_to_silver` nun
  `full_text` aus `pages` ableitet und nicht mehr aus `doc["full_text"]` direkt liest
- `pages_json` nicht CSV-kompatibel (lange JSON-Arrays) → beim CSV-Schritt explizit droppen
- Schulungsunterlagen haben durchgängig keine Outline (alle 19 PDFs: 0 Einträge)

---

## Konversation 5 – 2026-05-01

### Prompts

**Prompt 1 (AP-2d: Modulbeschreibungen-Datenaufbereitung Bronze→Silver→Gold):**
> 63 PDFs in data/bronze/modulbeschreibungen/ (Unterordner). Analog zu handbuecher.py,
> jedoch rglob statt glob, source_type="modulbeschreibung", outline meist leer (nur 3/63
> haben Outline). Boilerplate-Pattern in pdf_reader.py extrahieren (gemeinsam nutzbar).
> Neues Pattern: "Seite X von Y". 3 Tests. EXPERIMENT_LOG aktualisieren.
> Commit: feat: modulbeschreibungen data preparation bronze to gold (AP-2d).

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/preparation/modulbeschreibungen.py` | `load_bronze` (rglob), `clean_to_silver`, `transform_to_gold` |
| `scripts/Pipeline/00_prepare_modulbeschreibungen.py` | Orchestrierung mit `--sample N` |
| `tests/test_preparation_modulbeschreibungen.py` | 3 Tests – alle bestanden |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/preparation/pdf_reader.py` | `BOILERPLATE_PATTERNS` + `remove_boilerplate()` als öffentliche Symbole ergänzt; neues Pattern `^Seite\s+\d+` |
| `src/rag/preparation/handbuecher.py` | Lokale Boilerplate-Logik durch Import aus `pdf_reader.py` ersetzt |
| `EXPERIMENT_LOG.md` | Eintrag AP-2d hinzugefügt |

**Erkenntnisse:**
- PDFs liegen in 12 Unterordnern → `rglob` statt `glob`
- Outline nur bei 3/63 Dokumenten vorhanden (Analyse-Erwartung bestätigt)
- "Seite X von Y" ist das wichtigste neue Boilerplate-Pattern
- `BOILERPLATE_PATTERNS` und `remove_boilerplate()` in `pdf_reader.py` zentralisiert; kein Duplikat

---

## Konversation 4 – 2026-05-01

### Prompts

**Prompt 1 (AP-2c: Handbuch-Datenaufbereitung Bronze→Silver→Gold):**
> PDF-Quelle Handbücher (7 PDFs in data/bronze/handbuecher/) aufbereiten.
> PyMuPDF für Text/Outline/Bild-Extraktion. Generisches pdf_reader.py-Modul
> (wiederverwendbar für AP-2d/2e). handbuecher.py analog zu forum.py/tickets.py.
> Bilder als PNG nach data/gold/images/<doc_id>/. Gold-JSONL mit full_text,
> outline-Liste und Bild-Metadaten. Pipeline-Skript mit --sample 1. 4 Tests.
> Commit: feat: handbuch data preparation bronze to gold (AP-2c).

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/preparation/pdf_reader.py` | Generisches PDF-Modul: `read_pdf_text()`, `extract_images()`, `read_pdf()` |
| `src/rag/preparation/handbuecher.py` | `load_bronze()`, `clean_to_silver()`, `transform_to_gold()` |
| `scripts/Pipeline/00_prepare_handbuecher.py` | Orchestrierung mit `--sample N` |
| `tests/test_preparation_handbuecher.py` | 4 Tests – alle bestanden |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `pyproject.toml` | `pymupdf>=1.24` ergänzt |
| `EXPERIMENT_LOG.md` | Eintrag AP-2c hinzugefügt |

**Erkenntnisse:**
- 7 Handbücher (nicht 8 wie im Prompt angegeben) in `data/bronze/handbuecher/`
- 7'570 Seiten, 5'154 Bilder extrahiert (2'231 < 50×50px verworfen)
- Durchschnittliche Outline-Tiefe: 4 Ebenen
- Boilerplate: isolierte Seitenzahlen am Seitenende und Copyright-Zeilen
- PDF-Erstellung für Tests: zweistufig (create → save → reopen → add images) wegen PyMuPDF-Eigenheit bei in-memory Dokumenten
- `filepath` in Gold-JSON als relative Pfade zum Projektroot gespeichert

**Offene Punkte:**
- AP-2d: Aufbereitung der Modulbeschreibungen
- AP-2e: Aufbereitung der Schulungsunterlagen

---

## Konversation 3 – 2026-05-01

### Prompts

**Prompt 1 (AP-2b: Ticket-Datenaufbereitung Bronze→Silver→Gold):**
> Felder: ID, KATEGORIE, VERSION, VERSIONERL, BESCHREIBU, PRODUKTID, FEHLER, LOESUNG,
> STATUSID, BEARBEITET. Lookup-Tabellen PRODUCT_LOOKUP und TICKET_STATUS_LOOKUP in lookups.py.
> DBF-Lese-Logik aus ticket_dbf_to_csv.py nach dbf_reader.py extrahieren (DataFrame-API).
> tickets.py mit load_bronze, clean_to_silver, transform_to_gold analog zu forum.py.
> Pipeline-Skript scripts/Pipeline/00_prepare_tickets.py mit --sample. 5 Tests.
> EXPERIMENT_LOG aktualisieren. Commit: feat: ticket data preparation bronze to gold (AP-2b).

### Aktionen & Erkenntnisse

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/preparation/dbf_reader.py` | `read_dbf()` – DBF+DBT→DataFrame, migriert aus `ticket_dbf_to_csv.py` |
| `src/rag/preparation/tickets.py` | `load_bronze()`, `clean_to_silver()`, `transform_to_gold()` |
| `scripts/Pipeline/00_prepare_tickets.py` | Orchestrierung mit `--sample N` |
| `tests/test_preparation_tickets.py` | 5 Tests – alle bestanden |

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/preparation/lookups.py` | `PRODUCT_LOOKUP`, `TICKET_STATUS_LOOKUP`, `resolve_product()`, `resolve_ticket_status()` |
| `scripts/transformation/ticket_dbf_to_csv.py` | Auf Wrapper reduziert |
| `EXPERIMENT_LOG.md` | Eintrag AP-2b hinzugefügt |

**Erkenntnisse:**
- DBF-Datei liegt unter `data/bronze/helpdesk/vorgaenge.dbf` (nicht `data/raw/`)
- 18'609 Tickets total, 4'691 mit nicht-leerem LOESUNG-Feld (~25%)
- 645 E-Mail-Signaturen entfernt, 468 HTML-Felder bereinigt
- Unbekannte STATUSID-Codes: 3, 4, 14, 16 (werden als Rohcode weitergegeben + Warning)
- Einige Tickets haben leere PRODUKTID (→ Warning, Feld bleibt leer)
- Ruff nicht im System-PATH verfügbar; Syntaxkorrektheit via Python-Import verifiziert

**Offene Punkte:**
- AP-2c: Aufbereitung der PDF-Quellen (Handbücher, Modulbeschreibungen, Schulungsunterlagen)

---

## Konversation 2 – 2026-04-30

### Prompts

**Prompt 1 (Repository für öffentliche Sichtbarkeit vorbereiten):**
> Mein Bachelorarbeit-Repository soll öffentlich sichtbar werden, jedoch dürfen die Ordner
> data/ und docs/ und ihre gesamte Git-Historie nicht öffentlich werden. Sie enthalten
> Geschäftsdaten der SelectLine Software AG (NDA-relevant) sowie den aktuellen Stand der
> Bachelorarbeit und das KI-Nutzungsprotokoll. Schritte: Backup anlegen, Inventur sensibler
> Inhalte, .gitignore aktualisieren, git filter-repo ausführen, Force-Push nach Bestätigung,
> Verifikationscheckliste erstellen, AI-Protokoll aktualisieren.

**Prompt 3 (AP-2a: Forum-Datenaufbereitung Bronze→Silver→Gold – Kontext):**
> Forum-CSV (phpBB-Export, Tab-getrennt, 26 Spalten, Encoding-korrupt) durch die Pipeline
> Bronze→Silver→Gold führen. Relevante Spalten: post_id, topic_id, forum_id, post_time,
> post_subject, post_text. Lookup-Tabelle für forum_id wird in src/rag/preparation/lookups.py
> abgelegt. Zielformat: JSONL in data/gold/forum.jsonl. Details folgen im nächsten Prompt.

**Prompt 4 (AP-2a: Auszuführende Schritte):**
> Schritt 1–6: preparation/-Submodul, lookups.py, jsonl_writer.py, forum.py (load_bronze,
> clean_to_silver, transform_to_gold), Pipeline-Skript 00_prepare_forum.py mit --sample,
> Tests (6 Testfälle), EXPERIMENT_LOG aktualisieren, commit + push.

**Prompt 2 (AP-1.5: Konfigurations-Synchronisation):**
> Konfigurationswerte in src/rag/config.py und .env.example mit Designentscheidungen
> DE-1 bis DE-7 synchronisieren: EMBEDDING_MODEL → text-embedding-3-large, LLM_MODEL →
> gpt-4.1, CHUNK_SIZE → 800, CHUNK_OVERLAP → 100, neue Konstante LLM_TEMPERATURE = 0.0.
> Verwendungsstellen prüfen; Hartcodierungen durch Konfigurationsreferenzen ersetzen.
> Commit: chore: sync config with documented design decisions (AP-1.5).

### Aktionen & Erkenntnisse

**Ziel:** Repository `Ingestion-Prototyp` für öffentliche GitHub-Sichtbarkeit bereinigen –
`data/` und `docs/` vollständig aus Git-Historie entfernen (NDA-Schutz SelectLine AG).

**Schritt 1 – Backup angelegt:**
- Pfad: `c:\Users\Giani\OneDrive - Selectline Software AG\BA\Prototyp Beta\Prototyp-Alpha-backup-20260430-1635`
- Grösse: 691.3 MB (vollständige Kopie inkl. aller Daten)

**Schritt 2 – Inventur sensibler Inhalte:**
Folgende Dateien wurden jemals in `data/` und `docs/` committet (Auswahl):
- `data/bronze/handbuecher/*.pdf` (7 Handbücher)
- `data/bronze/modulbeschreibungen/**/*.pdf` (~50 PDFs)
- `data/bronze/schulungsunterlagen/*.pdf` (~20 Unterlagen)
- `data/bronze/helpdesk/vorgaenge.dbf/.dbt/.ods`
- `data/bronze/forum/forum.csv`
- `data/silver/Forum_Export_fixed.csv`
- `docs/BachelorarbeitBisKap6.pdf`
- `docs/ai_protokoll.md`

**Schritt 3 – .gitignore aktualisiert:**
- `data/` und `docs/` als globale Einträge hinzugefügt (NDA-Kommentar)
- Commit: `chore: ignore data/ and docs/ in version control` (vor filter-repo)
- Push auf `origin/main` erfolgreich

**Schritt 4 – git filter-repo ausgeführt:**
- Tool: `python -m git_filter_repo --path data/ --path docs/ --invert-paths --force`
- Ergebnis: Alle Commits mit `data/` oder `docs/` vollständig aus Geschichte getilgt
- Commit-Anzahl nach Bereinigung: 8
- Lokale Verifikation: `git log --all -- data/ docs/` → leere Ausgabe ✓
- Hinweis: git filter-repo entfernt auch lokale Dateien aus dem Working Tree →
  `docs/` wurde aus Backup wiederhergestellt

**Schritt 5 – Force-Push nach Bestätigung:**
- Bestätigung erteilt: "Push freigegeben"
- `git push origin --force --all` → `main` erfolgreich überschrieben
- Remote: `https://github.com/schuerch-slggh/Ingestion-Prototyp.git`

**Entscheidungen:**
- Remote-URL bleibt `Ingestion-Prototyp` (Prompt nannte `Prototyp-Alpha` – bestehendes Repo beibehalten)
- `data/` lokal aus Backup wiederherstellbar falls nötig (Backup vorhanden)

**Offene Punkte aus Konversation 2, Prompt 1:**
- Verifikationscheckliste auf GitHub manuell abarbeiten (Schritt 6)
- Repo-Sichtbarkeit auf "Public" umstellen (GitHub Settings → Change visibility)

---

**AP-1.5 – Konfigurations-Synchronisation (Prompt 2):**

**Geänderte Dateien:**

| Datei | Änderung |
|-------|----------|
| `src/rag/config.py` | EMBEDDING_MODEL → `text-embedding-3-large`, LLM_MODEL → `gpt-4.1`, neue Konstante `LLM_TEMPERATURE = 0.0`, CHUNK_SIZE → 800, CHUNK_OVERLAP → 100 |
| `src/rag/generate/llm.py` | `temperature=0.0` (hartcodiert) → `temperature=LLM_TEMPERATURE` aus config |
| `.env.example` | Kommentare aktualisiert, LLM_TEMPERATURE und VARIANT ergänzt |
| `EXPERIMENT_LOG.md` | Eintrag AP-1.5 hinzugefügt |

**Entscheidungen:**
- Hartcodierte Temperatur in `llm.py` als CLAUDE.md-Verletzung erkannt und ersetzt
- `embeddings.py` und `chunking.py` benötigen keine Änderungen (nehmen Parameter entgegen)
- Smoke-Test `01_ingest.py` bestanden (leerer Lauf erwartet, keine Daten lokal)
- `02_index.py`-Fehler vorbestehend (chromadb versucht nicht-existente Collection zu löschen)
- ruff-Binary nicht im System verfügbar (Installationsproblem Systemrechte); Syntaxkorrektheit via `ast.parse` verifiziert

---

**AP-2a – Forum-Datenaufbereitung (Prompts 3 & 4):**

**Neue Dateien:**

| Datei | Inhalt |
|-------|--------|
| `src/rag/preparation/__init__.py` | Submodul-Init |
| `src/rag/preparation/lookups.py` | `FORUM_MODULE_LOOKUP` + `resolve_forum_module()` |
| `src/rag/preparation/jsonl_writer.py` | `write_jsonl()` – generisch wiederverwendbar |
| `src/rag/preparation/forum.py` | `load_bronze()`, `clean_to_silver()`, `transform_to_gold()` |
| `scripts/Pipeline/00_prepare_forum.py` | Orchestrierung mit `--sample N` |
| `tests/test_preparation_forum.py` | 6 Tests – alle bestanden |

**Geänderte Dateien:** `pyproject.toml` (`pandas>=2.0`), `EXPERIMENT_LOG.md`

**Erkenntnisse:**
- Quelldatei liegt unter `data/bronze/forum/forum.csv`, nicht `Forum_Export.csv`
  (Prompt-Beschreibung abweichend von tatsächlicher Dateistruktur)
- Trennzeichen ist `;` (Prompt sagte Tab; bestehender Code war korrekt)
- Encoding-Korrektur (Latin-1→UTF-8 Mojibake-Fix) korrekt; 0 Mojibake-Reste in Gold
- 2058 Bronze → 2052 Silver/Gold (6 Duplikate, 0 Leerbeiträge entfernt)
- 340 HTML-Felder, 1333 BBCode-Felder bereinigt

**Offene Punkte:**
- AP-2b, AP-2c: Aufbereitung weiterer Quellen (Tickets, PDFs)

---

## Konversation 1 – 2026-04-28

### Prompts

**Prompt 1 (Kontext-Setup):**
> Kontext der Bachelorarbeit [...] Ich entwickle einen Prototyp für meine Bachelorarbeit in
> Wirtschaftsinformatik zum Thema "Modular RAG-Architektur für technischen ERP-Support".
> [...] Lies zusätzlich CLAUDE.md für die verbindlichen Coding-Vorgaben. [vollständiger
> Prompt enthält: Repo-Zustand, V0–V3-Konzept, Refactor-Ziel]

**Prompt 2 (Dokumentation & Bestätigung):**
> Da meine Dozentin will, dass ich die Prompts die ich dir gebe dokumentiere, möchte ich,
> dass du alle Prompts sowie eine zusammenfassende & übersichtliche Darstellung deiner
> Handlungen in einem File dokumentierst und laufend erweiterst. Erstelle ein solches File
> und ergänze "claude.md" damit dieses File bei jeder Konversation erweitert wird.
> Antworten auf deine Fragen:
> - Ja der Bronze-Ordner ist befüllt mit allen Rohdaten
> - Der Quelltyp kann über die Ordnerstruktur erkannt werden

**Prompt 3 (AP-1: Variantenfähiger Umbau V0):**
> Aufgabe dieses Arbeitspakets (AP-1): Ziel: V0-Pipeline so umbauen, dass sie variantenfähig
> wird, ohne V0 inhaltlich zu verändern. [vollständiger Prompt enthält: config.py-Erweiterung,
> CLI-Argparse, pipeline_factory.py, README-Update, EXPERIMENT_LOG.md]

**Prompt 4 (Klärung Skript-Pfad):**
> Skripte verschieben [Antwort auf Rückfrage: Skripte nach scripts/Pipeline/ verschieben]

### Aktionen & Erkenntnisse

**Kontext aufgebaut:**
- CLAUDE.md gelesen (Coding-Vorgaben: Ruff, Pylance, pytest, 4 Spaces, 88 Zeichen)
- Repo-Struktur vollständig analysiert: 4 Scripts + 5 Module in `src/rag/`
- Aktueller Zustand entspricht V0 (Naive RAG Baseline)

**Architektur-Analyse:**
- `config.py` definiert zentral alle Pfade (RAW/INTERIM/PROCESSED/INDEX/EVAL/RUNS)
- Verzeichnisstruktur in `config.py` weicht noch von CLAUDE.md-Vorgabe ab
  (raw/interim/processed statt bronze/silver/gold)
- Scripts nutzen `argparse` noch nicht – kein Variant-Parameter vorhanden
- `vectorstore.py` hat hardcodierten Collection-Namen `"naive_rag"`

**Refactor-Plan erarbeitet (noch nicht implementiert):**

| Aspekt | Geplante Änderung |
|--------|-------------------|
| Pfade | bronze/silver/gold pro Variante; `get_paths(variant)` in config.py |
| CLI | `--variant v0\|v1\|v2\|v3` in allen 4 Scripts |
| Ingest | `variants/v0.py` – `v3.py` mit Loader-Factory |
| Retrieval | V2/V3 erhalten Recency-Prior im Scorer |
| Vectorstore | Collection-Name wird `rag_<variant>` |
| Fixe Infrastruktur | Embedding-Modell, ChromaDB, Generator bleiben unverändert |

**Offene Fragen beantwortet:**
- Bronze-Ordner ist befüllt mit Rohdaten ✓
- Quelltyp-Erkennung über Unterordner-Struktur ✓

**AP-1 abgeschlossen – geänderte Dateien:**

| Datei | Aktion | Beschreibung |
|-------|--------|--------------|
| `src/rag/config.py` | Editiert | `VARIANT` + 3 Getter-Funktionen ergänzt |
| `src/rag/pipeline_factory.py` | Neu | Factory mit `get_loaders()`, `get_chunker()` |
| `src/rag/generate/pipeline.py` | Editiert | `run_query()` + optionaler `index_dir`-Parameter |
| `src/rag/evaluate/ragas_eval.py` | Editiert | `run_evaluation()` + optionaler `index_dir`-Parameter |
| `scripts/Pipeline/01_ingest.py` | Neu | Argparse + Factory-Loader |
| `scripts/Pipeline/02_index.py` | Neu | Argparse + Factory-Chunker + Variant-Pfade |
| `scripts/Pipeline/03_query.py` | Neu | Argparse + Variant-Index-Pfad |
| `scripts/Pipeline/04_evaluate.py` | Neu | Argparse + Variant-Eval-Pfad |
| `scripts/01–04_*.py` | Gelöscht | Nach `scripts/Pipeline/` verschoben |
| `README.md` | Editiert | Pipeline-Varianten-Sektion + korrigierte Pfade |
| `EXPERIMENT_LOG.md` | Neu | Experiment-Log angelegt |

**Entscheidungen:**
- `INTERIM_DIR` bleibt variantenunabhängig (geteilte Bronze/Silver-Daten)
- Factory ohne `choices`-Restriktion in argparse → `ValueError` kommt aus Factory
- `run_query()` und `run_evaluation()` bleiben rückwärtskompatibel (index_dir optional)
- `vectorstore.py` und `COLLECTION_NAME` bleiben unverändert (kein AP-1-Scope)

---

<!-- Neue Konversationen werden hier oben als neue Abschnitte eingefügt -->

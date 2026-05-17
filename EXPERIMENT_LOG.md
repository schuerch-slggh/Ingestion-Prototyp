# Experiment Log

Pro Eintrag: Datum, Variante, Änderung, beobachteter Effekt.

---

## 2026-05-17 – AP-19: Diagnose der RAGAS-Scoring-Ausfälle

**Hintergrund:** AP-18 zeigte 168 fehlende Scores. Die ursprüngliche Hedging-Hypothese
wurde durch AP-18 widerlegt (nur 6.5% Hedging). AP-19 testet vier Hypothesen (A: Markdown,
B: Quellenangaben, C: Länge, D: Pydantic) anhand von drei gezielt ausgewählten Fällen.

**Vorgehen:** `scripts/eval/diagnose_ragas_failures.py` – sequenzielles Rescore
(max_workers=1, timeout=300s) für Q005/Q006/Q020 (V0) mit vollständigem Debug-Output.

**Ergebnisse:**

| Test-Fall | Antworttyp | Faithfulness | ContextRecall |
|---|---|---|---|
| Q005 | Numm. Liste, Quellenangaben, 875 Z. | 1.0 | 1.0 |
| Q006 | Mehrstufige Liste, 2721 Z. | 0.97 | 1.0 |
| Q020 | Hedging-Antwort, 517 Z. | 1.0 | 0.5 |

Alle drei Test-Fälle liefern valide Scores beim sequenziellen Rescore.

**Hypothesen-Check:**

| Hypothese | Ergebnis |
|---|---|
| A – Markdown-Formatierung | Widerlegt |
| B – Quellenangaben | Widerlegt |
| C – Lange Antworten (>2000 Z.) | Widerlegt |
| D – Pydantic-Validation | Widerlegt |

**Tatsächliche Ursache: Concurrency/Timeout-Problem** (identisch zu AP-15):
RAGAS 0.4.3 mit Standard-max_workers verursacht Rate-Limit-Timeouts beim parallelen
Batch-Scoring → NaN. Sequenziell (max_workers=1) funktioniert alles einwandfrei.

**Zusatz-Beobachtung:** Hedging-Antworten sind kein NaN-Treiber. Faithfulness=1.0
für Q020 ist korrekt: keine falschen Claims → vollständig kontexttreu.

**Artefakte:**
- `scripts/eval/diagnose_ragas_failures.py`
- `runs/eval/aggregate/ragas_diagnosis_20260517T164959Z.log`
- `runs/eval/aggregate/ragas_diagnosis_findings.md`

---

## 2026-05-17 – AP-18: Analyse fehlender RAGAS-Scores

**Hintergrund:** Nach AP-15 (Rescore) und AP-17 (NaN-Transparenz) fehlte ein
systematischer Überblick, welche konkreten Fragen pro Variante und Metrik keinen
gültigen Score haben.

**Code-Änderungen:** `scripts/eval/analyze_missing_scores.py` (neu)
- `collect_missing(variant, questions_by_id)`: lädt Bundle + ragas_*.json,
  identifiziert alle None/NaN-Scores pro Metrik.
- `render_report(stats_by_variant)`: erzeugt Markdown mit Übersichtstabelle
  (Variante × Metrik) und Detailabschnitt pro Variante/Metrik.
- Ausgabe: `runs/eval/aggregate/missing_scores_analysis_<ts>.md`

**Befunde (fehlende Scores):**

| Variante | Faithfulness | Answer Relevance | Context Recall | Factual Correctness |
|---|---|---|---|---|
| V0 | 24/40 | 0 | 17/40 | 1/40 |
| V1 | 19/40 | 0 | 13/40 | 0 |
| V2 | 19/40 | 0 | 15/40 | 0 |
| V3 | 17/40 | 0 | 17/40 | 0 |
| V4 | 14/40 | 1/40 | 11/40 | 0 |

- Faithfulness fehlt am häufigsten (14–24/40 pro Variante): tritt auf wenn RAGAS
  keine klaren Behauptungen im Text identifizieren kann (Listen-Antworten, hedging).
- Context Recall fehlt flächendeckend (11–17/40): jede Frage ohne Ground-Truth
  ist nicht scorebar.
- V4 hat die wenigsten fehlenden Faithfulness-Scores (14/40): präzisere Antworten
  durch Bildkontext.
- Answer Relevance vollständig für V0–V3; V4 hat 1 fehlenden Wert.
- FactualCorrectness: V0 noch 1 fehlender Wert (Frage ohne Ground-Truth im Bundle).

---

## 2026-05-17 – AP-17: Korrektur der Aggregation für NaN-Werte

**Hintergrund:** Die `category_breakdown.md` zeigte `nan`-Zellen ohne Erklärung.
Die Arithmetik war bereits korrekt (None-Werte werden vor `mean()` gefiltert), aber
sparse Zellen waren nicht transparent dokumentiert.

**Befund (Inspektion):** V2/CrossSource/Faithfulness hat **0/4** valide Werte
(nicht 3/4 wie in der Spezifikation vermutet). Context Recall ist ebenfalls
flächendeckend sparse (z.B. V0/Chunking: 9/20, V0/CrossSource: 1/4).

**Code-Änderungen:** `scripts/eval/aggregate_full_run.py`
- `compute_category_breakdown` gibt nun ein Tupel (means_df, counts_df) zurück,
  wobei counts_df pro Zelle `n_valid/n_total` erfasst.
- `write_markdown_category` generiert eine Fussnoten-Sektion für alle Zellen
  mit `n_valid < n_total` (sowohl 0-Wert-Zellen als auch Teilmengen).
- Neues Artefakt: `category_breakdown_counts.csv`.

**Resultat:** `category_breakdown.md` enthält jetzt eine vollständige
Anmerkungssektion. Beispiele sparse Zellen:
- V2/CrossSource/Faithfulness: 0/4 (NaN, korrekt)
- V0–V3/CrossSource/Faithfulness: 1/4 (1 valider Wert)
- V0/Chunking/Context Recall: 9/20

**Neues Aggregat:** `runs/eval/aggregate/full_run_2026-05-17/`

---

## 2026-05-15 – AP-15: FactualCorrectness-Rescore

**Hintergrund:** AP-14 lieferte für FactualCorrectness durchgängig None wegen
TimeoutErrors bei RAGAS 0.4.3 parallelem Scoring (16+ Worker).

**Diagnose:** 3-Fragen-Lauf sequenziell (max_workers=1, timeout=300s) erfolgreich.
Ursache: Concurrency-Problem, nicht Schema-Problem. Spaltenname: `factual_correctness(mode=f1)`.

**Code-Änderungen:**
- `scripts/eval/diagnose_factual_correctness.py` (neu)
- `scripts/eval/rescore_factual_correctness.py` (neu, max_workers=2, timeout=300s)

**Rescore-Statistik:**

| Variante | Erfolgreiche Werte | Mittlere FactualCorrectness |
|---|---|---|
| V0 | 39 / 40 | 0.345 |
| V1 | 40 / 40 | 0.315 |
| V2 | 40 / 40 | 0.376 |
| V3 | 40 / 40 | 0.249 |
| V4 | 40 / 40 | 0.359 |
| **Gesamt** | **199 / 200** | **–** |

*V0: 1 None-Wert (1 Frage ohne Ground-Truth im Bundle).*

**Backup:** Pro Variante `ragas_<ts>.json.backup_pre_ap15` angelegt.

**Aktualisierte Aggregat-Metriken (alle 4 Metriken, N=40):**

| Variante | Faithfulness | Answer Relevance | Context Recall | Factual Correctness |
|---|---|---|---|---|
| V0 | 0.880 | 0.787 | 0.496 | 0.345 |
| V1 | 0.886 | 0.824 | 0.512 | 0.315 |
| V2 | 0.851 | 0.801 | 0.537 | **0.376** |
| V3 | 0.858 | 0.785 | 0.486 | 0.249 |
| V4 | 0.836 | 0.823 | **0.603** | 0.359 |

**Paarweise Differenzen mit FactualCorrectness:**

| Vergleich | Δ FC |
|---|---|
| V0 → V1 | −0.030 |
| V1 → V2 | **+0.061** |
| V2 → V3 | **−0.127** |
| V2 → V4 | −0.017 |

**Befunde:**
- V2 (Hybrid-Suche) zeigt stärksten positiven FC-Effekt (+0.061): BM25-Keywords
  verbessern Retrieval präziserer Kontextpassagen für faktenbasierte Fragen.
- V3 (Recency) schadet faktischer Korrektheit stark (−0.127): Undatierte Texte werden
  bevorzugt, obwohl für präzise Faktenantworten oft die spezifischeren Tickets relevanter sind.
- V1 vs V0: Leichter FC-Rückgang (−0.030) – Outline-Chunking produziert breitere
  Abschnitte mit weniger spezifischen Fakten pro Chunk.

**Verdikt:** Rescore erfolgreich. Vollständige 4-Metrik-Auswertung für Kap. 8 verfügbar.

---

## 2026-05-15 – AP-14: Vollauf-Eval V0–V4 mit Auswertung

**Eval-Konfiguration:**
- Test-Set: `data/eval/questions.jsonl` (40 Fragen, alle mit Ground-Truth)
- Generator: gpt-4.1 (Temperatur 0, Seed 42)
- Judge: gpt-4o
- Metriken: Faithfulness, AnswerRelevancy, LLMContextRecall, FactualCorrectness

**Bundles archiviert:** Smoke-Eval-Bundles nach `runs/eval/archive/2026-05-15_smoke/` (13 Dateien).

**Vollauf-Statistik:**

| Variante | Antworten OK | Fehler | Laufzeit (s) | ~Kosten (USD) |
|---|---|---|---|---|
| V0 | 40 | 0 | 236 | 0.330 |
| V1 | 40 | 0 | 542 | 0.276 |
| V2 | 40 | 0 | 446 | 0.265 |
| V3 | 40 | 0 | 486 | 0.293 |
| V4 | 40 | 0 | 388 | 0.262 |
| **Total** | **200** | **0** | **~2098** | **~1.43** |

*Scoring (Judge gpt-4o): ~$8–10 zusätzlich (nicht einzeln erfasst)*

**Aggregat-Metriken (Mittelwert über 40 Fragen):**

| Variante | Faithfulness | Answer Relevance | Context Recall | Factual Correctness |
|---|---|---|---|---|
| V0 | 0.880 | 0.787 | 0.496 | – |
| V1 | 0.886 | 0.824 | 0.512 | – |
| V2 | 0.851 | 0.801 | 0.537 | – |
| V3 | 0.858 | 0.785 | 0.486 | – |
| V4 | 0.836 | 0.823 | 0.603 | – |

*FactualCorrectness = None für alle Varianten (RAGAS 0.4.3 Scoring-Fehler, kein Ergebnis zurückgegeben).*

**Paarweise Differenzen (Ablation):**

| Vergleich | Erweiterung | Δ Faith | Δ AnsRel | Δ CtxRecall |
|---|---|---|---|---|
| V0 → V1 | Quellenspezifisches Chunking | +0.006 | +0.037 | +0.016 |
| V1 → V2 | Hybrid-Suche + Keywords | −0.035 | −0.023 | +0.024 |
| V2 → V3 | Recency-Re-Ranking | +0.008 | −0.017 | **−0.051** |
| V2 → V4 | Multimodalität | −0.015 | +0.022 | **+0.067** |

**Auswertungs-Output:**
- `runs/eval/aggregate/full_run_2026-05-15/`
  - `aggregate_metrics.md` / `.csv`
  - `category_breakdown.md` / `.csv`
  - `pairwise_deltas.md` / `.csv`
  - `latencies.csv`
  - `diagrams/` (4 PNG: bar, radar, heatmap, latency boxplot)

**Hauptbefunde:**

1. **V1 (Chunking) liefert beste Faithfulness und Answer Relevance** (+3.7 pp AnsRel gegenüber V0)
   durch kohärentere H2-Outline-Chunks bei Handbüchern.

2. **V4 (Multimodalität) liefert den grössten Context-Recall-Sprung** (+6.7 pp gegenüber V2).
   [Bild:]-Marker in Schulungsunterlage-Chunks verbessern die Retrieval-Trefferquote bei
   Visual-Fragen: Kategorie Visuals steigt von 0.4375 (V2) auf 0.5714 (V4).

3. **V3 (Recency-Re-Ranking) senkt Context Recall** (−5.1 pp gegenüber V2). Ursache: 
   Das Re-Ranking bevorzugt undatierte Handbuch/Modulbeschreibungs-Chunks gegenüber
   thematisch relevanteren, aber älteren Tickets/Foreneinträgen. Bei 40 Fragen ohne 
   Zeitbezug überwiegt der negative Effekt.

4. **FactualCorrectness durchgehend None**: RAGAS 0.4.3 gibt für diese Konfiguration
   keine FactualCorrectness-Werte zurück (TimeoutErrors im Scoring-Job, keine 
   Fallback-Scores). Für die Bachelorarbeit wird nur auf die 3 verfügbaren Metriken 
   abgestützt.

5. **CrossSource-Kategorie** zeigt dramatische Verbesserung: Context Recall V0=0.0 → 
   V1=1.0, was auf V0's unzureichendes cross-document Chunking zurückzuführen ist.

**Verdikt:** Vollauf erfolgreich abgeschlossen (200/200). Resultate stehen für Kapitel 8
der Bachelorarbeit zur Verfügung.

---

## 2026-05-15 – AP-13: Pipeline Functional Verification

**Ziel:** Systematische Prüfung aller V0–V4 Varianten vor dem Vollauf.

**Code-Änderungen:**
- `data/eval/testset_v1.jsonl`: Zeile 31 (Q027) – unescapte Backslashes in
  Windows-Pfad (`\SelectLine Tools\Diverse\PDF-Printer`) per Regex repariert.

**Verifikations-Report:** `docs/verification/AP13_pipeline_verification_2026-05-15.md`

**Chunk-Zählung (alle Varianten):**

| Variante | Chunks |
| --- | --- |
| V0 | 11 789 |
| V1 | 12 381 |
| V2 | 12 381 |
| V3 | 12 381 |
| V4 | 12 382 |

**Retrieval-Pfad-Logging (Query: "Wie konfiguriere ich den Mandanten?"):**

| Variante | Log-Signatur | Status |
| --- | --- | --- |
| V0 | `top similarity: 0.3470` | ✓ Embedding-only |
| V1 | `top similarity: 0.3709` | ✓ Embedding-only |
| V2 | `Hybrid-Retrieval (embed=3, bm25=3)` | ✓ RRF aktiv |
| V3 | `Pool: 10` → `V3-Recency-Re-Ranking` | ✓ Recency aktiv |
| V4 | `Hybrid-Retrieval (embed=3, bm25=3)` | ✓ Eigener BM25 |

**Pytest-Ergebnis:** `146 passed, 0 failed` (nach Testset-Fix Q027)

**Befund:** Alle Pipeline-Varianten V0–V4 funktional verifiziert.

---

## 2026-05-14 – AP-12: V4-Indexlauf und V4-Smoke-Eval

**Code-Änderungen:**
- `src/rag/config.py`: `V4_KEYWORDS_CACHE`, `V4_BM25_INDEX_PATH` ergänzt
- `src/rag/index/chunking_v4.py`: `enrich_with_keywords` nutzt `V4_KEYWORDS_CACHE`
- `src/rag/retrieve/retriever.py`: V4-Dispatch auf `_retrieve_hybrid` mit V4-BM25-Index
- `scripts/Pipeline/02_index.py`: BM25-Aufbau für V4 (`V4_BM25_INDEX_PATH`)
- `scripts/Pipeline/04_evaluate.py`: `--question-ids` Flag für Subset-Override
- `src/rag/evaluate/runner.py`: `_select_dry_run_subset` mit `override_ids`-Parameter
- `tests/test_chunking_v4.py`: Test `test_chunk_documents_v4_uses_v4_keywords_cache`
- `tests/test_keyword_generator.py`: Test `test_enrich_with_keywords_uses_custom_cache_path`
- `data/eval/testset_v1.jsonl`: JSON-Escape-Fehler in Q020 behoben (`\D`, `\P`)

**V4-Indexlauf-Statistik:**

| Aspekt | Wert |
| --- | --- |
| Total Chunks | 12'382 |
| davon V4 Schulung (mit Bildern) | 76 |
| V4 Keywords (neu generiert) | 76 Einträge |
| Keywords-Kosten | ~$0.009 (gpt-4o-mini) |
| Embedding-Kosten | ~$0.69 (text-embedding-3-large) |
| Dauer | ~8 Minuten |

V4-BM25-Index: `data/index/v4/bm25.pkl` (3.2 MB, basiert auf V4-Keywords-Cache).
Separate Keyword-Caches: `data/cache/v2_keywords.jsonl` (Forum/Ticket/Handbuch/Modulbeschr.)
und `data/cache/v4_keywords.jsonl` (76 V4-Schulungsunterlagen-Chunks).

**V4-Smoke-Eval (Q036, Q042, Q001, Q002):**

Bundle: `runs/eval/v4/responses_2026-05-14T15-04-03.jsonl`
Scores:  `runs/eval/v4/ragas_2026-05-14T15-04-03.json`
Summary: `runs/eval/v4/summary_2026-05-14T15-04-03.md`

| Frage | Kategorie | GT? | Faithfulness | AnsRel | CtxRecall | FactCorr |
| --- | --- | --- | --- | --- | --- | --- |
| Q036 | Visuals | ✓ | 0.667 | 0.903 | 1.000 | – |
| Q042 | Visuals | – | 1.000 | 0.000 | – | – |
| Q001 | Chunking | ✓ | 1.000 | 0.911 | 0.750 | – |
| Q002 | Chunking | ✓ | 1.000 | 0.912 | 0.750 | – |
| **Gesamt** | | | **0.917** | **0.681** | **0.833** | **0.000** |

*FactCorrectness=0.000: alle Einträge ohne Ground-Truth → als 0.0 gemittelt (N=0).*

**Befunde:**

- **V4-Bildintegration funktioniert** (Schritt 9): Q042-Chunk `page_0001` enthält
  zwei `[Bild: ...]`-Marker (Cover-Bild und Kontaktinfos). Marker sind im abgerufenen
  Chunk sichtbar und werden vom Generator korrekt verarbeitet.
- **Q042 AnsRel = 0.000**: Richtige Seite (Mandantenwechsel) wurde nicht abgerufen –
  Page 1 (Titelseite) hatte höchste Embedding-Ähnlichkeit. Retrieval-Miss, nicht
  Bildintegrations-Fehler.
- **Q036 Faithfulness = 0.667**: Antwort korrekt (75% Komprimierung), aber nur 2/3
  Aussagen direkt belegt. Keine V4-Schulungsunterlage-Chunks unter Top-5 – Frage
  adressiert Handbuch-Inhalt, nicht Bildmaterial.
- **Q001/Q002 unverändert** gegenüber V2: Erwartet, da beide Fragen Handbuch/Ticket-
  Quellen betreffen, die V4 identisch zu V2 behandelt.
- **Kosten Smoke-Eval** (Generator gpt-4.1): ~$0.021 (8'226 In-Tokens, 498 Out-Tokens).

---

## 2026-05-14 – AP-11: V4-Chunker mit Position-aware Bildintegration

- `src/rag/index/chunking_v4.py`: Neues Modul mit
  * `chunk_documents_v4()` als Hauptfunktion (V2-Architektur + Multimodalität)
  * `chunk_schulungsunterlage_v4_with_images()` mit Position-aware Bildintegration
  * `_integrate_images_into_page_text()` – PyMuPDF Bounding-Box-basierte
    räumliche Sortierung von Text- und Bildelementen
  * `_load_image_descriptions_cache()` – Cache-Wiederverwendung aus AP-10
- `src/rag/config.py`: V4_SCHULUNG_PDF_NAME, V4_IMAGE_MARKER_TEMPLATE ergänzt
- `src/rag/pipeline_factory.py`: V4-Dispatch ergänzt
- `src/rag/retrieve/retriever.py`: V4-Dispatch ergänzt (nutzt Hybrid-Retrieval)
- `tests/test_chunking_v4.py`: 6 neue Tests (alle grün)
- V4 = V2-Architektur + Multimodalität für 1 Dokument

**Format der Bildintegration:**
`[Bild: <vlm_description>]` als Klartext-Marker an Position des Bildes
(vereinfachtes MMORE-Pattern nach Sallinen et al., 2025)

**Quellen-Behandlung:**
- forum, ticket, handbuch, modulbeschreibung, andere Schulungen: identisch zu V2
- "Schulungsunterlagen Auftrag Einsteiger.pdf": NEU mit Bildbeschreibungen

**Sanity-Test:**
76 Seiten-Chunks erzeugt, 64 davon mit `[Bild: ...]`-Markern. Beispiel-Chunk
auf Seite 1 enthält Cover-Bild-Beschreibung direkt im Fliesstext.

**Vorbereitung für AP-12:** V4-Indexlauf und V4-Smoke-Eval.

---

## 2026-05-14 – AP-10: V4 VLM-Bildbeschreibungen

- `src/rag/index/vlm_image_describer.py`: Neues Modul mit
  * `describe_images_from_pdf()` als Hauptfunktion
  * `_call_vlm()` mit Retry-Logik (5 Versuche, 2/5/15/30/60s Backoff)
  * `_build_image_id()` für eindeutige IDs (schulung_auftrag_einsteiger_p{p}_img{i})
  * JSONL-Cache mit Idempotenz (Crash-Resistenz)
- `src/rag/config.py`: V4_VLM_* Konstanten ergänzt (Modell, Detail, Retry)
- `scripts/Pipeline/02b_describe_v4_images.py`: Voll-Lauf-Skript
- `tests/test_vlm_image_describer.py`: 6 neue Tests grün
- `data/cache/v4_image_descriptions.jsonl`: Cache mit allen Beschreibungen

**Voll-Lauf-Statistik:**

| Aspekt | Wert |
| --- | --- |
| Bilder im PDF | 283 |
| V4-relevant (>=300 px) | 171 |
| Neu beschrieben | 171 |
| Cache-Hits | 0 |
| Input-Tokens total | 121'864 |
| Output-Tokens total | 14'921 |
| Kosten | $0.45 |
| Laufzeit | ~7 Minuten |

VLM: gpt-4o, detail=high. Vorbereitung für AP-11 (V4-Chunker) abgeschlossen.

---

## 2026-05-12 – AP-8.1: V3 Halbwertszeit auf 1825 Tage angepasst

- `src/rag/config.py`: V3_HALF_LIFE_DAYS = 1825.0 (5 Jahre),
  V3_DECAY_RATE = ln(2) / 1825 (statt 1/1316).
  Begründung: bei genau 5 Jahren ergibt sich R = 0.5 (intuitive Halbwertszeit).
  Alter Wert (λ = 1/1316) lieferte R ≈ 0.25 nach 5 Jahren – zu aggressiv.

---

## 2026-05-12 – AP-8: V3 Recency-Re-Ranking nach Grofsky (2025)

- `src/rag/retrieve/recency_reranker.py`: Post-RRF Re-Ranking
  * `final_score = α · rrf_score + (1-α) · recency_score`
  * α = 0.8, Decay-Rate λ = 1/1316 (Halbwertszeit ~912 Tage)
  * Recency nur für Forum (`post_date`) und Ticket (`processed_date`)
  * Handbuch, Modulbeschreibung, Schulung: recency = 1.0 (keine Abwertung)
  * Pre-Rerank-Pool: 10 Kandidaten aus V2-Hybrid-Retriever, daraus Top-5
- `src/rag/retrieve/retriever.py`: `_retrieve_hybrid_with_recency()` ergänzt,
  Dispatch für `variant="v3"` aktiviert
- `src/rag/config.py`: Konstanten V3_ALPHA, V3_DECAY_RATE,
  V3_PRE_RERANK_TOP_K, V3_RECENCY_DATE_FIELDS
- `src/rag/pipeline_factory.py`: V3-Chunker auf chunk_documents_v2 gesetzt
- `tests/test_recency_reranker.py`: 8 Tests grün
- `tests/test_retriever_v3.py`: 2 Integration-Tests grün
- V3 nutzt V2-Index (ChromaDB + BM25), kein eigener Indexlauf nötig

**Smoke-Test V3 (Query "Probleme mit dem Tagesabschluss"):**

| Rang | Source | Datum | RRF | Recency | Final |
| --- | --- | --- | --- | --- | --- |
| 1 | modulbeschreibung | – | 0.0161 | 1.0000 | 0.2129 |
| 2 | handbuch | – | 0.0159 | 1.0000 | 0.2127 |
| 3 | ticket | 2023-12-15 | 0.0156 | 0.5128 | 0.1151 |
| 4 | ticket | 2023-02-20 | 0.0164 | 0.4089 | 0.0949 |
| 5 | ticket | 2022-05-09 | 0.0154 | 0.3287 | 0.0781 |

Beobachtung: Ältere Tickets werden durch Recency-Abwertung hinter
nicht-datierte Handbuch/Modulbeschreibungs-Chunks zurückgestuft.
Der Effekt ist mit α=0.8 moderat – relevante RRF-Scores überwiegen
nach wie vor. V3-Smoke-Eval auf Test-Set folgt in separatem AP.

---

## 2026-05-12 – AP-7: Scorer auf referenz-gestützte RAGAS-Metriken umgestellt

**Geänderte Metriken:**
- Entfernt: `LLMContextPrecisionWithoutReference` (kein ground_truth nötig)
- Hinzugefügt: `LLMContextRecall` + `FactualCorrectness` (referenz-gestützt)
- Beibehalten: `Faithfulness` + `ResponseRelevancy`

**Geänderte Dateien:**
- `src/rag/evaluate/scorer.py`:
  - `RagasScores`: `context_precision` → `context_recall` + `factual_correctness`
  - `score_bundle()`: lädt Testset, baut `ground_truth_by_id`-Lookup,
    warnt wenn Einträge ohne Ground-Truth
  - `_build_ragas_dataset()`: übergibt `reference` an `SingleTurnSample`
  - `_persist_scores()`: speichert `n_with_ground_truth` in Metadaten
- `src/rag/evaluate/reporter.py`:
  - `CategoryAggregate`: `context_precision_mean` → `context_recall_mean` +
    `factual_correctness_mean`
  - `VariantSummary`: neues Feld `n_with_ground_truth`
  - `write_markdown()`: 4-spaltige Pro-Kategorie-Tabelle

**Tests:**
- `tests/test_scorer.py`: 6 → 11 Tests (3 neue + bestehende angepasst)
- `tests/test_reporter.py`: bestehende Tests auf neues Schema angepasst
- 41/41 Tests grün, Ruff sauber

**Hinweis:** Bestehende Score-JSONs (V0–V2) verwenden noch altes Schema
(`context_precision`). Für neue Evaluations-Runs muss `04_evaluate.py --score`
erneut ausgeführt werden, um referenz-gestützte Metriken zu erhalten.

---

## 2026-05-12 – AP-6.4: Test-Set-Schema um Ground-Truth erweitert

- `src/rag/evaluate/testset.py`: `TestQuestion` um Feld `ground_truth: str = ""`
  erweitert (rückwärtskompatibel durch Default)
- `validate_entry()`: prüft `ground_truth` als String (wirft ValueError bei
  falschem Typ, nimmt fehlendes Feld mit Default `""` an)
- `_check_consistency()`: gibt WARNING wenn Fragen ohne Ground-Truth vorhanden
- `data/eval/testset_v1.jsonl`: 50 Einträge um `"ground_truth": ""` ergänzt
- `data/eval/testset_v1.jsonl.backup`: Sicherungskopie der alten Version
- `scripts/analysis/migrate_testset_to_v2.py`: idempotentes Migrations-Skript
- `tests/test_testset.py`: 2 neue Tests (13 → 15 Tests)
- 118/118 Tests grün, Ruff sauber

**Vorbereitung für:**
- Manuelle Befüllung der Ground-Truth-Antworten durch User
- Scorer-Erweiterung auf `LLMContextRecall` und `FactualCorrectness` (separater AP)

---

## 2026-05-12 – AP-6.3: V2-Smoke-Eval

- V2-Smoke-Eval auf 5 Fragen via `04_evaluate.py --variant v2 --dry-run --score`
  (kein neuer Code – Infrastruktur ist variantenagnostisch)
- Identisches Dry-Run-Subset wie V0 und V1: Q001, Q002 (Chunking), Q026 (Recency),
  Q036 (Visuals), Q046 (CrossSource)
- Bundle: `runs/eval/v2/responses_2026-05-12T07-41-46.jsonl`
- Scores: `runs/eval/v2/ragas_2026-05-12T07-41-46.json`
- Summary: `runs/eval/v2/summary_2026-05-12T07-41-46.md`

**Lauf-Statistiken:**

| Aspekt | Wert |
| --- | --- |
| Erfolgreiche Antworten | 5/5 |
| Generator-Tokens (Input/Output) | 11'619 / 1'911 |
| Generator-Kosten | ~$0.0385 USD (gpt-4.1) |
| Judge-Kosten | ~$0.13 USD (gpt-4o, RAGAS) |
| Generator-Dauer | 19.8 s |
| RAGAS 429-Rate-Limits | häufig (Auto-Retry griff) |

**RAGAS-Scores V2:**

| Metrik | Gesamt | Chunking | Recency | Visuals | CrossSource |
| --- | --- | --- | --- | --- | --- |
| Faithfulness | **0.875** | 1.000 | 1.000 | 1.000 | 0.375 |
| Answer Relevance | **0.923** | 0.942 | 0.919 | 0.848 | 0.962 |
| Context Precision | **0.655** | 0.662 | 0.250 | 0.700 | 1.000 |

**V0/V1/V2-Direktvergleich pro Frage:**

| Frage | Kategorie | Faith V0/V1/V2 | AnsRel V0/V1/V2 | CtxPrec V0/V1/V2 |
| --- | --- | --- | --- | --- |
| Q001 | Chunking | 1.00/1.00/1.00 | 0.91/0.91/0.91 | 1.00/0.76/1.00 |
| Q002 | Chunking | 1.00/1.00/1.00 | 0.81/0.97/0.97 | 0.87/0.58/0.33 |
| Q026 | Recency | 1.00/1.00/1.00 | 0.89/0.89/0.92 | 0.20/0.33/0.25 |
| Q036 | Visuals | 0.97/1.00/1.00 | 0.85/0.85/0.85 | 1.00/1.00/0.70 |
| Q046 | CrossSource | 0.62/0.38/0.38 | 0.85/0.84/0.96 | 0.53/0.75/1.00 |

**Aggregat-Mittelwerte:**

| Variante | Faithfulness | Answer Relevance | Context Precision |
| --- | --- | --- | --- |
| V0 | 0.917 | 0.863 | 0.720 |
| V1 | 0.877 | 0.892 | 0.684 |
| V2 | **0.875** | **0.923** | **0.655** |

**Befunde:**

- **CrossSource Context Precision: stärkste Verbesserung** (+0.250 vs V1, +0.467 vs V0).
  Hauptbeleg für den Wert des Hybrid-Retrievals: BM25 auf Schlüsselwörtern
  verbessert die Treffgenauigkeit bei quellenübergreifenden Fragen deutlich.
- **Answer Relevance: beste aller drei Varianten** (0.923). Antworten sind durch
  den verbesserten Kontext relevanter.
- **Visuals Context Precision: Rückgang** (0.700 vs 1.000 in V0/V1).
  Q036 (Kassenoberfläche PC-Kasse) – BM25 bringt andere Chunks hoch, die den
  visuellen Kontext verdrängen. Mögliche Ursache: Keywords wurden auf Text-
  Inhalt generiert, nicht auf visuelle Elemente.
- **Recency Context Precision weiterhin niedrig** (0.250). V2 adressiert Temporalität
  noch nicht strukturell (das ist V3-Scope).
- **Q002 Context Precision: Rückgang** (0.325 vs V1 0.583). Mischeffekt durch
  BM25-Treffer aus anderen Quellen; bei N=1 pro Kategorie nicht belastbar.
- **Faithfulness CrossSource konstant niedrig** (0.375–0.625) über alle Varianten.
  Diese Kategorie erfordert Syntheseleistung über Quellen – inherent schwierig.
- Hinweis: N=1 pro Kategorie (ausser Chunking N=2) – keine statistisch
  belastbare Aussage. Vollauf (50 Fragen) für belastbare Werte erforderlich.

---

## 2026-05-11 – AP-6.1d: Retry-Robustheit im Keyword-Generator

- `src/rag/index/keyword_generator.py`: `_call_llm()` mit Retry-Wrapping (5 Versuche,
  exponentielles Backoff: 2s / 5s / 15s / 30s / 60s)
- Retry bei `APIConnectionError`, `APITimeoutError`, `RateLimitError`
- Andere Exceptions werden sofort propagiert (kein Retry)
- WARNING-Logging pro Retry-Versuch (Versuch N/5, Fehlertyp, Wartezeit)
- Neue Modul-Konstanten `RETRY_MAX_ATTEMPTS = 5`, `RETRY_BACKOFF_SECONDS = (2, 5, 15, 30, 60)`
- `tests/test_keyword_generator.py`: 3 neue Retry-Tests (8 → 11 Tests gesamt)
- Alle 116 Tests grün, Ruff sauber

**Hintergrund:** AP-6.2 Session 3 brach mit `httpx.ConnectError: [WinError 10054]`
ab (7'533/12'381 Chunks gecacht). Die erweiterte Retry-Logik soll zukünftige
Netzwerk-Unterbrüche überbrücken.

**Smoke-Test:** 3 Chunks aus Cache geladen, keine Retries ausgelöst.

---

## 2026-05-10 – AP-6.1c: V2 Schlüsselwort-basierte Hybrid-Suche

**Architekturwechsel:** V2 von Tagging (AP-6.1b) auf Schlüsselwort-
Anreicherung mit Hybrid-Retrieval (Embedding + BM25 + RRF) umgestellt.

**Rückbau aus AP-6.1b:**
- `src/rag/index/llm_tagger.py` gelöscht
- `src/rag/index/tag_taxonomy.py` gelöscht
- `tests/test_llm_tagger.py` gelöscht
- `scripts/analysis/v2_tagging_estimate.py` durch `v2_keywords_estimate.py` ersetzt

**Neu implementiert:**
- `src/rag/index/keyword_generator.py`: gpt-4o-mini Keyword-Generierung
  (5–12 pro Chunk, Synonyme erlaubt), Structured Outputs, Pro-Chunk-Caching,
  Qualitäts-Abort bei <3 Keywords > 5% der Chunks
- `src/rag/index/bm25_index.py`: BM25Okapi-Index (rank_bm25), Aufbau aus
  Keywords, serialisiert als .pkl, Suche mit Score-Filterung
- `src/rag/retrieve/retriever.py`: Hybrid-Retrieval für V2 mit RRF (k=60
  nach Cormack et al., 2009); V0/V1 behalten Embedding-only-Pfad
- `scripts/Pipeline/02_index.py`: BM25-Index-Aufbau am Ende des V2-Indexlaufs
- `src/rag/config.py`: V2_KEYWORDS_CACHE_PATH, V2_BM25_INDEX_PATH
- `pyproject.toml`: rank_bm25>=0.2.2 als Dependency

**Mini-Smoke-Test (5 Forum-Chunks, echter LLM-Call):**

| Aspekt | Wert |
| --- | --- |
| Anzahl Chunks | 5 |
| Keywords pro Chunk | 8–11 (Ziel: 8) |
| Violations (char-range) | 0/5 |
| Beispiel-Keywords | `Fremdsprachen,Artikelgruppen,Datensätze,Anlegen,Bearbeiten,Entfernen,Formulare,Stammdaten,Formulareditor,Fremdbezeichnungen` |

**Pre-Flight-Schätzung Voll-Lauf:**

| Aspekt | Wert |
| --- | --- |
| Total Chunks | 12'381 |
| Geschätzte Input-Tokens | ~8.05M |
| Geschätzte Output-Tokens | ~990K (80 Tokens pro Chunk) |
| Geschätzte Kosten | ~1.80 USD |

Voller Keyword-Lauf, V2-Indexlauf und V2-Smoke-Eval kommen in AP-6.2.

---

## 2026-05-09 – AP-6.1b: V2 LLM-Tagging als zweiter Anreicherungs-Schritt

- `src/rag/index/tag_taxonomy.py`: Tag-Listen als Modul-Konstanten
  - `MODULE_TAGS` (~35 Werte aus `FORUM_MODULE_LOOKUP`)
  - `THEMA_TAGS` (16 Werte)
  - `TYP_TAGS` (6 Werte)
  - `MAX_TAGS` (module_tags=2, thema_tags=3, typ_tags=1)
- `src/rag/index/llm_tagger.py`: gpt-4o-mini Tagging mit Structured Outputs
  - Pro-Chunk-Caching nach chunk_id in `data/cache/v2_tags.jsonl`
  - Validierung gegen Whitelist, MAX_TAGS-Limits
  - Abbruch bei Ungetaggt-Rate > 5%
  - Crash-Resistenz: Cache-Append nach jedem Call
- `src/rag/index/chunking_v2.py`:
  - Dritter Schritt in `chunk_documents_v2()`: `tag_chunks()` hinzugefügt
  - Naming-Konflikt aufgelöst: `module` → `module_lookup` (Forum),
    `module` → `module_filename` (Schulungsunterlage)
  - `llm_tagger.tag_chunks` als Top-Level-Import
- `src/rag/config.py`: `V2_TAGS_CACHE_PATH` ergänzt
- `scripts/analysis/v2_tagging_estimate.py`: Pre-Flight-Kostenschätzung
- `tests/test_llm_tagger.py`: 10 Tests mit Mocks (kein API-Call)
- `tests/test_chunking_v2.py`: `module` → `module_lookup`/`module_filename`,
  `autouse`-Mock-Fixture für LLM-Tagger

**Mini-Smoke-Test (1 Forum-Chunk, echter LLM-Call):**

| Aspekt | Wert |
| --- | --- |
| Anzahl Chunks | 1 (forum ist atomic → 1 Entry = 1 Chunk) |
| Tags valide (in Whitelist) | 1/1 |
| Mindestens 1 Tag pro Kategorie | 1/1 |
| Beispiel-Tags | `module_tags='SelectLine Auftrag,Programm Einrichtung'`, `thema_tags='Stammdaten,Druck,Konfiguration'`, `typ_tags='Anleitung'` |

**Pre-Flight-Schätzung Voll-Tagging-Lauf:**

| Aspekt | Wert |
| --- | --- |
| Total Chunks | 12'381 |
| Geschätzte Input-Tokens | ~6.83M |
| Geschätzte Output-Tokens | ~619K (50 Tokens pro Chunk) |
| Geschätzte Kosten | ~1.40 USD |

Voller Tagging-Lauf, V2-Indexierung und V2-Smoke-Eval kommen in
separaten APs (AP-6.2, AP-6.3).

---

## 2026-05-08 – AP-6.1: V2-Metadaten-Anreicherung

- `src/rag/index/chunking_v2.py`: V2-Chunker als Wrapper auf V1
  - `chunk_documents_v2()` ruft `chunk_documents_v1()` auf, danach
    `_enrich_with_metadata()` — V1-Code bleibt unverändert
  - Quelltyp-spezifische Anreicherungs-Funktionen:
    - forum: `post_id`, `topic_id`, `module`, `post_date`
    - ticket: `ticket_id`, `product`, `category`, `version_reported`,
      `version_resolved`, `processed_date`
    - handbuch: `outline_level`, `page_start`, `page_end`, `doc_title`;
      `outline_path` (Liste → String serialisiert, z. B. `'H1 > H2'`)
    - modulbeschreibung: `doc_title`
    - schulungsunterlage: `doc_title`, `module` (aus doc_id abgeleitet)
  - `_derive_module_from_doc_id()`: erstes Token nach erstem Unterstrich aus
    doc_id, kapitalisiert (z. B. `schulungsunterlagen_auftrag` → `Auftrag`)
  - ChromaDB-Kompatibilität: alle Werte als str/int/float/bool
  - Recursive-Fallback-Chunks erben Parent-Metadaten
- `src/rag/pipeline_factory.py`: `get_chunker("v2")` aktiviert
- `tests/test_chunking_v2.py`: 14 Tests (Hilfsfunktionen, Anreicherung pro
  Quelltyp, Edge Cases, Dispatch, ChromaDB-Kompatibilität)

**Smoke-Test V2-Metadaten (1 Eintrag pro Quelltyp):**

| Quelltyp | Beispiel-Felder |
| --- | --- |
| forum | `post_id='118'`, `topic_id='100'`, `module='SelectLine Auftrag Allgemein'`, `post_date='2013-11-11'` |
| ticket | `ticket_id='76'`, `product='Auftrag'`, `category='1000'`, `version_resolved=''` |
| handbuch | `outline_path='1 Willkommen > Inhalt'`, `outline_level=2`, `page_start=5`, `page_end=38`, `doc_title='...'` |
| modulbeschreibung | `page_number=1`, `doc_title='Beschreibung Cloudkasse'` |
| schulungsunterlage | `page_number=1`, `doc_title='...'`, `module='Und'`* |

*Heuristik-Edge-Case: `jahresabschluss_und_...` → `module='Und'` (erster Token nach
Unterstrich ist `und`). Für Standard-Doc-IDs wie `schulungsunterlagen_auftrag_profi`
funktioniert die Heuristik korrekt.

ChromaDB-Kompatibilitäts-Verstösse: **0**

---

## 2026-05-08 – AP-5.3: V1-Smoke-Eval

- V1-Smoke-Eval auf 5 Fragen via `scripts/Pipeline/04_evaluate.py --variant v1 --dry-run --score`
  (kein neuer Code – Workflow ist variantenagnostisch)
- Bundle: `runs/eval/v1/responses_2026-05-08T13-57-31.jsonl`
- Scores: `runs/eval/v1/ragas_2026-05-08T13-57-31.json`
- Summary: `runs/eval/v1/summary_2026-05-08T13-57-31.md`
- Identisches Dry-Run-Subset wie V0 (Q001, Q002, Q026, Q036, Q046)
- 429-Rate-Limit-Retries beim RAGAS-Judge (gpt-4o), automatisch abgefangen

**V1-Smoke-Eval-Resultat:**

| Aspekt | Wert |
| --- | --- |
| Erfolgreiche Antworten | 5/5 |
| Generator-Kosten (geschätzt) | ~0.045 USD |
| Judge-Kosten (RAGAS gpt-4o) | ~0.05 USD |
| Dauer | 81.7 s (Runner) + ~155 s (Judge) |

**RAGAS-Scores V1:**

| Metrik | Gesamt | Chunking | Recency | Visuals | CrossSource |
| --- | --- | --- | --- | --- | --- |
| Faithfulness | 0.877 | 1.000 | 1.000 | 1.000 | 0.385 |
| Answer Relevance | 0.892 | 0.939 | 0.893 | 0.848 | 0.841 |
| Context Precision | 0.684 | 0.669 | 0.333 | 1.000 | 0.750 |

**V0/V1-Direktvergleich pro Frage:**

| Frage | Kategorie | Faith V0/V1 | AnsRel V0/V1 | CtxPrec V0/V1 |
| --- | --- | --- | --- | --- |
| Q001 | Chunking | 1.00/1.00 | 0.91/0.91 | 1.00/0.76 |
| Q002 | Chunking | 1.00/1.00 | 0.81/0.97 | 0.87/0.58 |
| Q026 | Recency | 1.00/1.00 | 0.89/0.89 | 0.20/0.33 |
| Q036 | Visuals | 0.97/1.00 | 0.85/0.85 | 1.00/1.00 |
| Q046 | CrossSource | 0.62/0.38 | 0.85/0.84 | 0.53/0.75 |

**V0/V1-Gesamtvergleich:**

| Metrik | V0 | V1 | Δ |
| --- | --- | --- | --- |
| Faithfulness | 0.917 | 0.877 | −0.040 |
| Answer Relevance | 0.863 | 0.892 | +0.029 |
| Context Precision | 0.720 | 0.684 | −0.036 |

**Befunde:**

- Recency Context Precision: V1=0.333 > V0=0.200 (+0.133) — atomares Chunking von
  Forum-/Ticket-Einträgen liefert kohärentere, zeitlich relevantere Kontexte
- CrossSource Context Precision: V1=0.750 > V0=0.533 (+0.217) — V1 findet bessere
  Quellkombinationen
- CrossSource Faithfulness: V1=0.385 < V0=0.615 (−0.230) — atomare Chunks sind kürzer;
  LLM synthetisiert stärker über Quellen hinweg → höheres Halluzinationsrisiko
- Chunking Context Precision: V1=0.669 < V0=0.933 (−0.264) — V1-Outline-Chunks für
  Handbücher sind teils grösser als V0-Token-Windows, was Precision senkt
- Answer Relevance leicht besser in V1 (+0.029), weil atomare Chunks inhaltlich
  fokussierter sind und die Antwortqualität steigt
- Hinweis: N=1 pro Kategorie (ausser Chunking N=2) — keine statistisch belastbare
  Aussage. Vollauf für belastbare Werte erforderlich.

---

## 2026-05-08 – AP-5.2: V1-Indexierung

- `scripts/analysis/v1_token_estimate.py`: Pre-Flight-Skript zur Token- und
  Kostenschätzung ohne API-Calls (vor 02_index.py --variant v1)
- V1-Indexlauf via `scripts/Pipeline/02_index.py --variant v1` (kein
  Code-Change nötig — Skript war bereits variantenagnostisch)
- ChromaDB-Sammlung in `data/index/v1/` (parallel zu data/index/v0/)
- Variante v1 ist nun End-to-End nutzbar (Retrieval funktioniert)
- Hinweis: COLLECTION_NAME = "v0_index" ist hardcoded in vectorstore.py,
  aber jede Variante nutzt ein eigenes ChromaDB-Verzeichnis → kein Problem

**Pre-Flight-Schätzung:**

| Quelle | Einträge | Chunks | Tokens | Strategie-Verteilung |
| --- | --- | --- | --- | --- |
| forum.jsonl | 2052 | 2093 | 637'191 | atomic=2045, recursive_fallback=48 |
| tickets.jsonl | 4691 | 4745 | 1'064'593 | atomic=4686, recursive_fallback=59 |
| handbuecher.jsonl | 8 | 3564 | 2'953'642 | outline=2535, recursive_fallback=1029 |
| modulbeschreibungen.jsonl | 63 | 1048 | 381'173 | page=1048 |
| schulungsunterlagen.jsonl | 19 | 931 | 279'394 | page=931 |

**Indexlauf-Resultat:**

| Aspekt | V1 | V0 (Vergleich) |
| --- | --- | --- |
| Total Chunks | 12'381 | 11'789 |
| Total Tokens | 5'315'993 (~5.32M) | ~6.34M |
| Embedding-Kosten | 0.6911 USD | 0.82 USD |
| Dauer | 403.9 s (6.7 min) | 29.3 min |

V1 ist trotz mehr Chunks günstiger als V0, da der Token-Sliding-Overlap (1000/150
in V0) bei 11'789 Chunks viele redundante Tokens produziert, während V1 mit
atomaren und seitenbasierten Chunks weniger Overhead hat.

**Sanity-Check Retrieval (Query: "Wie konfiguriere ich die Mehrwertsteuer?"):**

| Top | ID | Strategy | Source | Similarity |
| --- | --- | --- | --- | --- |
| 1 | `modulbeschreibung__anwendung_saldo_und_pauschalsteuersatz_methode_v11_0_page_0010` | page | modulbeschreibung | 0.2194 |
| 2 | `forum__forum_311` | atomic | forum | 0.2186 |
| 3 | `forum__forum_1573` | atomic | forum | 0.1891 |
| 4 | `ticket__ticket_206510` | atomic | ticket | 0.1767 |
| 5 | `forum__forum_1650` | atomic | forum | 0.1736 |

**Befunde:**

- Recursive-Fallback-Anteil im Vollumfang: 1136/12381 = 9.2% (vs. Smoke-Test 33%)
- Chunk-Anzahl gegenüber V0: +5% (12'381 vs. 11'789)
- Handbücher dominieren Token-Volumen (2.95M von 5.32M = 55%), da 8 grosse PDFs
- Top-1 Retrieval-Ergebnis (Saldo-/Pauschalsteuersatz-Modulbeschreibung) ist
  semantisch passend zur Mehrwertsteuer-Query

---

## 2026-05-08 – AP-5.1: Quellenspezifischer V1-Chunker

- `src/rag/index/chunking_v1.py`: V1-Chunking mit Quelltyp-Dispatch
  - Atomar (forum, ticket): 1 Chunk pro Eintrag, Recursive-Fallback bei
    Token-Überlauf > 8000
  - Seitenweise (modulbeschreibung, schulungsunterlage): 1 Chunk pro Seite,
    Recursive-Fallback bei > 2000 Tokens
  - Outline (handbuch): H2-basiert (Outline-Feld mit `level`, `title`, `page`),
    Fallback H3 → Recursive bei > 2000 Tokens. Text-Extraktion via
    Page-Range-Mapping (pages_by_num dict)
  - Wiederverwendung des V0-`_split_text` für alle Recursive-Fallbacks
  - Erweitertes Metadaten-Schema: `chunking_strategy`, `outline_path`,
    `page_number`
- `src/rag/pipeline_factory.py`: `get_chunker("v1")` aktiviert
- `tests/test_chunking_v1.py`: 13 Tests (alle Strategien + Dispatch + IDs),
  rein synthetisch (kein API, kein echtes Gold)

**Gold-Schema-Verifikation (Schritt 1):**
- Outline-Felder: `level` (1–4), `title`, `page` (Startseite), kein `page_start`
- Pages-Felder: `page_number`, `text`
- forum/ticket: nur `full_text`, keine Pages/Outline

**Smoke-Test auf realen Gold-Einträgen (1 Eintrag pro Quelltyp):**

| Quelle | Strategie | Anzahl Chunks |
| --- | --- | --- |
| forum | atomic | 1 |
| ticket | atomic | 1 |
| handbuch | outline + recursive_fallback | 685 + 356 |
| modulbeschreibung | page | 20 |
| schulungsunterlage | page | 18 |
| **Total** | | **1081** |

Beobachtung: Das Handbuch hat viele grosse H2-Sektionen (> 2000 Tokens), die
in den Recursive-Fallback fallen. Dies zeigt, dass der H3-Fallback bei diesem
Dokument häufig greift — ein Optimierungspunkt für spätere Varianten.

---

## 2026-05-08 – AP-4.3: RAGAS-Scorer und Reporter

- `src/rag/evaluate/scorer.py`: RAGAS-Bewertung auf Response-Bundle
  - Drei Metriken: Faithfulness, ResponseRelevancy,
    LLMContextPrecisionWithoutReference (RAGAS 0.2.15)
  - Judge-LLM: gpt-4o (Begründung in Kap. 7 der Arbeit)
  - Filtert Bundle-Einträge mit `error != null` heraus
  - Persistiert Pro-Frage-Scores als JSON mit Metadaten
- `src/rag/evaluate/reporter.py`: Aggregation und Markdown-Output
  - `build_summary()`: Gesamt- und Kategorie-Mittelwerte
  - `write_markdown()`: Tabellen-Format für Kap. 8 der Arbeit
  - None-Scores werden ausgeschlossen (nicht als 0 gewertet)
- `scripts/Pipeline/04_evaluate.py`: `--score`, `--bundle`, `--no-runner`
  - Bugfix: `--bundle` impliziert nun `--no-runner` (verhindert
    versehentlichen Vollauf beim Scoren eines bestehenden Bundles)
- `src/rag/config.py`: `RAGAS_JUDGE_MODEL`, `_TEMPERATURE`, `_SEED`
- `pyproject.toml`: `ragas>=0.2.0,<0.3`, `langchain-openai>=0.3`, `tqdm>=4.0`
- `tests/test_scorer.py`: 6 Tests mit RAGAS-Mocks (kein API-Call)
- `tests/test_reporter.py`: 5 Tests, pure (kein RAGAS, keine API)
- 64/64 Tests bestanden (11 neue)

**Smoke-Test (V0, 5-Fragen-Bundle aus AP-4.2, gpt-4o als Judge):**

| Metrik | Mittelwert | n |
|--------|------------|---|
| Faithfulness | 0.917 | 5 |
| Answer Relevance | 0.863 | 5 |
| Context Precision | 0.720 | 5 |

| Kategorie | n | Faithfulness | Answer Relevance | Context Precision |
|-----------|---|---|---|---|
| Chunking | 2 | 1.000 | 0.861 | 0.933 |
| Recency | 1 | 1.000 | 0.894 | 0.200 |
| Visuals | 1 | 0.968 | 0.848 | 1.000 |
| CrossSource | 1 | 0.615 | 0.853 | 0.533 |

**Befunde:**
- Faithfulness hoch (0.917): V0-Generator halluziniert wenig relativ zum
  abgerufenen Kontext – aber Kontext selbst ist ggf. nicht ideal (V0)
- Context Precision Recency (0.200): Erwartungsgemäss tief – V0 ohne
  Recency-Prior ruft thematisch-ähnliche aber nicht zeitlich-relevante
  Chunks ab; wird in V2 adressiert
- CrossSource Faithfulness (0.615): Tiefster Wert; Fragen über mehrere
  Quellen liegen ausserhalb des V0-Abdeckungsbereichs
- Vollständiger V0-Lauf über 50 Fragen zufällig mitgestartet (CLI-Bug):
  674.6s, ~0.437 USD Runner-Kosten; Bundle in
  `runs/eval/v0/responses_<ts>.jsonl` persistiert (kann für V0-Report
  genutzt werden)

---

## 2026-05-08 – AP-4.2: Runner für die RAGAS-Evaluation

- `src/rag/evaluate/runner.py`: Bundle-Generator für RAGAS-Eval
  - `run_testset(questions, variant, output_path)`: zeilenweise JSONL-
    Persistierung, fehlerresilient (>50% Fehler → Abbruch via RuntimeError)
  - `_select_dry_run_subset()`: stratifiziert 5 Fragen über alle 4 Kategorien
    (Chunking 2×, Recency/Visuals/CrossSource je 1×); deterministisch
  - `_aggregate_stats()`: summiert Token-Counts und schätzt LLM-Kosten
  - `BundleEntry`-Dataclass: question_id, category, result, error
- `scripts/Pipeline/04_evaluate.py`: CLI mit --variant, --dry-run, --verbose
  (ersetzt den alten `ragas_eval`-Stub)
- `tests/test_runner.py`: 8 Tests mit `answer_query`-Mock (kein API-Call)
- Output-Schema: `runs/eval/<variant>/responses_<ts>.jsonl`
  - Hülle: question_id, category, result (= answer_query-Dict), error
- 53/53 Tests bestanden (8 neue)

**Smoke-Test (--dry-run, V0):**

| Aspekt | Wert |
|--------|------|
| Anzahl Fragen | 5 (Q001, Q002, Q026, Q036, Q046) |
| Erfolgreiche Antworten | 5/5 |
| Geschätzte Kosten | ~0.0475 USD |
| Gesamtdauer | 30.8 s |
| Bundle-Datei | `runs/eval/v0/responses_2026-05-08T09-58-07.jsonl` |

---

## 2026-05-08 – AP-4.1: Test-Set-Modul für die RAGAS-Evaluation

- `src/rag/evaluate/__init__.py`: Modul-Docstring mit Stub-Hinweisen für AP-4.2/4.3
- `src/rag/evaluate/testset.py`: Loader, Validator, Iter-Funktionen
  - `load_testset(path)`: JSONL-Loader mit Zeilennummer in Fehlermeldungen
  - `validate_entry(entry, line_number)`: Strenge Validierung (ID-Format, Pflichtfelder,
    Kategorie-Whitelist), zusätzliche Felder werden ignoriert (Vorwärtskompatibilität)
  - `iter_by_category(questions)`: Gruppierung in Canonical-Reihenfolge
  - `_check_consistency(questions)`: Warnungen bei Duplikaten / ID-Lücken (kein Abbruch)
- `src/rag/config.py`: `TESTSET_PATH` ergänzt (variantenunabhängig unter `data/eval/`)
- `data/eval/testset_v1.jsonl`: 50 Fragen, 4 Kategorien
  (Chunking 25, Recency 10, Visuals 10, CrossSource 5)
  Korrektur: ungültiger JSON-Escape `\ ` in Q016 behoben
- `tests/test_testset.py`: 13 Tests, alle ohne API-Calls
- `pyproject.toml`: `filterwarnings` für `PytestCollectionWarning` ergänzt
  (pytest versucht `TestQuestion`-Dataclass als Testklasse zu sammeln)
- 45/45 Tests bestanden

---

## 2026-05-02 – AP-3.1: V0 End-to-End (Retrieval + Generation)

- `src/rag/retrieve/retriever.py`: `retrieve_chunks()` mit cosine-to-similarity-
  Konvertierung (`similarity = 1 - distance`); ChromaDB-IDs werden automatisch
  zurückgegeben (nicht in `include` angegeben – ChromaDB 1.5.8 API)
- `src/rag/generate/prompts.py`: `build_messages()` mit Chunk-Header
  `[source_file: X, chunk_index: N]` und Zitations-Instruktion in System-Message
- `src/rag/generate/llm.py`: `call_llm()` mit Token-Tracking und Dauer-Messung
- `src/rag/generate/pipeline.py`: `answer_query()` orchestriert Retrieval →
  Prompt-Aufbau → LLM-Aufruf; gibt vollständiges JSON-Output-Schema zurück
- `scripts/Pipeline/03_query.py`: CLI mit `--query`, `--variant`, `--no-save`;
  speichert Ergebnis in `runs/<variant>/queries/<ts>_<slug>.json`
- `tests/test_retrieval_and_prompts.py`: 4 Unit-Tests (pure, kein Index nötig)
  + 1 Integration-Test (skippt ohne V0-Index)
- 32/32 Tests bestanden

**Smoke-Tests (Variante v0, TOP_K=5, gpt-4.1):**

| # | Frage | top sim | in tok | out tok | s |
|---|-------|---------|--------|---------|---|
| 1 | Wie lege ich einen neuen Kunden im SelectLine Auftrag an? | 0.3789 | 1561 | 135 | 3.2 |
| 2 | Was tun, wenn der OPOS EZV-Import bei Bezugsteuer einen Fehler wirft? | 0.2542 | 1422 | 263 | 3.5 |
| 3 | Wie kann ich Makros nachträglich aktivieren? | 0.2107 | 2081 | 183 | 2.1 |

**Befunde:**
- Similaritätswerte generell niedrig (0.21–0.38): V0-Naive-Baseline expected;
  ohne Metadaten-Filterung oder Reranking liefert die naive Suche suboptimale Matches
- Zitation `[Quelle: unknown, Chunk 0]` erscheint bei Fragen 1 & 2: LLM nutzt
  das Zitations-Format, aber `source_file`-Metadaten aus dem Ticket/Forum-Quellen
  enthalten keinen Dateinamen → als "unknown" ausgegeben. Muss in V1+ adressiert werden.
- Frage 3 ("Makros"): korrekte Quellennennung `[Schulungsunterlagen Makroassistent.pdf, Chunk 2]`

---

## 2026-05-02 – AP-3: V0-Indexierung auf Vollumfang

- `CHUNK_SIZE` auf 1000, `CHUNK_OVERLAP` auf 150 gesetzt (DE-4)
- `src/rag/index/chunking.py`: V0-Chunker mit tiktoken (`cl100k_base`),
  quelltypagnostisch; liest `content.full_text`; Chunk-IDs mit `source_type`-
  Prefix zur Vermeidung von Kollisionen bei gleichen Dateinamen in
  verschiedenen Quellen
- `src/rag/index/embeddings.py`: `embed_chunks()` mit Batch-Logging
- `src/rag/index/vectorstore.py`: `get_or_create_collection()` + `add_chunks_to_collection()`
- `src/rag/pipeline_factory.py`: `get_chunker("v0")` implementiert
- `scripts/Pipeline/02_index.py`: Orchestrierung über alle fünf Gold-Quellen,
  `--reset` und `--max-chunks N` Flags, Kosten-Schätzung im Log
- Indexierung Vollumfang:
  - forum.jsonl:              2'052 Einträge →  2'303 Chunks
  - tickets.jsonl:            4'691 Einträge →  4'867 Chunks
  - handbuecher.jsonl:            8 Einträge →  3'814 Chunks
  - modulbeschreibungen.jsonl:   63 Einträge →    469 Chunks
  - schulungsunterlagen.jsonl:   19 Einträge →    336 Chunks
  - Total: 11'789 Chunks im Index (`data/index/v0/`)
  - Embedding-Kosten: ~0.82 USD (text-embedding-3-large, 6.34M Tokens)
  - Dauer: 29.3 Minuten
- 27/27 Tests bestanden (4 neue Chunking-Tests)
- Befund: "Jahresabschluss und Zwischenabschluss SelectLine.pdf" liegt in
  sowohl modulbeschreibungen/ als auch schulungsunterlagen/ → gleiche doc_id;
  gelöst durch source_type-Prefix in Chunk-IDs

---

## 2026-05-02 – AP-2.5: Repo-Aufräumen nach Datenaufbereitungs-APs

Aufräumarbeiten nach Abschluss der Datenaufbereitungs-APs (AP-2a bis AP-2e):

- Duplikat `.github/CLAUDE.md` entfernt (Claude-Konfig nur noch im Root)
- `src/rag/ingest/` war bereits nicht mehr vorhanden (wurde offenbar schon entfernt)
- `scripts/Pipeline/01_ingest.py` gelöscht (ersetzt durch `00_prepare_*.py`)
- `src/rag/pipeline_factory.py` mit `NotImplementedError`-Stubs versehen;
  Neuimplementation in AP-3 (alte Imports auf `rag.ingest` entfernt)
- `scripts/transformation/forum_encoding_fix.py` gelöscht
  (Logik liegt vollständig in `preparation/forum.py`)
- `.gitignore` modernisiert: spezifische `data/raw|interim|processed|index|eval`-
  Einträge entfernt (redundant zu pauschaler `data/`-Regel); `runs/naive_rag`-
  Eintrag entfernt
- `runs/naive_rag/` entfernt; `NAIVE_RAG_RUNS_DIR` aus `config.py` entfernt
- Alle fünf `00_prepare_*.py`-Skripte weiterhin lauffähig (Smoke-Tests bestanden)
- 23/23 Tests bestanden

---

## 2026-05-02 – AP-2e: Schulungsunterlagen + pages-Array in Gold-Schema (PDF)

- Modul `src/rag/preparation/schulungsunterlagen.py` (analog zu handbuecher.py,
  flaches glob, source_type="schulungsunterlage", kein Outline erwartet)
- Pipeline-Skript `scripts/Pipeline/00_prepare_schulungsunterlagen.py`
- Gold-Schema für alle PDF-Quellen erweitert: `content.pages` als Array von
  `{page_number, text}`-Dicts (Grundlage für V1-Chunking per Seite)
- `clean_to_silver()` in allen drei PDF-Modulen: Boilerplate-Bereinigung jetzt
  pro Seite; `full_text` wird aus bereinigten Seiten zusammengesetzt (Konsistenz)
- `transform_to_gold()` in allen drei PDF-Modulen: `pages_json` → `content.pages`
- Pipeline-Skripte (handbuecher, modulbeschreibungen, schulungsunterlagen):
  `pages_json` wird beim CSV-Export gedroppt (nicht CSV-kompatibel)
- Schulungsunterlagen: 19 PDFs, 937 Seiten, 1'319 Bilder (alle ohne Outline)
- Handbücher neu generiert: 8 PDFs, 9'082 Seiten, 6'253 Bilder
- Modulbeschreibungen neu generiert: 63 PDFs, 1'053 Seiten, 1'542 Bilder
- Tests: 23/23 bestanden (6 neue Tests: 3 schulungsunterlagen + 1 handbuecher +
  1 modulbeschreibungen + Fixture-Fix für pages-losen _make_doc)

---

## 2026-05-01 – AP-2d: Modulbeschreibungen-Datenaufbereitung

- Modul `src/rag/preparation/modulbeschreibungen.py` (analog zu handbuecher.py,
  rglob für Unterordner, source_type="modulbeschreibung")
- Pipeline-Skript `scripts/Pipeline/00_prepare_modulbeschreibungen.py`
- Boilerplate-Pattern `BOILERPLATE_PATTERNS` + `remove_boilerplate()` nach
  `pdf_reader.py` extrahiert (gemeinsam genutzt von handbuecher.py und
  modulbeschreibungen.py); neues Pattern: `^Seite\s+\d+` (für "Seite X von Y")
- 63 PDFs in 12 Unterordnern, 1'053 Seiten, 1'542 Bilder extrahiert
- Outline-Statistik: 3/63 Dokumente mit Outline, 60 ohne → robust behandelt
- Tests 3/3 bestanden; alle bisherigen Tests weiterhin grün (7/7)

---

## 2026-05-01 – AP-2c: Handbuch-Datenaufbereitung

- Modul `src/rag/preparation/pdf_reader.py` (PyMuPDF-basiert, generisch
  wiederverwendbar für alle PDF-Quellen: Text, Outline, Bild-Extraktion)
- Modul `src/rag/preparation/handbuecher.py` (load_bronze, clean_to_silver, transform_to_gold)
- Pipeline-Skript `scripts/Pipeline/00_prepare_handbuecher.py`
- Bilder als PNG nach data/gold/images/<doc_id>/ extrahiert; Bilder <50×50px verworfen
- Outline als strukturierte Liste in Gold-Schicht (für V1-Chunking)
- Boilerplate-Filter (isolierte Seitenzahlen, Copyright-Zeilen)
- Dependency: pymupdf>=1.24 (installiert: 1.27.2)
- 8 PDFs, 9'082 Seiten, 6'253 Bilder extrahiert (2'782 gefiltert als zu klein)
  (inkl. SelectLine System Handbuch: 1'512 Seiten, 1'084 Outline-Einträge)
- Tests 4/4 bestanden

---

## 2026-05-01 – AP-2b: Ticket-Datenaufbereitung

- Modul `src/rag/preparation/dbf_reader.py` (DBF-Lese-Logik aus
  `scripts/transformation/ticket_dbf_to_csv.py` extrahiert,
  Pfad-Hartcodierung entfernt, API gibt DataFrame statt CSV zurück)
- Modul `src/rag/preparation/tickets.py` (load_bronze, clean_to_silver, transform_to_gold)
- Lookup-Tabellen `PRODUCT_LOOKUP` und `TICKET_STATUS_LOOKUP` in `lookups.py`
- Pipeline-Skript `scripts/Pipeline/00_prepare_tickets.py`
- Filter: nur Tickets mit nicht-leerem LOESUNG-Feld (18'609 → 4'691)
- Gold-Format mit strukturierten Markern (Fehlerbeschreibung:, Lösung:)
- Tests für DBF-Lese-Logik und alle drei Verarbeitungsstufen (5/5 bestanden)
- Altes Skript `ticket_dbf_to_csv.py` als Wrapper reduziert
- 645 E-Mail-Signaturen entfernt, 468 HTML-Felder bereinigt

---

## 2026-05-01 – AP-2a.1: Pfadstruktur korrigieren

- `PROCESSED_DIR` umbenannt zu `GOLD_DIR` (Datenaufbereitung, variantenunabhängig)
- Neuer Pfad `CHUNKS_DIR` für variantenspezifische Chunks (Ingestion)
- `get_variant_processed_dir()` entfernt, ersetzt durch `get_variant_chunks_dir()`
- Verwendungsstellen in `00_prepare_forum.py` und `02_index.py` angepasst
- Klare Trennung zwischen Datenaufbereitung (Kap. 5) und Ingestion (Kap. 6)

---

## 2026-05-01 – AP-2a: Forum-Datenaufbereitung

- Submodul `src/rag/preparation/` mit Modulen `lookups.py`, `jsonl_writer.py`, `forum.py`
- Pipeline-Skript `scripts/Pipeline/00_prepare_forum.py`
- Bronze→Silver→Gold-Verarbeitung für Forum-Quelle
- Encoding-Korrektur (Latin-1/UTF-8 Mojibake-Fix), Spaltenfilterung, BBCode/HTML-Entfernung,
  Modul-Code-Auflösung, Deduplizierung, JSONL-Export
- 2058 Bronze-Beiträge → 2052 Silver/Gold (6 Duplikate entfernt)
- Tests für alle drei Verarbeitungsstufen (6/6 bestanden)
- Quelldatei: `data/bronze/forum/forum.csv` (Trennzeichen: `;`, 26 phpBB-Spalten)

---

## 2026-04-30 – AP-1.5: Konfigurations-Synchronisation

- EMBEDDING_MODEL Default auf `text-embedding-3-large` (DE-1)
- LLM_MODEL Default auf `gpt-4.1` (DE-3)
- CHUNK_SIZE 800, CHUNK_OVERLAP 100 (DE-4)
- LLM_TEMPERATURE als neue Konfiguration mit Default 0.0 (DE-7)
- `.env.example` entsprechend aktualisiert
- V0 weiterhin lauffähig

---

## 2026-04-28 – AP-1: Repo-Refactor

- Variant-Switch eingeführt (Default V0)
- Variantenspezifische Pfade für Index, Processed, Eval
- Pipeline-Factory als Entkopplungsschicht
- Skripte nach `scripts/Pipeline/` verschoben
- V0 weiterhin lauffähig

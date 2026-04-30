# Claude Instructions – Bachelorarbeit

## Projektziel

Dieses Repository implementiert einen **RAG** (Retrieval-Augmented Generation)
Prototypen als wissenschaftliches Artefakt für eine Bachelorarbeit. 

Wichtiger konzeptioneller Hintergrund
In der Bachelorarbeit werden vier Pipeline-Varianten definiert, die kumulativ aufeinander aufbauen:

V0 – Naive Baseline: Alle Quellen werden gleich behandelt.
V1 – Quellenspezifische Aufbereitung: Pro Quelltyp (Handbuch, Modulbeschreibung, Schulungsunterlage, Ticket, Forum) wird eigene Loader- und Chunking-Logik angewendet.
V2 – Metadaten-Anreicherung und Temporalität: Strukturelle Metadaten + LLM-generierte Metadaten + Recency-Prior im Retrieval.
V3 – Multimodalität: Bilder werden via Vision-Language-Model beschrieben und in den Chunk-Kontext eingebunden.

Alle vier Varianten teilen sich dieselbe fixe Infrastruktur: identisches Embedding-Modell, identischer Vektorstore, identischer Generator. Nur die Ingestion- und (bei V2) Retrieval-Logik unterscheidet sich.
Daraus folgt für den Refactor: Das Repo muss einen sauberen Variant-Switch bekommen, sodass alle vier Varianten parallel existieren und über einen Parameter gewählt werden können. Daten und Indizes pro Variante werden in eigenen Unterordnern persistiert, um Vergleichbarkeit zu gewährleisten.

## Allgemeine Regeln

- **Einfachheit vor Eleganz.** Code soll minimal, verständlich und ohne
  Overengineering sein. Studentisch nachvollziehbar.
- **Keine magischen Pfade.** Alle Pfade und Parameter werden zentral in
  `src/rag/config.py` verwaltet. Kein Hardcoding in Modulen oder Skripten.
- **Artefakte sind Pflicht.** Jede Pipeline-Stufe (Ingest → Index → Retrieve →
  Generate → Evaluate) schreibt ihre Ergebnisse als persistente Dateien in die
  entsprechenden `data/` oder `runs/` Ordner.
- **Modularität ohne Querverkabelung.** Neue Features werden als eigene Module
  ergänzt. Kein Modul importiert quer aus einer fremden Pipeline-Stufe, ausser
  über die zentrale Konfiguration.
- **Öffentliche Funktionen** erhalten Typannotationen und einen kurzen Docstring.
- **Logging statt print.** Verwende das `logging`-Modul für jede Ausgabe.
- **Reproduzierbarkeit.** Seeds, Modellversionen und Parameter werden in der
  Konfiguration festgehalten.
- **Keine unnötigen Dependencies.** Nur Pakete hinzufügen, die wirklich
  gebraucht werden. Jede neue Dependency in `pyproject.toml` eintragen.


## Code-Stil

- Python ≥ 3.11
- Formatter & Linter: **Ruff**
- Typprüfung: **Pylance** (in VS Code)
- Tests: **pytest**
- Einrückung: 4 Spaces
- Max. Zeilenlänge: 88 Zeichen (Ruff-Default)

## Verzeichnisstruktur

```
data/bronze/          ← Originaldaten (PDFs, CSVs, …)
data/silver/      ← Zwischenergebnisse (extrahierter Text)
data/gold/       ← Aufbereitete, normalisierte Dokumente
data/index/        ← Vektorindex / Embeddings
data/eval/         ← Evaluationsergebnisse
runs/naive_rag/    ← Lauf-Artefakte des Naive RAG
runs/eval/         ← Evaluations-Runs
src/rag/           ← Hauptpaket
scripts/           ← Einstiegspunkte (01_ingest, 02_index, …)
tests/             ← Unit-Tests
```

## Hinweise für Claude

- Halte Vorschläge bewusst einfach und nachvollziehbar.
- Verwende immer Pfade aus `config.py`, niemals Literal-Strings.
- Wenn du unsicher bist, schlage die einfachere Variante vor.

## KI-Protokoll (Pflicht)

Am **Beginn jeder Konversation** und am **Ende jeder Konversation** (nach Abschluss
eines Arbeitspakets) muss `docs/ai_protokoll.md` erweitert werden:

1. **Konversationsbeginn**: Neuen Abschnitt `## Konversation N – YYYY-MM-DD` anlegen.
2. **Jeden Prompt** des Benutzers vollständig (oder sinnvoll gekürzt) unter
   `### Prompts` eintragen.
3. **Nach Abschluss eines Arbeitspakets**: Unter `### Aktionen & Erkenntnisse`
   zusammenfassen was gemacht wurde – geänderte Dateien, getroffene Entscheidungen,
   offene Punkte.
4. Neuste Konversation steht **oben** (absteigend chronologisch).
5. Das File liegt unter `docs/ai_protokoll.md` – niemals umbenennen oder verschieben.

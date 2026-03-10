# Copilot Instructions – Naive RAG Baseline (Bachelorarbeit)

## Projektziel

Dieses Repository implementiert einen **Naive RAG** (Retrieval-Augmented Generation)
Prototypen als wissenschaftliche Baseline für eine Bachelorarbeit.
Der Naive RAG wird später gegen ein **Modular RAG** evaluiert.

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
- **Keine fortgeschrittenen RAG-Features** in der Baseline-Version: kein
  Re-Ranking, keine hybride Suche, keine Agentenlogik, keine zeitliche
  Gewichtung, keine Multimodalität.

## Code-Stil

- Python ≥ 3.11
- Formatter & Linter: **Ruff**
- Typprüfung: **Pylance** (in VS Code)
- Tests: **pytest**
- Einrückung: 4 Spaces
- Max. Zeilenlänge: 88 Zeichen (Ruff-Default)

## Verzeichnisstruktur

```
data/raw/          ← Originaldaten (PDFs, CSVs, …)
data/interim/      ← Zwischenergebnisse (extrahierter Text)
data/processed/    ← Aufbereitete, normalisierte Dokumente
data/index/        ← Vektorindex / Embeddings
data/eval/         ← Evaluationsergebnisse
runs/naive_rag/    ← Lauf-Artefakte des Naive RAG
runs/eval/         ← Evaluations-Runs
src/rag/           ← Hauptpaket
scripts/           ← Einstiegspunkte (01_ingest, 02_index, …)
tests/             ← Unit-Tests
```

## Hinweise für Copilot

- Schlage keine Features vor, die über den Naive RAG hinausgehen.
- Halte Vorschläge bewusst einfach und nachvollziehbar.
- Verwende immer Pfade aus `config.py`, niemals Literal-Strings.
- Wenn du unsicher bist, schlage die einfachere Variante vor.

# Kategorieweise Aufschlüsselung

Mittelwert der RAGAS-Metriken pro Variante und Kategorie.
Zellen mit `–` / `nan` haben keine validen Scores für diese Kombination.

## Faithfulness

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     1.0000 |        1.0000 |    0.8889 |    0.7729 |
| V1         |     0.9599 |        0.6250 |    0.9167 |    0.8112 |
| V2         |     0.9519 |      nan      |    0.9444 |    0.6893 |
| V3         |     0.8820 |        0.8000 |    0.9630 |    0.7468 |
| V4         |     0.9158 |        0.6282 |    0.9141 |    0.7153 |

## Answer Relevance

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     0.8614 |        0.6532 |    0.7685 |    0.6870 |
| V1         |     0.8490 |        0.8647 |    0.8891 |    0.6751 |
| V2         |     0.8472 |        0.6408 |    0.8813 |    0.6862 |
| V3         |     0.8196 |        0.8690 |    0.6725 |    0.7676 |
| V4         |     0.8466 |        0.9026 |    0.8711 |    0.6793 |

## Context Recall

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     0.6204 |        0.0000 |    0.3889 |    0.5000 |
| V1         |     0.5682 |        1.0000 |    0.4405 |    0.4375 |
| V2         |     0.6917 |        0.3333 |    0.4667 |    0.4375 |
| V3         |     0.6515 |        1.0000 |    0.2000 |    0.3333 |
| V4         |     0.7000 |        0.5000 |    0.4000 |    0.5714 |

## Factual Correctness

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     0.4268 |        0.3050 |    0.1575 |    0.3600 |
| V1         |     0.3585 |        0.2200 |    0.2375 |    0.3312 |
| V2         |     0.4970 |        0.2425 |    0.1963 |    0.3200 |
| V3         |     0.2675 |        0.2100 |    0.2137 |    0.2575 |
| V4         |     0.4335 |        0.2225 |    0.1963 |    0.4050 |

## Anmerkungen zu fehlenden Scores (sparse Zellen)

- **V0/Chunking/Faithfulness**: 5/20 valide Werte (Mittelwert aus 5 Fragen)
- **V0/CrossSource/Faithfulness**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V0/Recency/Faithfulness**: 3/8 valide Werte (Mittelwert aus 3 Fragen)
- **V0/Visuals/Faithfulness**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V1/Chunking/Faithfulness**: 9/20 valide Werte (Mittelwert aus 9 Fragen)
- **V1/CrossSource/Faithfulness**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V1/Recency/Faithfulness**: 4/8 valide Werte (Mittelwert aus 4 Fragen)
- **V1/Visuals/Faithfulness**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V2/Chunking/Faithfulness**: 10/20 valide Werte (Mittelwert aus 10 Fragen)
- **V2/CrossSource/Faithfulness**: 0/4 valide Werte – RAGAS konnte keinen Score berechnen (Antworten ohne prüfbare Aussagen)
- **V2/Recency/Faithfulness**: 3/8 valide Werte (Mittelwert aus 3 Fragen)
- **V3/Chunking/Faithfulness**: 9/20 valide Werte (Mittelwert aus 9 Fragen)
- **V3/CrossSource/Faithfulness**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V3/Recency/Faithfulness**: 6/8 valide Werte (Mittelwert aus 6 Fragen)
- **V3/Visuals/Faithfulness**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V4/Chunking/Faithfulness**: 11/20 valide Werte (Mittelwert aus 11 Fragen)
- **V4/CrossSource/Faithfulness**: 3/4 valide Werte (Mittelwert aus 3 Fragen)
- **V4/Recency/Faithfulness**: 6/8 valide Werte (Mittelwert aus 6 Fragen)
- **V4/Visuals/Faithfulness**: 6/8 valide Werte (Mittelwert aus 6 Fragen)
- **V4/Chunking/Answer Relevance**: 19/20 valide Werte (Mittelwert aus 19 Fragen)
- **V0/Chunking/Context Recall**: 9/20 valide Werte (Mittelwert aus 9 Fragen)
- **V0/CrossSource/Context Recall**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V0/Recency/Context Recall**: 6/8 valide Werte (Mittelwert aus 6 Fragen)
- **V0/Visuals/Context Recall**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V1/Chunking/Context Recall**: 11/20 valide Werte (Mittelwert aus 11 Fragen)
- **V1/CrossSource/Context Recall**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V1/Recency/Context Recall**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V2/Chunking/Context Recall**: 10/20 valide Werte (Mittelwert aus 10 Fragen)
- **V2/CrossSource/Context Recall**: 2/4 valide Werte (Mittelwert aus 2 Fragen)
- **V2/Recency/Context Recall**: 5/8 valide Werte (Mittelwert aus 5 Fragen)
- **V3/Chunking/Context Recall**: 11/20 valide Werte (Mittelwert aus 11 Fragen)
- **V3/CrossSource/Context Recall**: 1/4 valide Werte (Mittelwert aus 1 Fragen)
- **V3/Recency/Context Recall**: 5/8 valide Werte (Mittelwert aus 5 Fragen)
- **V3/Visuals/Context Recall**: 6/8 valide Werte (Mittelwert aus 6 Fragen)
- **V4/Chunking/Context Recall**: 15/20 valide Werte (Mittelwert aus 15 Fragen)
- **V4/CrossSource/Context Recall**: 2/4 valide Werte (Mittelwert aus 2 Fragen)
- **V4/Recency/Context Recall**: 5/8 valide Werte (Mittelwert aus 5 Fragen)
- **V4/Visuals/Context Recall**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V0/Chunking/Factual Correctness**: 19/20 valide Werte (Mittelwert aus 19 Fragen)

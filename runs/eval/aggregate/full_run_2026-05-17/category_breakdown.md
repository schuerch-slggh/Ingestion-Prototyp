# Kategorieweise Aufschlüsselung

Mittelwert der RAGAS-Metriken pro Variante und Kategorie.
Zellen mit `–` / `nan` haben keine validen Scores für diese Kombination.

## Faithfulness

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     0.9879 |        0.9181 |    1.0000 |    0.7812 |
| V1         |     0.9677 |        0.8727 |    0.9688 |    0.7827 |
| V2         |     0.9122 |        0.9427 |    0.9335 |    0.8083 |
| V3         |     0.8779 |        0.8333 |    0.9375 |    0.6534 |
| V4         |     0.8966 |        0.6643 |    0.9034 |    0.7406 |

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
| V0         |     0.7375 |        0.4167 |    0.4792 |    0.4375 |
| V1         |     0.7000 |        0.4444 |    0.3854 |    0.4375 |
| V2         |     0.6833 |        0.5833 |    0.4271 |    0.4375 |
| V3         |     0.5583 |        0.5833 |    0.1429 |    0.5625 |
| V4         |     0.6711 |        0.5833 |    0.4688 |    0.6250 |

## Factual Correctness

| Variante   |   Chunking |   CrossSource |   Recency |   Visuals |
|:-----------|-----------:|--------------:|----------:|----------:|
| V0         |     0.4268 |        0.3050 |    0.1575 |    0.3600 |
| V1         |     0.3585 |        0.2200 |    0.2375 |    0.3312 |
| V2         |     0.4970 |        0.2425 |    0.1963 |    0.3200 |
| V3         |     0.2675 |        0.2100 |    0.2137 |    0.2575 |
| V4         |     0.4335 |        0.2225 |    0.1963 |    0.4050 |

## Anmerkungen zu fehlenden Scores (sparse Zellen)

- **V0/Recency/Faithfulness**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V2/Chunking/Faithfulness**: 19/20 valide Werte (Mittelwert aus 19 Fragen)
- **V3/Chunking/Faithfulness**: 19/20 valide Werte (Mittelwert aus 19 Fragen)
- **V4/Chunking/Answer Relevance**: 19/20 valide Werte (Mittelwert aus 19 Fragen)
- **V1/CrossSource/Context Recall**: 3/4 valide Werte (Mittelwert aus 3 Fragen)
- **V3/Recency/Context Recall**: 7/8 valide Werte (Mittelwert aus 7 Fragen)
- **V4/Chunking/Context Recall**: 19/20 valide Werte (Mittelwert aus 19 Fragen)
- **V0/Chunking/Factual Correctness**: 19/20 valide Werte (Mittelwert aus 19 Fragen)

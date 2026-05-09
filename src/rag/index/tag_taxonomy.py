"""Tag-Taxonomie für V2 LLM-Tagging.

Geschlossene Listen für drei Tag-Kategorien:
- MODULE_TAGS:  ~35 SelectLine-Module (aus FORUM_MODULE_LOOKUP)
- THEMA_TAGS:   16 thematische Bereiche (inkl. 'Sonstiges' als Catch-all)
- TYP_TAGS:     6 Dokumenttypen
"""

from rag.preparation.lookups import FORUM_MODULE_LOOKUP

MODULE_TAGS: frozenset[str] = frozenset(FORUM_MODULE_LOOKUP.values())

THEMA_TAGS: frozenset[str] = frozenset(
    {
        "MWST",
        "Mahnwesen",
        "Stammdaten",
        "Buchungen",
        "Lohnabrechnung",
        "Lagerbewegungen",
        "Rechnungsversand",
        "Banking",
        "Schnittstellen",
        "Konfiguration",
        "Berechtigungen",
        "Auswertungen",
        "Druck",
        "Datenbank",
        "Update",
        "Sonstiges",
    }
)

TYP_TAGS: frozenset[str] = frozenset(
    {
        "Anleitung",
        "Fehlermeldung",
        "Konfiguration",
        "Frage",
        "Diskussion",
        "Konzept",
    }
)

MAX_TAGS: dict[str, int] = {
    "module_tags": 2,
    "thema_tags": 3,
    "typ_tags": 1,
}

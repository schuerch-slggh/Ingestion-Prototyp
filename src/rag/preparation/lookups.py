"""Lookup-Tabellen für die Datenaufbereitung."""

import logging

logger = logging.getLogger(__name__)

FORUM_MODULE_LOOKUP: dict[str, str] = {
    "12": "Neue Versionen",
    "15": "SelectLine Auftrag",
    "16": "SelectLine Lohn",
    "17": "V17 USTVADAT keine Anzeige - Lösung",
    "18": "SelectLine Mobile",
    "19": "Plantafel",
    "20": "Programmübergreifend",
    "24": "Installation / Updates",
    "25": "Updates",
    "26": "SQL Server",
    "27": "Abkündigung SQL Server 2008 R2 und Windows Vi",
    "29": "PC-Kasse",
    "34": "Lagerverwaltung",
    "36": "SelectLine Auftrag Allgemein",
    "45": "SelectLine Rechnungswesen / Fibu Allgemein",
    "49": "Kostenrechnung",
    "50": "SQL Server",
    "54": "Verbuchung der Bezugsteuer",
    "56": "ELM: EIV-Upload der XML-Datei per Internet",
    "57": "Skip5",
    "59": "Allgemeine Forum Regel für die Registrierung",
    "68": "Makros",
    "69": "Toolbox & COM",
    "70": "CRM",
    "72": "Off-Topics - Partner-Lösungen",
    "74": "SelectLine stellt sich vor - Rundgang durch's",
    "76": "Off-Topics - Partner-Lösungen",
    "77": "Fremdwährungen im Kassabuch",
    "78": "Programm Einrichtung",
    "79": "Einrichtung Lohn",
    "80": "OPOS EZV Rechnungswesen",
    "81": "Toolbox",
    "82": "SelectLine News",
    "83": "MDE",
    "84": "Doqio",
    "85": "SelectLine Server",
}


def resolve_forum_module(forum_id: str) -> str:
    """Löst einen phpBB forum_id-Code in den Klartext-Modulnamen auf.

    Liegt der Code nicht in der Lookup-Tabelle, wird der Code selbst
    zurückgegeben und eine Warnung geloggt.
    """
    if forum_id in FORUM_MODULE_LOOKUP:
        return FORUM_MODULE_LOOKUP[forum_id]
    logger.warning(
        "Unbekannte forum_id '%s' – Code wird als Klartext beibehalten", forum_id
    )
    return forum_id

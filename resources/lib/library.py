"""Anbindung an Kodi ueber JSON-RPC.

Die Kodi-Importe stehen in den Funktionen, damit dieses Modul auch ohne
laufendes Kodi importierbar bleibt.
"""
import json

import log


def _rpc(methode, params=None):
    import xbmc

    anfrage = {"jsonrpc": "2.0", "method": methode, "id": 1}
    if params is not None:
        anfrage["params"] = params
    try:
        roh = xbmc.executeJSONRPC(json.dumps(anfrage))
        return json.loads(roh)
    except (ValueError, TypeError) as ausnahme:
        log.warn("JSON-RPC fehlgeschlagen (%s): %s" % (methode, ausnahme))
        return {}


def scanne(pfad):
    """Gezielter Bibliotheksscan nur fuer dieses Verzeichnis."""
    log.info("Bibliotheksscan: %s" % pfad)
    _rpc("VideoLibrary.Scan", {"directory": pfad, "showdialogs": False})


def spielt_gerade(pfad):
    """Laeuft diese Datei gerade in einem Player?"""
    antwort = _rpc("Player.GetActivePlayers")
    spieler = antwort.get("result") or []
    if not isinstance(spieler, list):
        return False

    for eintrag in spieler:
        pid = eintrag.get("playerid")
        if pid is None:
            continue
        details = _rpc("Player.GetItem", {"playerid": pid, "properties": ["file"]})
        datei = (((details.get("result") or {}).get("item")) or {}).get("file")
        if datei and datei == pfad:
            return True
    return False


def benachrichtige(titel, text, dauer_ms=5000):
    import xbmcgui

    try:
        xbmcgui.Dialog().notification(titel, text, xbmcgui.NOTIFICATION_INFO, dauer_ms)
    except Exception as ausnahme:      # Kodi wirft hier je nach Version verschieden
        log.warn("Benachrichtigung fehlgeschlagen: %s" % ausnahme)

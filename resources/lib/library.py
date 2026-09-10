"""Anbindung an Kodi ueber JSON-RPC.

Die Kodi-Importe stehen in den Funktionen, damit dieses Modul auch ohne
laufendes Kodi importierbar bleibt.
"""
import json
import os

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


def quellpfad_fuer(pfad, quellen):
    """Uebersetzt einen Pfad in die Schreibweise der Kodi-Quelle, in der er liegt.

    Kodi vergleicht Pfade als Text. Heisst die Quelle /media/MOVIES/Serien/, der
    Zielpfad aber /var/media/MOVIES/Serien/..., laeuft ein Scan ins Leere, obwohl
    /media nur ein Symlink ist. Verglichen wird deshalb ueber die aufgeloesten
    Pfade, zurueckgegeben die Schreibweise der Quelle mit abschliessendem Slash.
    Netzwerkquellen wie smb:// werden uebersprungen. None, wenn keine passt.
    """
    echt = os.path.realpath(pfad)
    bester = None
    for quelle in quellen:
        if not quelle or "://" in quelle:
            continue
        quelle_echt = os.path.realpath(quelle)
        if echt == quelle_echt:
            rest = ""
        elif echt.startswith(quelle_echt.rstrip(os.sep) + os.sep):
            rest = os.path.relpath(echt, quelle_echt)
        else:
            continue
        if bester is None or len(quelle_echt) > bester[0]:
            bester = (len(quelle_echt), quelle, rest)

    if bester is None:
        return None
    _, quelle, rest = bester
    ergebnis = quelle.rstrip("/") + "/"
    if rest:
        ergebnis += rest.replace(os.sep, "/") + "/"
    return ergebnis


def _video_quellen():
    antwort = _rpc("Files.GetSources", {"media": "video"})
    quellen = (antwort.get("result") or {}).get("sources") or []
    return [q.get("file") for q in quellen if isinstance(q, dict) and q.get("file")]


def scanne(pfad):
    """Gezielter Bibliotheksscan in der Schreibweise der passenden Kodi-Quelle.

    Gibt True zurueck, wenn ein Scan abgeschickt wurde. Liegt der Pfad in keiner
    Quelle, wird nicht gescannt: ein solcher Scan liefe in Kodi wortlos ins Leere.
    """
    ziel = quellpfad_fuer(pfad, _video_quellen())
    if ziel is None:
        log.warn("Kein Bibliotheksscan: %s liegt in keiner Kodi-Videoquelle" % pfad)
        return False
    log.info("Bibliotheksscan: %s" % ziel)
    _rpc("VideoLibrary.Scan", {"directory": ziel, "showdialogs": False})
    return True


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

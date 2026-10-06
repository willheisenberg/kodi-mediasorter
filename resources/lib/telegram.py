"""Meldet neu einsortierte Filme und Serienfolgen in eine Telegram-Gruppe.

Kodi-frei wie durchlauf.py. Der Token steht in der Adresse der Bot-API und
darf deshalb in keiner Logzeile auftauchen: geloggt wird nie die Adresse und
nie der Text einer Ausnahme, die sie enthalten koennte.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

import log

STANDARD_FILM = "🎬 Der Film {titel} wurde zu Kodi hinzugefügt."
STANDARD_SERIE = (
    "📺 Die Serie {titel} Staffel {staffel} Episode {episode} wurde zu Kodi hinzugefügt."
)
_ZEITLIMIT = 15


def _episoden_text(episoden):
    """[8] -> 8, [1, 2, 3] -> 1–3, [1, 2, 5] -> 1, 2, 5."""
    nummern = sorted(set(episoden))
    if len(nummern) > 1 and nummern[-1] - nummern[0] == len(nummern) - 1:
        return "%d–%d" % (nummern[0], nummern[-1])
    return ", ".join(str(n) for n in nummern)


def text_fuer(eintrag, vorlage_film="", vorlage_serie=""):
    """Der Satz zu einem Eintrag aus durchlauf.einmal()["hinzugefuegt"].

    Eine leere oder fehlerhafte Vorlage faellt auf den Standardsatz zurueck,
    damit ein Tippfehler in den Einstellungen keine Meldung verschluckt.
    """
    if eintrag["typ"] == "serie":
        vorlage, standard = vorlage_serie, STANDARD_SERIE
        werte = {
            "titel": eintrag["titel"],
            "staffel": eintrag["staffel"],
            "episode": _episoden_text(eintrag["episoden"]),
        }
    else:
        vorlage, standard = vorlage_film, STANDARD_FILM
        werte = {"titel": eintrag["titel"], "staffel": "", "episode": ""}

    vorlage = (vorlage or "").strip()
    if not vorlage:
        return standard.format(**werte)
    try:
        return vorlage.format(**werte)
    except (KeyError, IndexError, ValueError):
        log.warn("Telegram-Vorlage fehlerhaft, Standardsatz benutzt: %s" % vorlage)
        return standard.format(**werte)


def sende(token, chat_id, text, oeffner=None):
    """Schickt text in den Chat. True nur, wenn Telegram die Nachricht annimmt."""
    anfrage = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % token,
        data=urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8"),
    )
    try:
        with (oeffner or urllib.request.urlopen)(anfrage, timeout=_ZEITLIMIT) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        # 401 heisst falscher Token, 400 und 403 meist falsche Chat-ID oder
        # der Bot ist kein Mitglied der Gruppe.
        log.warn("Telegram lehnt die Nachricht ab: HTTP %s" % fehler.code)
        return False
    except (OSError, ValueError) as fehler:
        log.warn("Telegram nicht erreichbar (%s)" % type(fehler).__name__)
        return False

    if not (isinstance(daten, dict) and daten.get("ok")):
        beschreibung = daten.get("description") if isinstance(daten, dict) else None
        log.warn("Telegram lehnt die Nachricht ab: %s" % (beschreibung or "ohne Angabe"))
        return False
    return True


def melde(cfg, eintraege, oeffner=None):
    """Eine Nachricht pro Eintrag. Liefert die Zahl der zugestellten Nachrichten."""
    if not cfg.telegram_aktiv():
        return 0
    zugestellt = 0
    for eintrag in eintraege:
        text = text_fuer(eintrag, cfg.telegram_text_film, cfg.telegram_text_serie)
        if sende(cfg.telegram_token, cfg.telegram_chat_id, text, oeffner):
            zugestellt += 1
    return zugestellt

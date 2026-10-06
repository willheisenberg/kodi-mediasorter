"""Meldet neu einsortierte Filme und Serienfolgen in eine Telegram-Gruppe.

Kodi-frei wie durchlauf.py. Der Token steht in der Adresse der Bot-API und
darf deshalb in keiner Logzeile auftauchen: geloggt wird nie die Adresse und
nie der Text einer Ausnahme, die sie enthalten koennte.

Folgen derselben Serie, die kurz nacheinander eintreffen, landen in einer
einzigen Nachricht: die letzte wird durch eine ergaenzte ersetzt. Dafuer merkt
sich melde() die zuletzt gesendete Nachricht in einer Datei.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import log

STANDARD_FILM = "🎬 The movie {titel} was added to Kodi."
STANDARD_SERIE = (
    "📺 The series {titel} Season {staffel} Episode {episode} was added to Kodi."
)
_ZEITLIMIT = 15
# Aelter als das, und die Folge bekommt wieder eine eigene Nachricht, die auch
# wieder klingelt. Bots duerfen eigene Nachrichten ohnehin nur 48 Stunden lang
# loeschen.
_SAMMELFENSTER = 6 * 3600
# "Season {staffel} Episode {episode}" samt dem Wort davor: der Teil der
# Vorlage, der sich bei mehreren Staffeln wiederholt.
_STAFFELBLOCK = re.compile(r"(?:[^\s{}]+\s+)?[^\s{}]*\{staffel\}.*?\{episode\}", re.S)


def _episoden_text(episoden):
    """[8] -> 8, [1, 2, 3] -> 1–3, [1, 2, 5] -> 1, 2, 5."""
    nummern = sorted(set(episoden))
    if len(nummern) > 1 and nummern[-1] - nummern[0] == len(nummern) - 1:
        return "%d–%d" % (nummern[0], nummern[-1])
    return ", ".join(str(n) for n in nummern)


def _staffeln(eintrag):
    """{staffel: [episoden]} fuer einen einfachen wie fuer einen gesammelten Eintrag."""
    if "staffeln" in eintrag:
        return eintrag["staffeln"]
    return {eintrag["staffel"]: eintrag["episoden"]}


def _aufzaehlung(teile):
    """[a] -> a, [a, b, c] -> a, b & c. Das Zeichen passt zu jeder Sprache der Vorlage."""
    if len(teile) < 2:
        return "".join(teile)
    return "%s & %s" % (", ".join(teile[:-1]), teile[-1])


def _serientext(vorlage, titel, staffeln):
    """Fuellt die Vorlage. Bei mehreren Staffeln wiederholt sich ihr Staffelblock:
    Season 1 Episode 1–4 & Season 2 Episode 1, 2."""
    paare = [(s, _episoden_text(e)) for s, e in sorted(staffeln.items())]
    if len(paare) > 1:
        treffer = _STAFFELBLOCK.search(vorlage)
        if not treffer:
            raise ValueError("kein Staffelblock")
        bloecke = [
            treffer.group(0).replace("{staffel}", str(s)).replace("{episode}", e)
            for s, e in paare
        ]
        vorlage = vorlage[:treffer.start()] + _aufzaehlung(bloecke) + vorlage[treffer.end():]
    return vorlage.format(titel=titel, staffel=paare[0][0], episode=paare[0][1])


def text_fuer(eintrag, vorlage_film="", vorlage_serie=""):
    """Der Satz zu einem Eintrag aus durchlauf.einmal()["hinzugefuegt"].

    Eine leere oder fehlerhafte Vorlage faellt auf den Standardsatz zurueck,
    damit ein Tippfehler in den Einstellungen keine Meldung verschluckt.
    """
    if eintrag["typ"] == "serie":
        vorlage, standard = vorlage_serie, STANDARD_SERIE

        def fuelle(text):
            return _serientext(text, eintrag["titel"], _staffeln(eintrag))
    else:
        vorlage, standard = vorlage_film, STANDARD_FILM

        def fuelle(text):
            return text.format(titel=eintrag["titel"], staffel="", episode="")

    vorlage = (vorlage or "").strip()
    if not vorlage:
        return fuelle(standard)
    try:
        return fuelle(vorlage)
    except (KeyError, IndexError, ValueError):
        log.warn("Telegram-Vorlage fehlerhaft, Standardsatz benutzt: %s" % vorlage)
        return fuelle(standard)


def _rufe(token, methode, felder, oeffner=None):
    """Ruft die Bot-API auf. Liefert result oder None, wenn Telegram ablehnt."""
    anfrage = urllib.request.Request(
        "https://api.telegram.org/bot%s/%s" % (token, methode),
        data=urllib.parse.urlencode(felder).encode("utf-8"),
    )
    try:
        with (oeffner or urllib.request.urlopen)(anfrage, timeout=_ZEITLIMIT) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        # 401 heisst falscher Token, 400 und 403 meist falsche Chat-ID oder
        # der Bot ist kein Mitglied der Gruppe.
        log.warn("Telegram lehnt die Nachricht ab: HTTP %s" % fehler.code)
        return None
    except (OSError, ValueError) as fehler:
        log.warn("Telegram nicht erreichbar (%s)" % type(fehler).__name__)
        return None

    if not (isinstance(daten, dict) and daten.get("ok")):
        beschreibung = daten.get("description") if isinstance(daten, dict) else None
        log.warn("Telegram lehnt die Nachricht ab: %s" % (beschreibung or "ohne Angabe"))
        return None
    ergebnis = daten.get("result")
    return ergebnis if isinstance(ergebnis, dict) else {}


def sende(token, chat_id, text, oeffner=None):
    """Schickt text in den Chat. True nur, wenn Telegram die Nachricht annimmt."""
    return _rufe(token, "sendMessage", {"chat_id": chat_id, "text": text}, oeffner) is not None


def _lade_letzte(pfad):
    """Die zuletzt gesendete Seriennachricht oder None."""
    try:
        with open(pfad, encoding="utf-8") as fh:
            daten = json.load(fh)
        return {
            "chat_id": daten["chat_id"],
            "message_id": daten["message_id"],
            "titel": daten["titel"],
            "zeit": daten["zeit"],
            "staffeln": {int(s): list(e) for s, e in daten["staffeln"].items()},
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _speichere_letzte(pfad, letzte):
    try:
        with open(pfad, "w", encoding="utf-8") as fh:
            json.dump(letzte or {}, fh, ensure_ascii=False, indent=2)
    except OSError as ausnahme:
        log.warn("Letzte Telegram-Nachricht nicht gemerkt: %s" % ausnahme)


def _ergaenzt(letzte, eintrag, chat_id, jetzt):
    """Die Staffeln der letzten Nachricht plus die des Eintrags, oder None,
    wenn der Eintrag eine eigene Nachricht braucht."""
    if not (letzte and eintrag["typ"] == "serie"
            and letzte["titel"] == eintrag["titel"]
            and letzte["chat_id"] == chat_id
            and 0 <= jetzt - letzte["zeit"] <= _SAMMELFENSTER):
        return None
    staffeln = {s: list(e) for s, e in letzte["staffeln"].items()}
    for staffel, episoden in _staffeln(eintrag).items():
        staffeln[staffel] = sorted(set(staffeln.get(staffel, [])) | set(episoden))
    return staffeln


def melde(cfg, eintraege, oeffner=None, merkpfad=None, jetzt=None):
    """Meldet jeden Eintrag. Liefert die Zahl der zugestellten Meldungen.

    Gehoert ein Eintrag zur selben Serie wie die letzte Nachricht, ersetzt eine
    um die neuen Folgen ergaenzte Nachricht die alte. Telegram kann eine
    bearbeitete Nachricht nicht ans Ende des Verlaufs holen, deshalb wird neu
    gesendet und die alte geloescht, und zwar still: es klingelt nur bei der
    ersten Folge. merkpfad ist die Datei, in der die letzte Nachricht ueber
    Takte und Neustarts hinweg steht.
    """
    if not cfg.telegram_aktiv():
        return 0
    jetzt = time.time() if jetzt is None else jetzt
    token, chat_id = cfg.telegram_token, cfg.telegram_chat_id
    vorher = letzte = _lade_letzte(merkpfad) if merkpfad else None
    zugestellt = 0

    for eintrag in eintraege:
        felder = {"chat_id": chat_id}
        staffeln = _ergaenzt(letzte, eintrag, chat_id, jetzt)
        if staffeln is not None:
            eintrag = {"typ": "serie", "titel": eintrag["titel"], "staffeln": staffeln}
            felder["disable_notification"] = "true"
        felder["text"] = text_fuer(eintrag, cfg.telegram_text_film, cfg.telegram_text_serie)

        ergebnis = _rufe(token, "sendMessage", felder, oeffner)
        if ergebnis is None:
            continue
        zugestellt += 1
        if staffeln is not None:
            # Erst nach dem Senden loeschen, sonst steht bei einem Fehler nichts da.
            _rufe(token, "deleteMessage",
                  {"chat_id": chat_id, "message_id": letzte["message_id"]}, oeffner)
        letzte = None
        if eintrag["typ"] == "serie" and ergebnis.get("message_id") is not None:
            letzte = {
                "chat_id": chat_id, "message_id": ergebnis["message_id"],
                "titel": eintrag["titel"], "zeit": jetzt,
                "staffeln": {s: sorted(set(e)) for s, e in _staffeln(eintrag).items()},
            }

    if merkpfad and letzte != vorher:
        _speichere_letzte(merkpfad, letzte)
    return zugestellt

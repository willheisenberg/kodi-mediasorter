"""Bestimmt den Zielordner zu einem erkannten Titel.

Zuerst die Stufen ohne Netzwerk, danach die Online-Stufen.
"""
import json
import os
import re

import log

_JAHR_UND_REST = re.compile(r"\b(19|20)\d{2}\b.*$")


def _woerter(titel):
    """Titel in Kleinbuchstaben-Woerter zerlegen, Jahr und Release-Rest weg."""
    rumpf = _JAHR_UND_REST.sub("", titel)
    return [w.lower() for w in re.split(r"[\s._-]+", rumpf) if w]


def passt_abkuerzung(kuerzel, titel):
    """Laesst sich kuerzel als Kette von Wortanfaengen von titel lesen?

    neohar -> Neon Harbor, dee.si -> Deep Signal, tso -> The Silent Order.
    nbs -> Nebula Station dagegen nicht, das ist eine Silbenabkuerzung.
    """
    rein = re.sub(r"[^a-z0-9]", "", kuerzel.lower())
    if not rein:
        return False
    woerter = _woerter(titel)

    def suche(pos, wort_index):
        if pos == len(rein):
            return True
        if wort_index >= len(woerter):
            return False
        if suche(pos, wort_index + 1):          # dieses Wort ueberspringen
            return True
        wort = woerter[wort_index]
        for laenge in range(1, len(wort) + 1):
            if pos + laenge > len(rein):
                break
            if rein[pos : pos + laenge] == wort[:laenge] and suche(pos + laenge, wort_index + 1):
                return True
        return False

    return suche(0, 0)


def vorhandene_serien(serien_pfad):
    """Ordnernamen unterhalb des Serienziels."""
    try:
        return [
            n for n in os.listdir(serien_pfad)
            if os.path.isdir(os.path.join(serien_pfad, n)) and not n.startswith(".")
        ]
    except OSError:
        return []


def _normal(text):
    return re.sub(r"[\s._-]+", " ", text.strip().lower())


def _kompakt(text):
    """Nur Buchstaben und Ziffern: 'Night Signal' und 'nightsignal' werden gleich."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def finde_bestehenden_ordner(titel, vorhandene):
    """Erst exakt ohne Ruecksicht auf Schreibweise, dann per Abkuerzung.

    Bei mehr als einem Abkuerzungstreffer wird None geliefert, damit eine
    Verwechslung lieber in der Warteschlange landet als am falschen Ort.
    """
    normal = _normal(titel)
    kompakt = _kompakt(titel)
    for ordner in vorhandene:
        if _normal(ordner) == normal or (kompakt and _kompakt(ordner) == kompakt):
            return ordner

    treffer = [o for o in vorhandene if passt_abkuerzung(titel, o)]
    if len(treffer) == 1:
        return treffer[0]
    if len(treffer) > 1:
        log.info("Abkürzung %r passt auf mehrere Ordner: %s" % (titel, treffer))
    return None


class Cache:
    """Merkt sich einmal geklaerte Zuordnungen dauerhaft."""

    def __init__(self, pfad):
        self.pfad = pfad
        self._daten = {}
        try:
            with open(pfad, encoding="utf-8") as fh:
                geladen = json.load(fh)
            if isinstance(geladen, dict):
                self._daten = geladen
        except (OSError, ValueError) as ausnahme:
            log.debug("Cache nicht geladen: %s" % ausnahme)

    def hole(self, schluessel):
        return self._daten.get(schluessel.lower())

    def setze(self, schluessel, wert):
        self._daten[schluessel.lower()] = wert

    def speichere(self):
        try:
            ordner = os.path.dirname(self.pfad)
            if ordner:
                os.makedirs(ordner, exist_ok=True)
            with open(self.pfad, "w", encoding="utf-8") as fh:
                json.dump(self._daten, fh, ensure_ascii=False, indent=2)
        except OSError as ausnahme:
            log.warn("Cache nicht gespeichert: %s" % ausnahme)


# --- Online-Stufen 1, 4 und 5 ---

import struct
import urllib.error
import urllib.parse
import urllib.request

# Der Score allein trennt nicht: Palace of the Sun (1.60) gegen die Doku
# Enter the Palace of the Sun (1.33) ist eindeutig, Nebula Station 2003
# gegen 1978 (1.18 zu 1.18) nicht. Entscheidend ist Namensgleichheit, nicht der
# Abstand. Der Faktor dient nur noch als Untergrenze bei verschiedenen Namen.
MINDESTVORSPRUNG = 1.15
_ZEITLIMIT = 15
_IMDB = re.compile(r"(?i)\btt(\d{7,9})\b")
_NFO_ENDUNGEN = (".nfo", ".txt")


def _oeffne(oeffner, ziel):
    return (oeffner or urllib.request.urlopen)(ziel, timeout=_ZEITLIMIT)


def _json_von(oeffner, ziel):
    try:
        with _oeffne(oeffner, ziel) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        if fehler.code == 404:
            return None
        log.warn("HTTP %s bei %s" % (fehler.code, ziel))
        return None
    except (OSError, ValueError) as fehler:
        log.warn("Abruf fehlgeschlagen: %s (%s)" % (ziel, fehler))
        return None


def imdb_id_aus_ordner(ordner):
    """Erste IMDb-ID aus einer NFO- oder TXT-Datei im Ordner.

    Scene-NFOs sind haeufig CP437-ASCII-Art, deshalb wird tolerant dekodiert.
    """
    try:
        eintraege = sorted(os.listdir(ordner))
    except OSError:
        return None

    for name in eintraege:
        if not name.lower().endswith(_NFO_ENDUNGEN):
            continue
        try:
            with open(os.path.join(ordner, name), "rb") as fh:
                roh = fh.read(200000)
        except OSError:
            continue
        for kodierung in ("utf-8", "cp437", "latin-1"):
            try:
                text = roh.decode(kodierung)
            except UnicodeDecodeError:
                continue
            treffer = _IMDB.search(text)
            if treffer:
                return "tt" + treffer.group(1)
    return None


def tvmaze_per_imdb(tt, oeffner=None):
    """Serienname zur IMDb-ID. None bedeutet: keine Serie, also ein Film."""
    url = "https://api.tvmaze.com/lookup/shows?imdb=" + urllib.parse.quote(tt)
    daten = _json_von(oeffner, url)
    if isinstance(daten, dict) and daten.get("name"):
        return daten["name"]
    return None


def tvmaze_per_name(titel, oeffner=None):
    """Serienname zur Namenssuche, nur bei klarem Vorsprung des besten Treffers."""
    url = "https://api.tvmaze.com/search/shows?q=" + urllib.parse.quote(titel)
    daten = _json_von(oeffner, url)
    if not isinstance(daten, list) or not daten:
        return None

    bester = daten[0]
    name = (bester.get("show") or {}).get("name")
    if not name:
        return None

    if len(daten) > 1:
        zweiter = daten[1]
        zweiter_name = (zweiter.get("show") or {}).get("name") or ""

        # Echte Ambiguitaet: zwei Serien gleichen Namens, etwa Nebula
        # Galactica 2003 und 1978. Kein Score kann das entscheiden.
        if _normal(zweiter_name) == _normal(name):
            log.info("TVmaze mehrdeutig für %r: %s existiert mehrfach" % (titel, name))
            return None

        # Verschiedene Namen: exakter Treffer gewinnt immer, sonst Vorsprung
        if _normal(titel) != _normal(name):
            bester_score = bester.get("score") or 0.0
            zweiter_score = zweiter.get("score") or 0.0
            if zweiter_score > 0 and bester_score < zweiter_score * MINDESTVORSPRUNG:
                log.info(
                    "TVmaze mehrdeutig für %r: %.2f gegen %.2f"
                    % (titel, bester_score, zweiter_score)
                )
                return None
    return name


_WIKIDATA = "https://www.wikidata.org/w/api.php?format=json&"
_WIKIDATA_TREFFER = 5
_WIKIDATA_AGENT = (
    "service.mediasorter/0.1.0 (https://github.com/willheisenberg/kodi-mediasorter)"
)
_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _gefaltet(text):
    """Wie _kompakt, aber Säure und Saeure werden gleich."""
    return _kompakt(text.lower().translate(_UMLAUTE))


def _wikidata(oeffner, abfrage):
    # Wikimedia verlangt einen User-Agent mit Kontaktangabe und drosselt sonst.
    return _json_von(oeffner, urllib.request.Request(
        _WIKIDATA + abfrage, headers={"User-Agent": _WIKIDATA_AGENT}
    ))


def _wikidata_wert(entitaet, eigenschaft):
    for aussage in (entitaet.get("claims") or {}).get(eigenschaft) or []:
        wert = ((aussage.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(wert, str) and wert:
            return wert
    return None


def wikidata_shows(titel, oeffner=None):
    """Serien zu einem uebersetzten Titel, als Liste von (exakt, TVmaze-Show).

    TVmaze kennt nur Originaltitel: Salz Fett Saeure Hitze findet dort nichts.
    Wikidata fuehrt den deutschen Titel und dazu die TVmaze- oder IMDb-Nummer
    der Serie. Eintraege ohne eine der beiden Nummern, etwa das Buch zur
    Serie, fallen weg, ebenso Filme, die TVmaze nicht kennt.

    exakt heisst: Bezeichnung oder Alias gleicht dem Suchtitel bis auf
    Satzzeichen und Umlautschreibweise. Die Volltextsuche liefert auch
    Aehnliches, und nur ein exakter Treffer darf ohne Rueckfrage zaehlen.
    """
    gesucht = _gefaltet(titel)
    if not gesucht:
        return []
    daten = _wikidata(oeffner, "action=query&list=search&srlimit=%d&srsearch=%s"
                      % (_WIKIDATA_TREFFER, urllib.parse.quote(titel)))
    kennungen = [t.get("title") for t in ((daten or {}).get("query") or {}).get("search") or []]
    kennungen = [k for k in kennungen if k]
    if not kennungen:
        return []
    daten = _wikidata(oeffner, "action=wbgetentities&props=labels%7Caliases%7Cclaims"
                      "&languages=de%7Cen&ids=" + "%7C".join(kennungen))
    entitaeten = (daten or {}).get("entities") or {}

    gefunden = {}
    for kennung in kennungen:
        entitaet = entitaeten.get(kennung) or {}
        tvmaze = _wikidata_wert(entitaet, "P8600")
        imdb = _wikidata_wert(entitaet, "P345")
        if tvmaze:
            show = _json_von(oeffner, "https://api.tvmaze.com/shows/"
                             + urllib.parse.quote(tvmaze))
        elif imdb:
            show = _json_von(oeffner, "https://api.tvmaze.com/lookup/shows?imdb="
                             + urllib.parse.quote(imdb))
        else:
            continue
        if not (isinstance(show, dict) and show.get("name")
                and isinstance(show.get("id"), int)):
            continue
        namen = [l.get("value") or "" for l in (entitaet.get("labels") or {}).values()]
        for liste in (entitaet.get("aliases") or {}).values():
            namen.extend(a.get("value") or "" for a in liste)
        exakt = any(_gefaltet(n) == gesucht for n in namen)
        vorher = gefunden.get(show["id"])
        gefunden[show["id"]] = (exakt or bool(vorher and vorher[0]), show)
    return list(gefunden.values())


def serien_vorschlaege(titel, vorhandene, oeffner=None, weitere=()):
    """Alle Suchtreffer mit Jahr, Sender/Land und stabiler ID fuer die Auswahl.

    weitere sind TVmaze-Shows aus anderer Quelle, etwa wikidata_shows().
    """
    vorschlaege = [{"id": "ordner:" + n, "ziel": n,
                    "beschreibung": n + " (vorhandener Serienordner)"}
                   for n in vorhandene if passt_abkuerzung(titel, n)]
    url = "https://api.tvmaze.com/search/shows?q=" + urllib.parse.quote(titel)
    daten = _json_von(oeffner, url)
    shows = {}
    for eintrag in daten if isinstance(daten, list) else []:
        show = eintrag.get("show") or {}
        if isinstance(show.get("id"), int) and show.get("name"):
            shows[show["id"]] = show
    for show in weitere:
        shows.setdefault(show["id"], show)
    for sid, show in shows.items():
        name = show["name"]
        jahr = (show.get("premiered") or "")[:4]
        sender = show.get("network") or show.get("webChannel") or {}
        land = (sender.get("country") or {}).get("name") or ""
        doppelt = sum(_normal(s["name"]) == _normal(name) for s in shows.values()) > 1
        ziel = "%s (%s)" % (name, jahr or sid) if doppelt else name
        if doppelt and sum(s["name"] == name and (s.get("premiered") or "")[:4] == jahr
                           for s in shows.values()) > 1:
            ziel += " [TVmaze %s]" % sid
        vorschlaege.append({
            "id": "tvmaze:%s" % sid, "ziel": ziel,
            "beschreibung": " | ".join(str(s) for s in (
                name, jahr or "Startjahr unbekannt", sender.get("name"), land,
                show.get("language"), "https://www.tvmaze.com/shows/%s" % sid,
            ) if s),
        })
    return vorschlaege


def opensubtitles_hash(pfad):
    """64-Bit-Hash aus Dateigroesse sowie den ersten und letzten 64 KB."""
    block = 65536
    try:
        laenge = os.path.getsize(pfad)
        if laenge < block * 2:
            return None
        wert = laenge
        with open(pfad, "rb") as fh:
            for _ in range(block // 8):
                (teil,) = struct.unpack("<q", fh.read(8))
                wert = (wert + teil) & 0xFFFFFFFFFFFFFFFF
            fh.seek(laenge - block)
            for _ in range(block // 8):
                (teil,) = struct.unpack("<q", fh.read(8))
                wert = (wert + teil) & 0xFFFFFFFFFFFFFFFF
    except (OSError, struct.error) as fehler:
        log.debug("Hash nicht berechenbar: %s (%s)" % (pfad, fehler))
        return None
    return "%016x" % wert


def opensubtitles_per_hash(hashwert, api_key, oeffner=None):
    """Titel, Staffel und Episode zum Dateihash. None ohne Key oder ohne Treffer."""
    if not api_key:
        return None

    url = ("https://api.opensubtitles.com/api/v1/subtitles?moviehash="
           + urllib.parse.quote(hashwert))
    anfrage = urllib.request.Request(
        url, headers={"Api-Key": api_key, "User-Agent": "service.mediasorter v0.1.0"}
    )
    daten = _json_von(oeffner, anfrage)

    eintraege = (daten or {}).get("data") or []
    if not eintraege:
        return None

    details = ((eintraege[0].get("attributes") or {}).get("feature_details") or {})
    if not details.get("title"):
        return None
    return {
        "titel": details["title"],
        "staffel": details.get("season_number"),
        "episode": details.get("episode_number"),
        "typ": "episode" if details.get("feature_type") == "Episode" else "film",
    }


def tvmaze_zusammengeschrieben(titel, oeffner=None):
    """Serie zu einem zusammengeschriebenen Titel wie nightsignal.

    TVmaze findet solche Tokens nicht, wohl aber ihre Wortanfaenge. Gefragt
    wird deshalb mit wachsenden Praefixen, akzeptiert wird nur ein Seriename,
    der ohne Leer- und Satzzeichen exakt dem Token entspricht. Tragen zwei
    Serien diesen Namen, ist nichts entscheidbar.
    """
    token = titel.strip().lower()
    if not re.fullmatch(r"[a-z0-9]{6,}", token):
        return None

    for laenge in range(4, len(token) - 1):
        url = ("https://api.tvmaze.com/search/shows?q="
               + urllib.parse.quote(token[:laenge]))
        daten = _json_von(oeffner, url)
        if daten is None:
            return None                 # Netzfehler oder Limit: nicht weiterbohren
        if not isinstance(daten, list):
            continue
        passend = {}
        for eintrag in daten:
            show = eintrag.get("show") or {}
            name = show.get("name") or ""
            if name and _kompakt(name) == token:
                passend[show.get("id", name)] = name
        if len(passend) == 1:
            return next(iter(passend.values()))
        if len(passend) > 1:
            log.info("TVmaze mehrdeutig für %r: %s existiert mehrfach"
                     % (titel, next(iter(passend.values()))))
            return None
    return None

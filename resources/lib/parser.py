"""Zerlegt Datei- und Ordnernamen in Typ, Titel, Staffel, Episode und Jahr.

Der gelieferte Titel ist ein Suchbegriff in Kleinschreibung, nicht der spaetere
Zielordnername. Welcher Ordner daraus wird, entscheidet resolver.py.
"""
import datetime
import re

VIDEO_ENDUNGEN = (".mkv", ".mp4", ".avi", ".m4v")

# s01e01, S01E01, s01.e01, s1e1
_EPISODE = re.compile(r"[sS](\d{1,2})[._ -]?[eE](\d{1,3})")
# 1x01
_EPISODE_X = re.compile(r"(?<![a-zA-Z0-9])(\d{1,2})[xX](\d{2,3})(?![0-9])")
# Staffel 1 Folge 2
_EPISODE_DE = re.compile(r"[sS]taffel[._ -]?(\d{1,2})[._ -]?[fF]olge[._ -]?(\d{1,3})")

_JAHR = re.compile(r"(?<![0-9])((?:19|20)\d{2})(?![0-9])")

# Release-Gruppensuffix am Ende, etwa -STM oder -BHX
_GRUPPE = re.compile(r"-[A-Za-z0-9]{2,12}$")
_MARKER = re.compile(
    r"(?i)(?<![a-z0-9])(1080p|720p|2160p|480p|bluray|blu-ray|web-?dl|webrip|web"
    r"|hddvd|hdtv|dvdrip|remux|x264|x265|h264|h265|avc|hevc|german|dl|ac3|dts"
    r"|aac|extended|remastered|repack|internal|proper)(?![a-z0-9])"
)

# Ein echter Release-Ordner nennt Quelle, Codec, Auflaesung und Sprache und
# kommt damit auf mindestens drei verschiedene Marker. Kurznamen wie
# bhx-neohar-x265 haben nur einen und sind kein Titel.
_MARKER_MINDESTZAHL = 3


def basisname(name):
    """Name ohne die letzte Endung."""
    return name.rsplit(".", 1)[0] if "." in name else name


def ist_video(name):
    return name.lower().endswith(VIDEO_ENDUNGEN)


def _normalisiere(text):
    """Trennzeichen zu Leerzeichen, mehrfache Leerzeichen zusammenziehen."""
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\s*-\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _ohne_endung(name):
    if ist_video(name):
        return basisname(name)
    return name


def _erscheinungsjahr(name):
    """Letztes plausibles Jahr im Namen.

    Neon.Harbor.2049.2017 liefert 2017, weil 2049 in der Zukunft liegt und
    damit zum Titel gehoert. 1999.Reise.zum.Mond.1972 liefert 1968, weil
    das letzte plausible Jahr gewinnt.
    """
    grenze = datetime.date.today().year + 1
    treffer = [(m.start(), int(m.group(1))) for m in _JAHR.finditer(name)]
    plausibel = [(pos, jahr) for pos, jahr in treffer if jahr <= grenze]
    return plausibel[-1] if plausibel else (None, None)


def ist_sprechend(name):
    """Laesst sich aus diesem Namen ein Titel ableiten?

    Wahr bei Episodenmuster, plausibler Jahreszahl, oder Release-Gruppensuffix
    zusammen mit einem Quellen- oder Qualitaetsmarker.
    """
    rumpf = _ohne_endung(name)
    if _EPISODE.search(rumpf) or _EPISODE_X.search(rumpf) or _EPISODE_DE.search(rumpf):
        return True
    if _erscheinungsjahr(rumpf)[1] is not None:
        return True

    if not _GRUPPE.search(rumpf):
        return False
    marker = {m.group(1).lower() for m in _MARKER.finditer(rumpf)}
    if len(marker) < _MARKER_MINDESTZAHL:
        return False
    # Vor dem ersten Marker muss ein Titel stehen, nicht nur ein Gruppenkuerzel
    erster = _MARKER.search(rumpf)
    return bool(_normalisiere(rumpf[: erster.start()]))


def parse(name):
    """Zerlegt einen Datei- oder Ordnernamen."""
    rumpf = _ohne_endung(name)

    for muster in (_EPISODE, _EPISODE_X, _EPISODE_DE):
        treffer = muster.search(rumpf)
        if treffer:
            titel = _normalisiere(rumpf[: treffer.start()])
            return {
                "typ": "episode",
                "titel": titel,
                "staffel": int(treffer.group(1)),
                "episode": int(treffer.group(2)),
                "jahr": None,
            }

    pos, jahr = _erscheinungsjahr(rumpf)
    if jahr is not None:
        return {
            "typ": "film",
            "titel": _normalisiere(rumpf[:pos]),
            "staffel": None,
            "episode": None,
            "jahr": jahr,
        }

    # Kein Jahr: Release-Marker und Gruppensuffix abschneiden
    rumpf_ohne_gruppe = _GRUPPE.sub("", rumpf)
    marker = _MARKER.search(rumpf_ohne_gruppe)
    titel = rumpf_ohne_gruppe[: marker.start()] if marker else rumpf_ohne_gruppe
    return {
        "typ": "film",
        "titel": _normalisiere(titel),
        "staffel": None,
        "episode": None,
        "jahr": None,
    }

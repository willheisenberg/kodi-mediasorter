"""Baut aus einem Kandidaten und einem aufgeloesten Titel die Zielpfade."""
import collections
import os

import parser
import readiness

Verschiebung = collections.namedtuple("Verschiebung", "quelle ziel grund")

UNTERTITEL_ENDUNGEN = (".srt", ".sub", ".idx", ".sup", ".ass", ".ssa")
FILM_BEGLEITER_ENDUNGEN = UNTERTITEL_ENDUNGEN + (".nfo", ".jpg", ".jpeg", ".png", ".webp", ".tbn")


def film_begleiter(pfad, mit_temporaeren=False):
    """Lose Begleitdateien nur bei eindeutiger Zuordnung zum Videobasisnamen."""
    ordner = os.path.dirname(pfad)
    try:
        namen = sorted(os.listdir(ordner))
    except OSError:
        return []
    videos = [n for n in namen if parser.ist_video(n)
              and not parser.ist_sample(n) and os.path.isfile(os.path.join(ordner, n))]
    treffer = []
    for name in namen:
        pruefname = name
        if mit_temporaeren and readiness.ist_temporaer(name):
            pruefname = parser.basisname(name)
        if not pruefname.lower().endswith(FILM_BEGLEITER_ENDUNGEN):
            continue
        if not os.path.isfile(os.path.join(ordner, name)):
            continue
        basis = parser.basisname(pruefname).lower()
        passend = []
        for video in videos:
            videobasis = parser.basisname(video).lower()
            if basis == videobasis or basis.startswith(tuple(
                    videobasis + trenner for trenner in (".", "-", "_", " "))):
                passend.append(video)
        if passend == [os.path.basename(pfad)]:
            treffer.append(os.path.join(ordner, name))
    return treffer


def season_ordner(nummer):
    return "Season %02d" % int(nummer)


def _season_fuer(staffel, episode):
    """Episode 0 kennzeichnet ein Special und landet in Season 00.

    Entspricht dem vorgefundenen Bestand: Nebula.Station.S01E00 liegt
    unter Season 00, obwohl der Name Staffel 1 nennt.
    """
    if episode == 0:
        return season_ordner(0)
    return season_ordner(staffel)


def episoden_im_ordner(ordner):
    """Videodateien nach (staffel, episode) gruppiert."""
    gefunden = collections.defaultdict(list)
    try:
        eintraege = sorted(os.listdir(ordner))
    except OSError:
        return {}

    for name in eintraege:
        if not parser.ist_video(name):
            continue
        info = parser.parse(name)
        if info["typ"] == "episode":
            gefunden[(info["staffel"], info["episode"])].append(name)
    return dict(gefunden)


def _begleiter(ordner, videoname):
    """Untertiteldateien mit demselben Basisnamen wie das Video."""
    basis = parser.basisname(videoname).lower()
    treffer = []
    try:
        eintraege = sorted(os.listdir(ordner))
    except OSError:
        return treffer

    for name in eintraege:
        if name == videoname or not name.lower().endswith(UNTERTITEL_ENDUNGEN):
            continue
        if parser.basisname(name).lower().startswith(basis):
            treffer.append(name)
    return treffer


def plane(kandidat, titel, ziel_serien, ziel_filme):
    """Liste von Verschiebungen. Leer heisst: gehoert in die Warteschlange."""
    pfad = kandidat["pfad"]
    name = kandidat["name"]
    info = parser.parse(name)

    if kandidat["ist_ordner"]:
        episoden = episoden_im_ordner(pfad)

        if len(episoden) > 1:
            if titel is None:
                return []
            plan = []
            for (staffel, episode), dateien in sorted(episoden.items()):
                zielordner = os.path.join(
                    ziel_serien, titel, _season_fuer(staffel, episode)
                )
                for videoname in dateien:
                    plan.append(Verschiebung(
                        os.path.join(pfad, videoname),
                        os.path.join(zielordner, videoname),
                        "Staffelpaket aufgebrochen",
                    ))
                    for begleiter in _begleiter(pfad, videoname):
                        plan.append(Verschiebung(
                            os.path.join(pfad, begleiter),
                            os.path.join(zielordner, begleiter),
                            "Untertitel zur Episode",
                        ))
            return plan

        if len(episoden) == 1:
            staffel, episode = next(iter(episoden))
        elif info["typ"] == "episode":
            staffel, episode = info["staffel"], info["episode"]
        else:
            return [Verschiebung(pfad, os.path.join(ziel_filme, name), "Filmordner")]

        if titel is None:
            return []
        return [Verschiebung(
            pfad,
            os.path.join(ziel_serien, titel, _season_fuer(staffel, episode), name),
            "Ordner mit einer Episode",
        )]

    # Einzeldatei
    if info["typ"] == "episode":
        if titel is None:
            return []
        return [Verschiebung(
            pfad,
            os.path.join(
                ziel_serien, titel, _season_fuer(info["staffel"], info["episode"]), name
            ),
            "Einzelne Episode",
        )]

    ordnername = parser.basisname(name)
    # Video zuletzt: bei einem Fehler bleiben die restlichen Begleiter im
    # naechsten Takt ueber den Videokandidaten erneut erreichbar.
    plan = [Verschiebung(
        begleiter, os.path.join(ziel_filme, ordnername, os.path.basename(begleiter)),
        "Begleitdatei zum Film",
    ) for begleiter in film_begleiter(pfad)]
    return plan + [Verschiebung(
        pfad, os.path.join(ziel_filme, ordnername, name), "Film als Einzeldatei"
    )]

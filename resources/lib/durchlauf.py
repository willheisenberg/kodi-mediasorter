"""Ein Takt: scannen, pruefen, aufloesen, planen, verschieben.

Kodi-frei und damit vollstaendig testbar. service.py ruft nur einmal() auf.
"""
import os

import log
import mover
import parser
import pending
import planner
import readiness
import resolver
import scanner


class Zustand:
    """Alles, was ueber einen Takt hinaus bestehen bleibt."""

    def __init__(self, cfg, datenordner):
        self.stabilitaet = readiness.Stabilitaet(cfg.stability_cycles)
        self.cache = resolver.Cache(os.path.join(datenordner, "cache.json"))
        self.warteschlange = pending.Warteschlange(
            os.path.join(datenordner, "queue.json")
        )
        self.protokoll = os.path.join(datenordner, "moves.log")


def _dateien_von(kandidat):
    if not kandidat["ist_ordner"]:
        return [kandidat["pfad"]]
    gefunden = []
    for wurzel, _ordner, namen in os.walk(kandidat["pfad"]):
        gefunden.extend(os.path.join(wurzel, n) for n in namen)
    return gefunden


def _ist_fertig(kandidat, cfg, zustand):
    """Alle vier Lagen plus SFV. True nur, wenn keine Lage widerspricht."""
    pfad = kandidat["pfad"]

    if kandidat["ist_ordner"]:
        if readiness.rar_aktiv(pfad, cfg.rar_quiet_seconds):
            return False
        if readiness.sfv_vollstaendig(pfad) is False:
            return False

    dateien = _dateien_von(kandidat)
    if not dateien:
        return False

    for datei in dateien:
        if readiness.ist_temporaer(os.path.basename(datei)):
            return False
        if parser.ist_video(datei) and readiness.ist_vollstaendig(datei) is False:
            return False
        if not zustand.stabilitaet.pruefe(datei):
            return False
    return True


def _wird_abgespielt(kandidat, spielt_gerade):
    """Laeuft der Kandidat oder eine Datei darin gerade im Player?"""
    for datei in _dateien_von(kandidat):
        if parser.ist_video(datei) and spielt_gerade(datei):
            return True
    return False


def loese_titel(kandidat, cfg, zustand):
    """Die Resolver-Kaskade. None heisst: Film oder Warteschlange."""
    pfad = kandidat["pfad"]
    name = kandidat["name"]
    info = parser.parse(name)
    suchtitel = info["titel"]

    if kandidat["ist_ordner"]:
        # Bei Ordnern entscheidet der Inhalt, nicht der Ordnername.
        # Reacher.S04.COMPLETE... enthaelt kein sXXeYY und saehe sonst wie ein
        # Film aus, obwohl klar benannte Episoden darin liegen.
        episoden = planner.episoden_im_ordner(pfad)
        if not episoden:
            return None                 # Filmordner, braucht keinen Titel
        erste = sorted(episoden.items())[0][1][0]
        aus_datei = parser.parse(erste)["titel"]
        if aus_datei:
            suchtitel = aus_datei       # Stufe 0: Dateiname im Ordner ist praeziser
    elif info["typ"] == "film":
        return None                     # Filme brauchen keinen Titel-Lookup

    vorhandene = resolver.vorhandene_serien(cfg.ziel_serien())

    # Stufe 2: Cache
    if suchtitel:
        gemerkt = zustand.cache.hole(suchtitel)
        if gemerkt:
            return gemerkt

    # Stufe 3: bestehende Ordner, exakt oder per Abkuerzung. Bewusst ohne
    # Cache-Eintrag: lokal und billig, und ein Cache wuerde nach dem
    # Umbenennen eines Serienordners ins Leere zeigen.
    if suchtitel:
        treffer = resolver.finde_bestehenden_ordner(suchtitel, vorhandene)
        if treffer:
            return treffer

    # Stufe 1: IMDb-ID aus NFO
    ordner = pfad if kandidat["ist_ordner"] else os.path.dirname(pfad)
    tt = resolver.imdb_id_aus_ordner(ordner)
    if tt:
        name_von_imdb = resolver.tvmaze_per_imdb(tt)
        if name_von_imdb:
            zustand.cache.setze(suchtitel or tt, name_von_imdb)
            return name_von_imdb

    # Stufe 4: Namenssuche
    if suchtitel:
        gefunden = resolver.tvmaze_per_name(suchtitel)
        if gefunden:
            zustand.cache.setze(suchtitel, gefunden)
            return gefunden

    # Stufe 5: Inhaltserkennung, nur mit API-Key und nur fuer Einzeldateien
    if cfg.opensubtitles_api_key and not kandidat["ist_ordner"]:
        hashwert = resolver.opensubtitles_hash(pfad)
        if hashwert:
            daten = resolver.opensubtitles_per_hash(
                hashwert, cfg.opensubtitles_api_key
            )
            if daten and daten.get("titel"):
                zustand.cache.setze(suchtitel or hashwert, daten["titel"])
                return daten["titel"]

    return None


def einmal(cfg, zustand, spielt_gerade=None):
    """Ein vollstaendiger Takt.

    spielt_gerade ist eine Funktion pfad -> bool. service.py reicht
    library.spielt_gerade durch; in Tests bleibt sie None. So wird die
    Player-Pruefung erfuellt, ohne dass durchlauf.py Kodi importiert.
    """
    zaehler = {"verschoben": 0, "wartend": 0, "uebersprungen": 0, "zielpfade": set()}

    zustand.warteschlange.aufraeumen()
    kandidaten = scanner.finde_kandidaten(cfg.watch_path, cfg.ignoriert())

    for kandidat in kandidaten:
        if not _ist_fertig(kandidat, cfg, zustand):
            zaehler["uebersprungen"] += 1
            continue

        if spielt_gerade is not None and _wird_abgespielt(kandidat, spielt_gerade):
            log.info("Wird gerade abgespielt, Takt übersprungen: %s" % kandidat["pfad"])
            zaehler["uebersprungen"] += 1
            continue

        titel = loese_titel(kandidat, cfg, zustand)
        plan = planner.plane(kandidat, titel, cfg.ziel_serien(), cfg.ziel_filme())

        if not plan:
            zustand.warteschlange.eintragen(kandidat["pfad"], "Titel nicht auflösbar")
            zaehler["wartend"] += 1
            continue

        offen = False
        for schritt in plan:
            ergebnis = mover.verschiebe(schritt, cfg.dry_run, zustand.protokoll)
            if ergebnis == mover.ERFOLG:
                zaehler["verschoben"] += 1
                zaehler["zielpfade"].add(os.path.dirname(schritt.ziel))
                zustand.stabilitaet.vergiss(schritt.quelle)
            elif ergebnis in (mover.KOLLISION, mover.FEHLER):
                offen = True

        if offen:
            zustand.warteschlange.eintragen(
                kandidat["pfad"], "Ziel existiert bereits oder Fehler"
            )
            zaehler["wartend"] += 1
        else:
            zustand.warteschlange.entfernen(kandidat["pfad"])
            if kandidat["ist_ordner"] and not cfg.dry_run:
                mover.raeume_leeren_ordner(kandidat["pfad"], cfg.dry_run)

    zustand.cache.speichere()
    zustand.warteschlange.speichere()
    log.info(
        "Takt beendet: %d verschoben, %d wartend, %d übersprungen"
        % (zaehler["verschoben"], zaehler["wartend"], zaehler["uebersprungen"])
    )
    return zaehler

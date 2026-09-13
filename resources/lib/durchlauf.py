"""Ein Takt: scannen, pruefen, aufloesen, planen, verschieben.

Kodi-frei und damit vollstaendig testbar. service.py ruft nur einmal() auf.
"""
import os
import time

import log
import mover
import parser
import pending
import planner
import readiness
import resolver
import scanner
import zuordnung


# Wie lange ein fehlgeschlagener Online-Lookup ruht. Ohne diese Sperre fragte
# die Warteschlange TVmaze fuer jeden wartenden Eintrag bei jedem Takt neu.
SPERRE_SEKUNDEN = 6 * 3600


class Zustand:
    """Alles, was ueber einen Takt hinaus bestehen bleibt."""

    def __init__(self, cfg, datenordner):
        self.stabilitaet = readiness.Stabilitaet(cfg.stability_cycles)
        self.cache = resolver.Cache(os.path.join(datenordner, "cache.json"))
        self.warteschlange = pending.Warteschlange(
            os.path.join(datenordner, "queue.json")
        )
        self.protokoll = os.path.join(datenordner, "moves.log")
        self.zuordnungen = zuordnung.Zuordnungen(cfg.watch_path, datenordner)
        # Nur im Speicher: ein Neustart des Dienstes hebt alle Sperren auf.
        self.uhr = time.time
        self._sperre = {}

    def gesperrt(self, schluessel):
        bis = self._sperre.get(schluessel)
        return bis is not None and self.uhr() < bis

    def sperren(self, schluessel):
        self._sperre[schluessel] = self.uhr() + SPERRE_SEKUNDEN


def _dateien_von(kandidat):
    if not kandidat["ist_ordner"]:
        dateien = [kandidat["pfad"]]
        if parser.parse(kandidat["name"])["typ"] == "film":
            dateien.extend(planner.film_begleiter(kandidat["pfad"], mit_temporaeren=True))
        return dateien
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

    alle_stabil = True
    for datei in dateien:
        if readiness.ist_temporaer(os.path.basename(datei)):
            return False
        if parser.ist_video(datei) and readiness.ist_vollstaendig(datei) is False:
            return False
        if not zustand.stabilitaet.pruefe(datei):
            alle_stabil = False
    return alle_stabil


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
    titelquelle = name

    if kandidat["ist_ordner"]:
        # Bei Ordnern entscheidet der Inhalt, nicht der Ordnername.
        # Ranger.S04.COMPLETE... enthaelt kein sXXeYY und saehe sonst wie ein
        # Film aus, obwohl klar benannte Episoden darin liegen.
        episoden = planner.episoden_im_ordner(pfad)
        if not episoden:
            return None                 # Filmordner, braucht keinen Titel
        erste = sorted(episoden.items())[0][1][0]
        if parser.parse(erste)["titel"]:
            titelquelle = erste         # Stufe 0: Dateiname im Ordner ist praeziser
    elif parser.parse(name)["typ"] == "film":
        return None                     # Filme brauchen keinen Titel-Lookup

    kandidaten = parser.titel_kandidaten(titelquelle) or parser.titel_kandidaten(name)
    haupttitel = kandidaten[0] if kandidaten else None
    vorhandene = resolver.vorhandene_serien(cfg.ziel_serien())

    def merke(wert, *schluessel):
        for s in schluessel:
            if s:
                zustand.cache.setze(s, wert)
        return wert

    # Manuelle Entscheidungen gelten sofort, auch waehrend der Online-Sperre.
    for k in kandidaten:
        if zustand.zuordnungen.bekannt(k):
            auswahl = zustand.zuordnungen.auswahl(k)
            return merke(auswahl, haupttitel, k) if auswahl else None

    # Stufe 2: Cache
    for k in kandidaten:
        gemerkt = zustand.cache.hole(k)
        if gemerkt:
            return gemerkt

    # Stufe 3: bestehende Ordner, exakt, zusammengeschrieben oder per
    # Abkuerzung. Bewusst ohne Cache-Eintrag und ohne Sperre: lokal und
    # billig, und ein Cache wuerde nach dem Umbenennen ins Leere zeigen.
    for k in kandidaten:
        treffer = resolver.finde_bestehenden_ordner(k, vorhandene)
        if treffer:
            return treffer

    # Stufe 1: IMDb-ID aus NFO
    ordner = pfad if kandidat["ist_ordner"] else os.path.dirname(pfad)
    tt = resolver.imdb_id_aus_ordner(ordner)
    if tt and not zustand.gesperrt("imdb:" + tt):
        name_von_imdb = resolver.tvmaze_per_imdb(tt)
        if name_von_imdb:
            return merke(name_von_imdb, haupttitel or tt)
        zustand.sperren("imdb:" + tt)

    # Stufe 4: Namenssuche, bei zusammengeschriebenen Titeln per Wortanfang
    for k in kandidaten:
        # Ein gekuerzter Kandidat wie nbs ist fuer Stufe 3 wertvoll, online
        # aber zu kurz: TVmaze faende womoeglich eine Serie, die zufaellig so heisst.
        if k != haupttitel and len(k.replace(" ", "")) < 6:
            continue
        if zustand.gesperrt("titel:" + k):
            continue
        gefunden = resolver.tvmaze_per_name(k)
        if not gefunden and " " not in k:
            gefunden = resolver.tvmaze_zusammengeschrieben(k)
        if gefunden:
            return merke(gefunden, haupttitel, k)
        zustand.sperren("titel:" + k)

    # Stufe 5: Inhaltserkennung, nur mit API-Key und nur fuer Einzeldateien
    if (cfg.opensubtitles_api_key and not kandidat["ist_ordner"]
            and not zustand.gesperrt("hash:" + pfad)):
        hashwert = resolver.opensubtitles_hash(pfad)
        if hashwert:
            daten = resolver.opensubtitles_per_hash(
                hashwert, cfg.opensubtitles_api_key
            )
            if daten and daten.get("titel"):
                return merke(daten["titel"], haupttitel or hashwert)
        zustand.sperren("hash:" + pfad)

    if haupttitel and not zustand.gesperrt("auswahl:" + haupttitel):
        vorschlaege = resolver.serien_vorschlaege(haupttitel, vorhandene)
        zustand.zuordnungen.vorschlagen(haupttitel, name, vorschlaege)
        zustand.sperren("auswahl:" + haupttitel)
    return None


def _scanziel(ziel, cfg):
    """Ordner, den Kodi nach dem Verschieben scannen soll.

    Die erste Ebene unter dem Serien- bzw. Filmziel, also der Serienordner oder
    der Filmordner. Nachgewiesen ist der Scan auf Serienordner-Ebene, und die
    ganze Filmquelle zu scannen waere fuer einen einzelnen Film unnoetig teuer.
    """
    for wurzel in (cfg.ziel_serien(), cfg.ziel_filme()):
        rest = os.path.relpath(ziel, wurzel)
        if rest != "." and not rest.startswith(".."):
            return os.path.join(wurzel, rest.split(os.sep)[0])
    return os.path.dirname(ziel)


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
        # Keine Begleitdateien zu einem bereits vorhandenen anderen Film legen.
        if any(os.path.lexists(schritt.ziel) for schritt in plan):
            zustand.warteschlange.eintragen(kandidat["pfad"], "Ziel existiert bereits")
            zaehler["wartend"] += 1
            continue
        for schritt in plan:
            ergebnis = mover.verschiebe(schritt, cfg.dry_run, zustand.protokoll)
            if ergebnis == mover.ERFOLG:
                zaehler["verschoben"] += 1
                zaehler["zielpfade"].add(_scanziel(schritt.ziel, cfg))
                zustand.stabilitaet.vergiss(schritt.quelle)
            elif ergebnis in (mover.KOLLISION, mover.FEHLER):
                offen = True
                break

        if offen:
            zustand.warteschlange.eintragen(
                kandidat["pfad"], "Ziel existiert bereits oder Fehler"
            )
            zaehler["wartend"] += 1
        else:
            zustand.warteschlange.entfernen(kandidat["pfad"])
            if not cfg.dry_run and titel:
                zustand.zuordnungen.erledigt(titel)
            if kandidat["ist_ordner"] and not cfg.dry_run:
                mover.raeume_leeren_ordner(kandidat["pfad"], cfg.dry_run)

    zustand.cache.speichere()
    zustand.zuordnungen.aufraeumen()
    zustand.warteschlange.speichere()
    log.info(
        "Takt beendet: %d verschoben, %d wartend, %d übersprungen"
        % (zaehler["verschoben"], zaehler["wartend"], zaehler["uebersprungen"])
    )
    return zaehler

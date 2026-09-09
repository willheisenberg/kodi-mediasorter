"""Warteschlange fuer Kandidaten, die sich nicht aufloesen liessen.

Sie wird bei jedem Takt neu bewertet. Ein Eintrag verschwindet, sobald ein
Ordner, eine NFO oder ein Abkuerzungstreffer ihn aufloest, oder wenn die Datei
nicht mehr da ist.

Heisst absichtlich nicht queue.py: service.py stellt resources/lib per
sys.path.insert(0, ...) voran und wuerde damit die Standardbibliothek fuer den
gesamten Kodi-Prozess verdecken.
"""
import datetime
import json
import os

import log


class Warteschlange:
    def __init__(self, pfad):
        self.pfad = pfad
        self._daten = {}
        try:
            with open(pfad, encoding="utf-8") as fh:
                geladen = json.load(fh)
            if isinstance(geladen, dict):
                self._daten = geladen
        except (OSError, ValueError) as ausnahme:
            log.debug("Warteschlange nicht geladen: %s" % ausnahme)

    def eintragen(self, pfad, grund):
        vorhanden = self._daten.get(pfad)
        if vorhanden:
            vorhanden["grund"] = grund
            vorhanden["versuche"] = vorhanden.get("versuche", 0) + 1
        else:
            self._daten[pfad] = {
                "grund": grund,
                "seit": datetime.datetime.now().isoformat(timespec="seconds"),
                "versuche": 1,
            }

    def entfernen(self, pfad):
        self._daten.pop(pfad, None)

    def eintraege(self):
        return [dict(werte, pfad=pfad) for pfad, werte in sorted(self._daten.items())]

    def anzahl(self):
        return len(self._daten)

    def aufraeumen(self):
        """Entfernt Eintraege, deren Datei verschwunden ist. Gibt die Anzahl zurueck."""
        weg = [p for p in self._daten if not os.path.exists(p)]
        for pfad in weg:
            del self._daten[pfad]
        if weg:
            log.info("%d verschwundene Einträge aus der Warteschlange entfernt" % len(weg))
        return len(weg)

    def speichere(self):
        try:
            ordner = os.path.dirname(self.pfad)
            if ordner:
                os.makedirs(ordner, exist_ok=True)
            with open(self.pfad, "w", encoding="utf-8") as fh:
                json.dump(self._daten, fh, ensure_ascii=False, indent=2)
        except OSError as ausnahme:
            log.warn("Warteschlange nicht gespeichert: %s" % ausnahme)

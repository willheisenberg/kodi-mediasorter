"""Listet die obersten Eintraege des ueberwachten Ordners und filtert sie."""
import os

import log
import parser
import readiness


def _enthaelt_video(ordner):
    """Liegt irgendwo unterhalb von ordner eine Videodatei?"""
    for _wurzel, _unterordner, namen in os.walk(ordner):
        if any(parser.ist_video(n) for n in namen):
            return True
    return False


def finde_kandidaten(watch_path, ignoriert):
    """Ordner und Videodateien direkt unterhalb von watch_path.

    Uebersprungen werden: ignorierte Namen, alles mit fuehrendem Punkt,
    Temporaerdateien, Dateien die kein Video sind, und Ordner ohne jede
    Videodatei. Letzteres verhindert, dass ein beliebiger Ordner als
    Filmordner einsortiert wird.
    """
    try:
        eintraege = sorted(os.listdir(watch_path))
    except OSError as ausnahme:
        log.warn("Überwachter Ordner nicht lesbar: %s (%s)" % (watch_path, ausnahme))
        return []

    kandidaten = []
    for name in eintraege:
        if name.startswith(".") or name in ignoriert:
            continue
        if readiness.ist_temporaer(name):
            continue

        pfad = os.path.join(watch_path, name)
        ist_ordner = os.path.isdir(pfad)
        if ist_ordner:
            if not _enthaelt_video(pfad):
                continue
        elif not parser.ist_video(name) or parser.ist_sample(name):
            continue

        kandidaten.append({"pfad": pfad, "name": name, "ist_ordner": ist_ordner})
    return kandidaten

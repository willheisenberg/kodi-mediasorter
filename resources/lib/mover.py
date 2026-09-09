"""Verschiebt Dateien per os.rename und protokolliert jeden Schritt.

Bewusst kein shutil.move: das wuerde bei einem Plattenwechsel stillschweigend
kopieren. Ziele auf anderer Platte lehnt bereits config.validiere() ab.
"""
import datetime
import os

import log

ERFOLG = "erfolg"
KOLLISION = "kollision"
FEHLER = "fehler"
TROCKEN = "trocken"


def _protokolliere(protokoll, status, quelle, ziel, grund):
    if not protokoll:
        return
    zeile = "%s\t%s\t%s\t%s\t%s\n" % (
        datetime.datetime.now().isoformat(timespec="seconds"),
        status.upper(), quelle, ziel, grund,
    )
    try:
        ordner = os.path.dirname(protokoll)
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        with open(protokoll, "a", encoding="utf-8") as fh:
            fh.write(zeile)
    except OSError as ausnahme:
        log.warn("Protokoll nicht schreibbar: %s" % ausnahme)


def verschiebe(v, dry_run, protokoll=None):
    """Verschiebt v.quelle nach v.ziel. Gibt einen der Statuswerte zurueck."""
    if not os.path.exists(v.quelle):
        log.warn("Quelle verschwunden: %s" % v.quelle)
        _protokolliere(protokoll, FEHLER, v.quelle, v.ziel, "Quelle fehlt")
        return FEHLER

    if os.path.exists(v.ziel):
        log.info("Ziel existiert bereits, nichts überschrieben: %s" % v.ziel)
        _protokolliere(protokoll, KOLLISION, v.quelle, v.ziel, v.grund)
        return KOLLISION

    if dry_run:
        log.info("[Trockenlauf] %s -> %s (%s)" % (v.quelle, v.ziel, v.grund))
        _protokolliere(protokoll, TROCKEN, v.quelle, v.ziel, v.grund)
        return TROCKEN

    try:
        ordner = os.path.dirname(v.ziel)
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        os.rename(v.quelle, v.ziel)
    except OSError as ausnahme:
        log.error("Verschieben fehlgeschlagen: %s -> %s (%s)" % (v.quelle, v.ziel, ausnahme))
        _protokolliere(protokoll, FEHLER, v.quelle, v.ziel, str(ausnahme))
        return FEHLER

    log.info("Verschoben: %s -> %s" % (v.quelle, v.ziel))
    _protokolliere(protokoll, ERFOLG, v.quelle, v.ziel, v.grund)
    return ERFOLG


def raeume_leeren_ordner(pfad, dry_run):
    """Entfernt pfad nur, wenn er leer ist. Gibt True zurueck, wenn entfernt."""
    try:
        if os.listdir(pfad):
            return False
    except OSError:
        return False

    if dry_run:
        log.info("[Trockenlauf] leerer Ordner würde entfernt: %s" % pfad)
        return True

    try:
        os.rmdir(pfad)
    except OSError as ausnahme:
        log.warn("Leerer Ordner nicht entfernt: %s (%s)" % (pfad, ausnahme))
        return False
    return True

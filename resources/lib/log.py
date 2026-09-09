"""Logging ohne Kodi-Abhaengigkeit.

Kodi haengt sich in service.py per set_sink() ein. Ohne Sink geht alles
auf stderr, damit die Module auch im Test und auf der Kommandozeile laufen.
"""
import sys

DEBUG, INFO, WARN, ERROR = 0, 1, 2, 3

_NAMEN = {DEBUG: "DEBUG", INFO: "INFO", WARN: "WARN", ERROR: "ERROR"}
_sink = None


def set_sink(fn):
    """Setzt die Ausgabefunktion fn(level, msg) oder None fuer stderr."""
    global _sink
    _sink = fn


def _schreibe(level, msg):
    if _sink is not None:
        _sink(level, msg)
    else:
        sys.stderr.write("[mediasorter][%s] %s\n" % (_NAMEN[level], msg))


def debug(msg):
    _schreibe(DEBUG, msg)


def info(msg):
    _schreibe(INFO, msg)


def warn(msg):
    _schreibe(WARN, msg)


def error(msg):
    _schreibe(ERROR, msg)

import os
import sys
import types

import pytest

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def bestand():
    """Die echten Pfade aus dem Bestandsscan, relativ zum Watch-Root."""
    pfad = os.path.join(FIXTURES, "bestand.txt")
    with open(pfad, encoding="utf-8") as fh:
        return [z.strip() for z in fh if z.strip()]


@pytest.fixture
def kodi_stubs(monkeypatch):
    """Registriert Dummy-Kodi-Module, damit config/library importierbar sind."""
    namen = ["xbmc", "xbmcaddon", "xbmcgui", "xbmcvfs"]
    for name in namen:
        modul = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, modul)
    return {name: sys.modules[name] for name in namen}


@pytest.fixture(autouse=True)
def kein_netzwerk(monkeypatch, request):
    """Blockiert echte HTTP-Aufrufe in der gesamten Testsuite.

    Ohne das griffe in den durchlauf-Tests unbemerkt Stufe 4 und fragte TVmaze
    live. Die Tests waeren dann langsam, offline rot und wuerden nicht mehr
    pruefen, was sie pruefen sollen. Module, die einen eigenen Oeffner
    durchreichen, sind nicht betroffen.

    Mit der Marke @pytest.mark.netzwerk laesst sich die Sperre aufheben.
    """
    if request.node.get_closest_marker("netzwerk"):
        return

    import urllib.request

    def verboten(*a, **kw):
        raise OSError("Netzwerkzugriff im Test blockiert (siehe conftest.kein_netzwerk)")

    monkeypatch.setattr(urllib.request, "urlopen", verboten)

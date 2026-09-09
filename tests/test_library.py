import json

import pytest


@pytest.fixture
def lib(kodi_stubs):
    """Importiert library erst, nachdem die Kodi-Stubs stehen."""
    import importlib

    import library as modul
    importlib.reload(modul)
    return modul, kodi_stubs


def test_scan_sendet_verzeichnis(lib):
    modul, stubs = lib
    gesendet = []
    stubs["xbmc"].executeJSONRPC = lambda roh: gesendet.append(roh) or '{"result":"OK"}'

    modul.scanne("/media/MOVIES/Serien/Reacher/Season 04")

    anfrage = json.loads(gesendet[0])
    assert anfrage["method"] == "VideoLibrary.Scan"
    assert anfrage["params"]["directory"] == "/media/MOVIES/Serien/Reacher/Season 04"


def test_spielt_gerade_erkennt_laufende_datei(lib):
    modul, stubs = lib

    def antworte(roh):
        anfrage = json.loads(roh)
        if anfrage["method"] == "Player.GetActivePlayers":
            return json.dumps({"result": [{"playerid": 1}]})
        return json.dumps({"result": {"item": {"file": "/media/MOVIES/film.mkv"}}})

    stubs["xbmc"].executeJSONRPC = antworte

    assert modul.spielt_gerade("/media/MOVIES/film.mkv") is True
    assert modul.spielt_gerade("/media/MOVIES/anderer.mkv") is False


def test_spielt_gerade_ohne_player(lib):
    modul, stubs = lib
    stubs["xbmc"].executeJSONRPC = lambda roh: json.dumps({"result": []})
    assert modul.spielt_gerade("/media/MOVIES/film.mkv") is False


def test_kaputte_antwort_wirft_nicht(lib):
    modul, stubs = lib
    stubs["xbmc"].executeJSONRPC = lambda roh: "kein json"
    assert modul.spielt_gerade("/media/x.mkv") is False


def test_benachrichtigung(lib):
    modul, stubs = lib
    gerufen = []

    class Dialog:
        def notification(self, titel, text, symbol=None, dauer=None):
            gerufen.append((titel, text, dauer))

    stubs["xbmcgui"].Dialog = Dialog
    stubs["xbmcgui"].NOTIFICATION_INFO = "info"

    modul.benachrichtige("Media Sorter", "3 Dateien einsortiert")

    assert gerufen == [("Media Sorter", "3 Dateien einsortiert", 5000)]


def test_benachrichtigung_verschluckt_kodi_fehler(lib):
    modul, stubs = lib

    class Dialog:
        def notification(self, *a, **kw):
            raise RuntimeError("Kodi zickt")

    stubs["xbmcgui"].Dialog = Dialog
    stubs["xbmcgui"].NOTIFICATION_INFO = "info"

    modul.benachrichtige("Media Sorter", "Text")   # darf nicht werfen

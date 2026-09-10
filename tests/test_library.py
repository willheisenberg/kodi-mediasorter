import json

import pytest


@pytest.fixture
def lib(kodi_stubs):
    """Importiert library erst, nachdem die Kodi-Stubs stehen."""
    import importlib

    import library as modul
    importlib.reload(modul)
    return modul, kodi_stubs


def antworter(quellen, gesendet):
    """Fake fuer xbmc.executeJSONRPC: Quellen liefern, alles andere mitschreiben."""
    def antworte(roh):
        anfrage = json.loads(roh)
        gesendet.append(anfrage)
        if anfrage["method"] == "Files.GetSources":
            return json.dumps({"result": {"sources": [{"file": q, "label": q} for q in quellen]}})
        return '{"result":"OK"}'
    return antworte


def symlink_welt(tmp_path):
    """Nachbau der Box: /media ist ein Symlink auf /var/media."""
    echt = tmp_path / "var" / "media" / "MOVIES" / "Serien" / "Night Signal" / "Season 05"
    echt.mkdir(parents=True)
    (tmp_path / "media").symlink_to(tmp_path / "var" / "media")
    quelle = str(tmp_path / "media" / "MOVIES" / "Serien") + "/"
    return echt, quelle


def test_scan_uebersetzt_in_die_schreibweise_der_quelle(lib, tmp_path):
    """Echter Befund: Kodi ignoriert /var/media/..., wenn die Quelle /media/... heisst."""
    modul, stubs = lib
    echt, quelle = symlink_welt(tmp_path)
    gesendet = []
    stubs["xbmc"].executeJSONRPC = antworter([quelle], gesendet)

    assert modul.scanne(str(echt.parent)) is True

    scans = [a for a in gesendet if a["method"] == "VideoLibrary.Scan"]
    assert len(scans) == 1
    assert scans[0]["params"]["directory"] == quelle + "Night Signal/"


def test_scan_ohne_passende_quelle_wird_nicht_abgeschickt(lib, tmp_path):
    modul, stubs = lib
    echt, _ = symlink_welt(tmp_path)
    gesendet = []
    stubs["xbmc"].executeJSONRPC = antworter(["/storage/videos/"], gesendet)

    assert modul.scanne(str(echt.parent)) is False
    assert not [a for a in gesendet if a["method"] == "VideoLibrary.Scan"]


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


# --- Pfaduebersetzung ohne Kodi ---

def test_quellpfad_fuer_symlink(lib, tmp_path):
    modul, _ = lib
    echt, quelle = symlink_welt(tmp_path)
    assert modul.quellpfad_fuer(str(echt.parent), [quelle]) == quelle + "Night Signal/"


def test_quellpfad_fuer_quellwurzel_selbst(lib, tmp_path):
    modul, _ = lib
    echt, quelle = symlink_welt(tmp_path)
    wurzel = tmp_path / "var" / "media" / "MOVIES" / "Serien"
    assert modul.quellpfad_fuer(str(wurzel), [quelle]) == quelle


def test_quellpfad_fuer_verlangt_verzeichnisgrenze(lib, tmp_path):
    """Serien2 liegt nicht in der Quelle Serien, auch wenn der Text so beginnt."""
    modul, _ = lib
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Serien2" / "X").mkdir(parents=True)
    assert modul.quellpfad_fuer(str(tmp_path / "Serien2" / "X"),
                                [str(tmp_path / "Serien") + "/"]) is None


def test_quellpfad_fuer_laengste_quelle_gewinnt(lib, tmp_path):
    modul, _ = lib
    ziel = tmp_path / "MOVIES" / "Serien" / "X"
    ziel.mkdir(parents=True)
    quellen = [str(tmp_path / "MOVIES") + "/", str(tmp_path / "MOVIES" / "Serien") + "/"]
    assert modul.quellpfad_fuer(str(ziel), quellen) == quellen[1] + "X/"


def test_quellpfad_fuer_ignoriert_netzwerkquellen(lib, tmp_path):
    modul, _ = lib
    ziel = tmp_path / "X"
    ziel.mkdir()
    assert modul.quellpfad_fuer(str(ziel), ["smb://nas/share/", "nfs://nas/x/"]) is None

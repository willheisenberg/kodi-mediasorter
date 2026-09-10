import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))

import baum                       # noqa: E402
import config                     # noqa: E402
import durchlauf                  # noqa: E402


def mache_welt(tmp_path, bestand, dry_run=True):
    baum.baue(str(tmp_path), bestand)
    (tmp_path / "daten").mkdir(exist_ok=True)
    cfg = config.Config.aus_dict({
        "watch_path": str(tmp_path),
        "series_path": "Serien",
        "movies_path": "Movies",
        "ignore_list": "Musik,Training,youtubePlaylists,lost+found",
        "interval_seconds": 30,
        "stability_cycles": 1,
        "rar_quiet_seconds": 120,
        "dry_run": dry_run,
        "notify": False,
        "library_scan": False,
        "opensubtitles_api_key": "",
    })
    return cfg, durchlauf.Zustand(cfg, str(tmp_path / "daten"))


@pytest.fixture
def welt(tmp_path, bestand):
    return mache_welt(tmp_path, bestand)


def alle_dateien(wurzel):
    return sorted(
        os.path.join(w, n) for w, _o, ns in os.walk(str(wurzel)) for n in ns
    )


def test_konfiguration_des_nachgebauten_bestands_ist_gueltig(welt):
    cfg, _ = welt
    assert cfg.validiere() == []


def test_trockenlauf_veraendert_nichts(welt, tmp_path):
    cfg, zustand = welt
    vorher = alle_dateien(tmp_path)

    for _ in range(3):
        durchlauf.einmal(cfg, zustand)

    nachher = alle_dateien(tmp_path)
    assert set(vorher) - set(nachher) == set(), "im Trockenlauf darf nichts verschwinden"
    zusatz = set(nachher) - set(vorher)
    assert all(os.sep + "daten" + os.sep in p for p in zusatz), \
        "nur Zustandsdateien dürfen entstehen, gefunden: %s" % zusatz


def test_lose_episoden_landen_in_der_warteschlange(welt):
    cfg, zustand = welt
    for _ in range(3):
        zaehler = durchlauf.einmal(cfg, zustand)

    # example und deep.signal haben keinen Serienordner und keine NFO,
    # koennen also ohne Netzwerk nicht aufgeloest werden
    assert zaehler["wartend"] >= 1


def test_ignorierte_ordner_tauchen_nie_auf(welt, tmp_path):
    cfg, zustand = welt
    for _ in range(3):
        durchlauf.einmal(cfg, zustand)

    for name in ("Musik", "Training", "youtubePlaylists", "lost+found"):
        assert (tmp_path / name).exists()


def test_kein_takt_wirft(welt):
    """Kein Eintrag aus dem echten Bestand darf einen Takt abbrechen."""
    cfg, zustand = welt
    for _ in range(5):
        durchlauf.einmal(cfg, zustand)      # darf keine Ausnahme werfen


def test_scharfer_lauf_sortiert_bekannte_serien_ein(tmp_path, bestand):
    """Mit dry_run=False: ranger und palace.of.the.sun sind aufloesbar, weil
    ihre Ordner im Bestand existieren. Die losen example-Folgen nicht.
    """
    cfg, zustand = mache_welt(tmp_path, bestand, dry_run=False)

    # zwei lose Folgen bekannter Serien dazulegen
    (tmp_path / "ranger.s04e08.german.dl.1080p.web.h264-crew.mkv").write_bytes(b"")
    (tmp_path / "palace.of.the.sun.s03e09.german.dl.1080p.web.h264-crew.mkv").write_bytes(b"")

    for _ in range(3):
        durchlauf.einmal(cfg, zustand)

    assert (tmp_path / "Serien" / "Ranger" / "Season 04"
            / "ranger.s04e08.german.dl.1080p.web.h264-crew.mkv").exists()
    assert (tmp_path / "Serien" / "Palace of the Sun" / "Season 03"
            / "palace.of.the.sun.s03e09.german.dl.1080p.web.h264-crew.mkv").exists()
    # die unbekannten bleiben liegen
    assert (tmp_path / "example.s01e01.german.dl.1080p.web.h264-group.mkv").exists()


def test_audiotests_wird_nie_als_film_einsortiert(tmp_path, bestand):
    """AudioTests liegt schon in Movies und darf nicht angefasst werden."""
    cfg, zustand = mache_welt(tmp_path, bestand, dry_run=False)

    for _ in range(3):
        durchlauf.einmal(cfg, zustand)

    assert (tmp_path / "Movies" / "AudioTests").is_dir()
    assert not (tmp_path / "Movies" / "Movies").exists()

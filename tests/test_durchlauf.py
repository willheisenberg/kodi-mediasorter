import os

import config
import durchlauf
import mover
import pytest


def test_filmordner_prueft_alle_dateien_im_selben_takt(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Blow.2001"
    ordner.mkdir()
    for name in ("film.mkv", "film.nfo", "folder.jpg", "sample.mkv"):
        (ordner / name).write_bytes(b"fertig")
    assert durchlauf.einmal(cfg, zustand)["verschoben"] == 0
    assert durchlauf.einmal(cfg, zustand)["verschoben"] == 1
    assert len(list((tmp_path / "Movies" / ordner.name).iterdir())) == 4


def test_filmordner_behaelt_alle_beigaben(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Blow.2001"
    dateien = {"film.mkv": b"video", "folder.jpg": b"bild", "release.nfo": b"nfo",
               "Sample/sample.mkv": b"sample", "Subs/de.srt": b"untertitel"}
    for name, daten in dateien.items():
        pfad = ordner / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(daten)
    stabil_machen(cfg, zustand, takte=12)
    assert not ordner.exists()
    for name, daten in dateien.items():
        assert (tmp_path / "Movies" / ordner.name / name).read_bytes() == daten


def test_loser_film_wartet_auf_wachsende_begleitdatei(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    video = tmp_path / "Blow.2001.mkv"
    nfo = tmp_path / "Blow.2001.nfo"
    video.write_bytes(b"video")
    nfo.write_bytes(b"nfo")
    for i in range(5):
        nfo.write_bytes(b"nfo" * (i + 1))
        durchlauf.einmal(cfg, zustand)
        assert video.exists()
        assert nfo.exists()
    stabil_machen(cfg, zustand, takte=5)
    ziel = tmp_path / "Movies" / "Blow.2001"
    assert (ziel / video.name).read_bytes() == b"video"
    assert (ziel / nfo.name).read_bytes() == b"nfo" * 5


def test_temporaere_begleitdatei_blockiert_film(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Blow.2001.mkv").write_bytes(b"video")
    nfo = tmp_path / "Blow.2001.nfo.part"
    nfo.write_bytes(b"nfo")
    stabil_machen(cfg, zustand, takte=6)
    assert (tmp_path / "Blow.2001.mkv").exists()
    nfo.rename(tmp_path / "Blow.2001.nfo")
    stabil_machen(cfg, zustand, takte=5)
    assert (tmp_path / "Movies" / "Blow.2001" / "Blow.2001.nfo").exists()


@pytest.mark.parametrize("konflikt", ["Blow.2001.mkv", "Blow.2001.nfo"])
def test_kollision_verschiebt_keinen_teil_des_films(tmp_path, konflikt):
    cfg, zustand = baue_umgebung(tmp_path)
    for name in ("Blow.2001.mkv", "Blow.2001.nfo"):
        (tmp_path / name).write_bytes(b"neu")
    ziel = tmp_path / "Movies" / "Blow.2001"
    ziel.mkdir()
    (ziel / konflikt).write_bytes(b"alt")
    stabil_machen(cfg, zustand, takte=5)
    assert (tmp_path / "Blow.2001.mkv").read_bytes() == b"neu"
    assert (tmp_path / "Blow.2001.nfo").read_bytes() == b"neu"
    assert (ziel / konflikt).read_bytes() == b"alt"
    assert len(list(ziel.iterdir())) == 1
    assert zustand.warteschlange.anzahl() == 1


def test_begleiterfehler_bleibt_wiederholbar(tmp_path, monkeypatch):
    cfg, zustand = baue_umgebung(tmp_path)
    for name in ("Blow.2001.mkv", "Blow.2001.jpg", "Blow.2001.nfo"):
        (tmp_path / name).write_bytes(b"daten")
    original = mover.verschiebe

    def mit_fehler(schritt, *args):
        if schritt.quelle.endswith(".nfo"):
            return mover.FEHLER
        return original(schritt, *args)

    monkeypatch.setattr(mover, "verschiebe", mit_fehler)
    stabil_machen(cfg, zustand, takte=6)
    assert (tmp_path / "Blow.2001.mkv").exists()
    assert (tmp_path / "Blow.2001.nfo").exists()
    monkeypatch.setattr(mover, "verschiebe", original)
    stabil_machen(cfg, zustand, takte=5)
    ziel = tmp_path / "Movies" / "Blow.2001"
    assert {p.name for p in ziel.iterdir()} == {"Blow.2001.mkv", "Blow.2001.jpg", "Blow.2001.nfo"}
    assert zustand.warteschlange.anzahl() == 0


def baue_umgebung(tmp_path, dry_run=False):
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Movies").mkdir()
    (tmp_path / "daten").mkdir()
    cfg = config.Config.aus_dict({
        "watch_path": str(tmp_path),
        "series_path": "Serien",
        "movies_path": "Movies",
        "ignore_list": "Musik",
        "interval_seconds": 30,
        "stability_cycles": 1,
        "rar_quiet_seconds": 120,
        "dry_run": dry_run,
        "notify": False,
        "library_scan": False,
        "opensubtitles_api_key": "",
    })
    zustand = durchlauf.Zustand(cfg, datenordner=str(tmp_path / "daten"))
    return cfg, zustand


def stabil_machen(cfg, zustand, takte=3, **kw):
    """Mehrere Takte ohne Aenderung, damit Lage 4 die Dateien freigibt."""
    ergebnis = None
    for _ in range(takte):
        ergebnis = durchlauf.einmal(cfg, zustand, **kw)
    return ergebnis


def test_episode_landet_im_season_ordner(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.german.dl.1080p.web.h264-crew.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    ziel = tmp_path / "Serien" / "Ranger" / "Season 04" / quelle.name
    assert ziel.exists()
    assert not quelle.exists()


def test_filmordner_landet_unter_movies(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "film.mkv").write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert (tmp_path / "Movies" / ordner.name / "film.mkv").exists()


def test_unbekannte_serie_geht_in_die_warteschlange(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    quelle = tmp_path / "xyz.s01e01.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert quelle.exists(), "darf nicht verschoben werden"
    assert zustand.warteschlange.anzahl() == 1


def test_wiedervorlage_loest_sich_selbst_auf(tmp_path):
    """Der nbs-Fall: erst unloesbar, dann entsteht der Ordner."""
    cfg, zustand = baue_umgebung(tmp_path)
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)
    assert zustand.warteschlange.anzahl() == 1

    (tmp_path / "Serien" / "Ranger").mkdir()      # Ordner taucht spaeter auf
    stabil_machen(cfg, zustand)

    assert (tmp_path / "Serien" / "Ranger" / "Season 04" / quelle.name).exists()
    assert zustand.warteschlange.anzahl() == 0


def test_unfertige_datei_wird_nicht_angefasst(tmp_path):
    """MKV mit Sollgroesse 5000, aber nur 100 Bytes geschrieben."""
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()

    from test_readiness_groesse import baue_mkv
    pfad, _ = baue_mkv(tmp_path, nutzlast=5000, geschrieben=100)
    ziel_name = tmp_path / "ranger.s04e08.mkv"
    os.rename(pfad, ziel_name)

    stabil_machen(cfg, zustand)

    assert ziel_name.exists(), "halb geschriebene Datei muss liegen bleiben"
    assert not (tmp_path / "Serien" / "Ranger" / "Season 04").exists()


def test_rar_im_ordner_blockiert_den_durchlauf(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "film.mkv").write_bytes(b"x" * 100)
    (ordner / "release.rar").write_bytes(b"x")

    stabil_machen(cfg, zustand)

    assert ordner.exists(), "solange RAR daneben liegt, wird nicht verschoben"


def test_kollision_ueberschreibt_nicht(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    season = tmp_path / "Serien" / "Ranger" / "Season 04"
    season.mkdir(parents=True)
    (season / "ranger.s04e08.mkv").write_bytes(b"alt")
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"neu")

    stabil_machen(cfg, zustand)

    assert (season / "ranger.s04e08.mkv").read_bytes() == b"alt"
    assert quelle.read_bytes() == b"neu"
    assert zustand.warteschlange.anzahl() == 1


def test_dry_run_verschiebt_nichts(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path, dry_run=True)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert quelle.exists()
    assert not (tmp_path / "Serien" / "Ranger" / "Season 04").exists()


def test_ignorierte_ordner_bleiben_unberuehrt(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    musik = tmp_path / "Musik"
    musik.mkdir()
    (musik / "lied.mkv").write_bytes(b"x")

    stabil_machen(cfg, zustand)

    assert (musik / "lied.mkv").exists()


def test_laufende_wiedergabe_blockiert(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand, spielt_gerade=lambda pfad: pfad == str(quelle))

    assert quelle.exists(), "was gerade laeuft, wird nicht verschoben"


def test_staffelpaket_wird_aufgebrochen(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    paket = tmp_path / "Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP"
    paket.mkdir()
    for nr in (1, 2):
        (paket / ("ranger.s04e0%d.mkv" % nr)).write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    season = tmp_path / "Serien" / "Ranger" / "Season 04"
    assert (season / "ranger.s04e01.mkv").exists()
    assert (season / "ranger.s04e02.mkv").exists()
    assert not paket.exists(), "leerer Paketordner wird entfernt"


def test_stufe_drei_wird_nicht_gecacht(tmp_path):
    """Nur teure Netzwerk-Treffer landen im Cache.

    Stufe 3 liest lokale Ordner und kostet nichts. Wuerde man sie cachen,
    zeigte der Cache nach einem Umbenennen des Serienordners ins Leere und das
    Addon legte den alten Namen neu an.
    """
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert (tmp_path / "Serien" / "Ranger" / "Season 04" / quelle.name).exists()
    assert zustand.cache.hole("ranger") is None


def test_stufe_vier_greift_und_wird_gecacht(tmp_path, monkeypatch):
    """Neue Serie ohne Ordner: TVmaze liefert den Namen, der Cache merkt ihn.

    Der Netzwerkaufruf ist ersetzt, damit der Test offline laeuft.
    """
    import resolver

    aufrufe = []

    def gefaelscht(titel, oeffner=None):
        aufrufe.append(titel)
        return "Example" if titel == "example" else None

    monkeypatch.setattr(resolver, "tvmaze_per_name", gefaelscht)

    cfg, zustand = baue_umgebung(tmp_path)
    quelle = tmp_path / "example.s01e01.german.dl.1080p.web.h264-group.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert (tmp_path / "Serien" / "Example" / "Season 01" / quelle.name).exists()
    assert zustand.cache.hole("example") == "Example"
    assert aufrufe == ["example"], "genau ein Lookup, danach greift der Cache"


def test_stufe_eins_nutzt_imdb_id_aus_nfo(tmp_path, monkeypatch):
    """Ordner mit NFO: die IMDb-ID entscheidet, nicht der Name."""
    import resolver

    monkeypatch.setattr(
        resolver, "tvmaze_per_imdb",
        lambda tt, oeffner=None: "Nebula Station" if tt == "tt1234567" else None,
    )
    monkeypatch.setattr(resolver, "tvmaze_per_name", lambda t, oeffner=None: None)

    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Nebula.Station.S01E06.Das.Tribunal.German.720p.BluRay.x264-NSG"
    ordner.mkdir()
    (ordner / "nsg-nbs-s01e06-720p.mkv").write_bytes(b"x" * 100)
    (ordner / "nsg-nbs-s01e06-720p.nfo").write_text(
        "Imdb : http://www.imdb.com/title/tt1234567/", encoding="utf-8"
    )

    stabil_machen(cfg, zustand)

    ziel = tmp_path / "Serien" / "Nebula Station" / "Season 01" / ordner.name
    assert ziel.exists(), "der ganze Release-Ordner wandert"
    assert (ziel / "nsg-nbs-s01e06-720p.mkv").exists()


def test_kurzschema_mit_zusammengeschriebenem_titel(tmp_path, monkeypatch):
    """4gr-nightsignal-1080p-s05e01: Kuerzel weg, Titel zusammengeschrieben."""
    import resolver

    monkeypatch.setattr(resolver, "tvmaze_per_name", lambda t, oeffner=None: None)
    monkeypatch.setattr(
        resolver, "tvmaze_zusammengeschrieben",
        lambda t, oeffner=None: "Night Signal" if t == "nightsignal" else None,
    )
    cfg, zustand = baue_umgebung(tmp_path)
    for nr in (1, 2):
        (tmp_path / ("4gr-nightsignal-1080p-s05e0%d.mkv" % nr)).write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    season = tmp_path / "Serien" / "Night Signal" / "Season 05"
    assert (season / "4gr-nightsignal-1080p-s05e01.mkv").exists()
    assert (season / "4gr-nightsignal-1080p-s05e02.mkv").exists()
    assert zustand.cache.hole("4gr nightsignal") == "Night Signal"
    assert zustand.warteschlange.anzahl() == 0


def test_fehlgeschlagener_onlinelookup_ruht(tmp_path, monkeypatch):
    """Zwei wartende Folgen, sechs Takte: TVmaze wird genau einmal gefragt."""
    import resolver

    aufrufe = []
    monkeypatch.setattr(resolver, "tvmaze_per_name",
                        lambda t, oeffner=None: aufrufe.append(t))
    monkeypatch.setattr(resolver, "tvmaze_zusammengeschrieben",
                        lambda t, oeffner=None: None)
    cfg, zustand = baue_umgebung(tmp_path)
    for nr in (1, 2):
        (tmp_path / ("xyz.s01e0%d.mkv" % nr)).write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand, takte=6)

    assert zustand.warteschlange.anzahl() == 2
    assert aufrufe == ["xyz"]


def test_sperre_laeuft_nach_sechs_stunden_ab(tmp_path, monkeypatch):
    import resolver

    aufrufe = []
    monkeypatch.setattr(resolver, "tvmaze_per_name",
                        lambda t, oeffner=None: aufrufe.append(t))
    monkeypatch.setattr(resolver, "tvmaze_zusammengeschrieben",
                        lambda t, oeffner=None: None)
    cfg, zustand = baue_umgebung(tmp_path)
    uhr = [1000.0]
    zustand.uhr = lambda: uhr[0]
    (tmp_path / "xyz.s01e01.mkv").write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand, takte=4)
    assert aufrufe == ["xyz"]

    uhr[0] += durchlauf.SPERRE_SEKUNDEN + 1
    durchlauf.einmal(cfg, zustand)
    assert aufrufe == ["xyz", "xyz"]


# --- Scanziel: Serienordner bzw. Filmordner, nicht Season-Ordner oder Quelle ---

def test_scanziel_bei_episoden_ist_der_serienordner(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    for nr in (1, 2):
        (tmp_path / ("ranger.s04e0%d.mkv" % nr)).write_bytes(b"x" * 100)

    zaehler = stabil_machen(cfg, zustand, takte=1)
    zaehler = durchlauf.einmal(cfg, zustand)

    assert zaehler["zielpfade"] == {str(tmp_path / "Serien" / "Ranger")}, \
        "zwei Folgen, ein Scan auf Serienebene"


def test_scanziel_bei_filmordner_ist_der_filmordner(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "film.mkv").write_bytes(b"x" * 100)

    alle = set()
    for _ in range(3):
        alle |= durchlauf.einmal(cfg, zustand)["zielpfade"]

    assert alle == {str(tmp_path / "Movies" / ordner.name)}, \
        "nicht die ganze Movies-Quelle"


def test_scanziel_bei_film_als_einzeldatei_ist_der_neue_ordner(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    datei = tmp_path / "Example.Movie.2025.GERMAN.DL.1080p.WEB.H264-MGX.mkv"
    datei.write_bytes(b"x" * 100)

    alle = set()
    for _ in range(3):
        alle |= durchlauf.einmal(cfg, zustand)["zielpfade"]

    assert alle == {str(tmp_path / "Movies" / "Example.Movie.2025.GERMAN.DL.1080p.WEB.H264-MGX")}

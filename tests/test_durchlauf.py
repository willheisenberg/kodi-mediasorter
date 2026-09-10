import os

import config
import durchlauf


def baue_umgxbung(tmp_path, dry_run=False):
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
    cfg, zustand = baue_umgxbung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.german.dl.1080p.web.h264-crew.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    ziel = tmp_path / "Serien" / "Ranger" / "Season 04" / quelle.name
    assert ziel.exists()
    assert not quelle.exists()


def test_filmordner_landet_unter_movies(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "film.mkv").write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert (tmp_path / "Movies" / ordner.name / "film.mkv").exists()


def test_unbekannte_serie_geht_in_die_warteschlange(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
    quelle = tmp_path / "xyz.s01e01.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert quelle.exists(), "darf nicht verschoben werden"
    assert zustand.warteschlange.anzahl() == 1


def test_wiedervorlage_loest_sich_selbst_auf(tmp_path):
    """Der nbs-Fall: erst unloesbar, dann entsteht der Ordner."""
    cfg, zustand = baue_umgxbung(tmp_path)
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
    cfg, zustand = baue_umgxbung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()

    from test_readiness_groesse import baue_mkv
    pfad, _ = baue_mkv(tmp_path, nutzlast=5000, geschrieben=100)
    ziel_name = tmp_path / "ranger.s04e08.mkv"
    os.rename(pfad, ziel_name)

    stabil_machen(cfg, zustand)

    assert ziel_name.exists(), "halb geschriebene Datei muss liegen bleiben"
    assert not (tmp_path / "Serien" / "Ranger" / "Season 04").exists()


def test_rar_im_ordner_blockiert_den_durchlauf(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "film.mkv").write_bytes(b"x" * 100)
    (ordner / "release.rar").write_bytes(b"x")

    stabil_machen(cfg, zustand)

    assert ordner.exists(), "solange RAR daneben liegt, wird nicht verschoben"


def test_kollision_ueberschreibt_nicht(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
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
    cfg, zustand = baue_umgxbung(tmp_path, dry_run=True)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand)

    assert quelle.exists()
    assert not (tmp_path / "Serien" / "Ranger" / "Season 04").exists()


def test_ignorierte_ordner_bleiben_unberuehrt(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
    musik = tmp_path / "Musik"
    musik.mkdir()
    (musik / "lied.mkv").write_bytes(b"x")

    stabil_machen(cfg, zustand)

    assert (musik / "lied.mkv").exists()


def test_laufende_wiedergabe_blockiert(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
    (tmp_path / "Serien" / "Ranger").mkdir()
    quelle = tmp_path / "ranger.s04e08.mkv"
    quelle.write_bytes(b"x" * 100)

    stabil_machen(cfg, zustand, spielt_gerade=lambda pfad: pfad == str(quelle))

    assert quelle.exists(), "was gerade laeuft, wird nicht verschoben"


def test_staffelpaket_wird_aufgebrochen(tmp_path):
    cfg, zustand = baue_umgxbung(tmp_path)
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
    cfg, zustand = baue_umgxbung(tmp_path)
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

    cfg, zustand = baue_umgxbung(tmp_path)
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

    cfg, zustand = baue_umgxbung(tmp_path)
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

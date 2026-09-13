import os

import planner
import pytest


def test_loser_film_nimmt_nur_eindeutige_begleiter_mit(tmp_path):
    for name in ("Blow.2001.mkv", "Blow.2001.nfo", "Blow.2001.de.srt",
                 "Blow.2001-poster.jpg", "Blow.20010.nfo", "folder.jpg",
                 "Anderer.Film.nfo", "Blow.2001.nfo.part"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "Blow.2001.png").mkdir()
    quelle = tmp_path / "Blow.2001.mkv"
    plan = planner.plane(
        {"pfad": str(quelle), "name": quelle.name, "ist_ordner": False},
        None, "/z/Serien", "/z/Movies",
    )
    assert {os.path.basename(s.quelle) for s in plan} == {
        "Blow.2001.mkv", "Blow.2001.nfo", "Blow.2001.de.srt", "Blow.2001-poster.jpg",
    }
    assert all(os.path.dirname(s.ziel) == "/z/Movies/Blow.2001" for s in plan)
    assert plan[-1].quelle == str(quelle)


@pytest.mark.parametrize("anderes_video", ["Film.Extended.mkv", "Film.mp4"])
def test_mehrdeutige_begleiter_bleiben_liegen(tmp_path, anderes_video):
    for name in ("Film.mkv", anderes_video, "Film.Extended.nfo"):
        (tmp_path / name).write_bytes(b"x")
    assert planner.film_begleiter(str(tmp_path / "Film.mkv")) == []
    assert planner.film_begleiter(str(tmp_path / anderes_video)) == []


def test_season_ordner_zweistellig():
    assert planner.season_ordner(4) == "Season 04"
    assert planner.season_ordner(0) == "Season 00"
    assert planner.season_ordner(12) == "Season 12"


def test_einzelne_episode_flach(tmp_path):
    quelle = tmp_path / "example.s01e01.german.dl.1080p.web.h264-group.mkv"
    quelle.write_bytes(b"x")
    kandidat = {"pfad": str(quelle), "name": quelle.name, "ist_ordner": False}

    plan = planner.plane(kandidat, "Example", "/z/Serien", "/z/Movies")

    assert len(plan) == 1
    assert plan[0].ziel == os.path.join("/z/Serien", "Example", "Season 01", quelle.name)


def test_ordner_mit_einer_episode_wandert_ganz(tmp_path):
    ordner = tmp_path / "Nebula.Station.S01E06.Das.Tribunal.German.720p.BluRay.x264-NSG"
    ordner.mkdir()
    (ordner / "nsg-nbs-s01e06-720p.mkv").write_bytes(b"x")
    kandidat = {"pfad": str(ordner), "name": ordner.name, "ist_ordner": True}

    plan = planner.plane(kandidat, "Nebula Station", "/z/Serien", "/z/Movies")

    assert len(plan) == 1
    assert plan[0].ziel == os.path.join(
        "/z/Serien", "Nebula Station", "Season 01", ordner.name
    )


def test_staffelpaket_wird_aufgebrochen(tmp_path):
    paket = tmp_path / "Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP"
    paket.mkdir()
    for nr in (1, 2, 3):
        (paket / ("ranger.s04e0%d.german.dl.1080p.web.h264-crew.mkv" % nr)).write_bytes(b"x")
    (paket / "release.nfo").write_bytes(b"x")
    kandidat = {"pfad": str(paket), "name": paket.name, "ist_ordner": True}

    plan = planner.plane(kandidat, "Ranger", "/z/Serien", "/z/Movies")

    assert len(plan) == 3, "nur die Videodateien, nicht die NFO"
    for eintrag in plan:
        assert os.path.dirname(eintrag.ziel).endswith("Season 04")


def test_staffelpaket_nimmt_untertitel_mit(tmp_path):
    paket = tmp_path / "Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP"
    paket.mkdir()
    (paket / "ranger.s04e01.mkv").write_bytes(b"x")
    (paket / "ranger.s04e01.srt").write_bytes(b"x")
    (paket / "ranger.s04e02.mkv").write_bytes(b"x")
    (paket / "werbung.url").write_bytes(b"x")
    kandidat = {"pfad": str(paket), "name": paket.name, "ist_ordner": True}

    plan = planner.plane(kandidat, "Ranger", "/z/Serien", "/z/Movies")
    namen = sorted(os.path.basename(e.quelle) for e in plan)

    assert namen == ["ranger.s04e01.mkv", "ranger.s04e01.srt", "ranger.s04e02.mkv"]


def test_filmordner_wandert_ganz(tmp_path):
    ordner = tmp_path / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX"
    ordner.mkdir()
    (ordner / "Neon.Harbor.1982.German.DL.1080p.BluRay.x264.mkv").write_bytes(b"x")
    kandidat = {"pfad": str(ordner), "name": ordner.name, "ist_ordner": True}

    plan = planner.plane(kandidat, None, "/z/Serien", "/z/Movies")

    assert len(plan) == 1
    assert plan[0].ziel == os.path.join("/z/Movies", ordner.name)


def test_film_als_einzeldatei_bekommt_ordner(tmp_path):
    quelle = tmp_path / "Example.Movie.2025.GERMAN.DL.1080p.WEB.H264-MGX.mkv"
    quelle.write_bytes(b"x")
    kandidat = {"pfad": str(quelle), "name": quelle.name, "ist_ordner": False}

    plan = planner.plane(kandidat, None, "/z/Serien", "/z/Movies")

    assert len(plan) == 1
    assert plan[0].ziel == os.path.join(
        "/z/Movies", "Example.Movie.2025.GERMAN.DL.1080p.WEB.H264-MGX", quelle.name
    )


def test_episode_ohne_titel_ist_nicht_planbar(tmp_path):
    quelle = tmp_path / "xyz.s01e01.mkv"
    quelle.write_bytes(b"x")
    kandidat = {"pfad": str(quelle), "name": quelle.name, "ist_ordner": False}

    assert planner.plane(kandidat, None, "/z/Serien", "/z/Movies") == []


def test_episoden_im_ordner_zaehlt_richtig(tmp_path):
    ordner = tmp_path / "paket"
    ordner.mkdir()
    (ordner / "serie.s01e01.mkv").write_bytes(b"x")
    (ordner / "serie.s01e02.mkv").write_bytes(b"x")
    (ordner / "serie.s01e02.srt").write_bytes(b"x")
    (ordner / "liesmich.nfo").write_bytes(b"x")

    gefunden = planner.episoden_im_ordner(str(ordner))

    assert sorted(gefunden.keys()) == [(1, 1), (1, 2)]


def test_sample_zaehlt_nicht_als_episode(tmp_path):
    """Ein Sample neben der Hauptdatei darf kein Staffelpaket vortaeuschen."""
    ordner = tmp_path / "Serie.S01E05.German.1080p.BluRay.x264-XYZ"
    ordner.mkdir()
    (ordner / "serie.s01e05.mkv").write_bytes(b"x")
    (ordner / "serie.s01e05.sample.mkv").write_bytes(b"x")
    kandidat = {"pfad": str(ordner), "name": ordner.name, "ist_ordner": True}

    plan = planner.plane(kandidat, "Serie", "/z/Serien", "/z/Movies")

    assert len(plan) == 1, "der ganze Ordner wandert, nicht aufgebrochen"
    assert plan[0].ziel.endswith(ordner.name)


def test_specials_landen_in_season_00(tmp_path):
    quelle = tmp_path / "Nebula.Station.S01E00.Pilot.Teil1.German.DL.BD.x264-TVS.mkv"
    quelle.write_bytes(b"x")
    kandidat = {"pfad": str(quelle), "name": quelle.name, "ist_ordner": False}

    plan = planner.plane(kandidat, "Nebula Station", "/z/Serien", "/z/Movies")

    # Im echten Bestand liegt genau diese Datei unter Season 00, nicht Season 01:
    # Episode 0 kennzeichnet ein Special und gewinnt ueber die Staffelnummer.
    assert os.path.dirname(plan[0].ziel).endswith("Season 00")

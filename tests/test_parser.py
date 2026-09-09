import pytest

import parser


def test_episode_aus_scene_namen():
    r = parser.parse("lanterns.s01e01.german.dl.1080p.web.h264-wvf.mkv")
    assert r["typ"] == "episode"
    assert r["titel"] == "lanterns"
    assert r["staffel"] == 1
    assert r["episode"] == 1


def test_episode_mit_mehrwortigem_titel():
    r = parser.parse("dark.matter.der.zeitenlaeufer.s02e01.german.dl.1080p.web.h264-wayne.mkv")
    assert r["typ"] == "episode"
    assert r["titel"] == "dark matter der zeitenlaeufer"
    assert r["staffel"] == 2
    assert r["episode"] == 1


def test_episode_grossgeschrieben_mit_folgentitel():
    r = parser.parse("Battlestar.Galactica.S01E06.Das.Tribunal.German.720p.BluRay.x264-RSG")
    assert r["typ"] == "episode"
    assert r["titel"] == "battlestar galactica"
    assert r["staffel"] == 1
    assert r["episode"] == 6


def test_episode_null_ist_special():
    r = parser.parse("Battlestar.Galactica.S01E00.Pilot.Teil1.German.DL.BD.x264-TVS")
    assert r["episode"] == 0


def test_kurzname_mit_bindestrichen():
    r = parser.parse("rsg-bsg-s01e06-720p.mkv")
    assert r["typ"] == "episode"
    assert r["staffel"] == 1
    assert r["episode"] == 6


def test_film_mit_jahr():
    r = parser.parse("Anora.2024.GERMAN.DL.1080P.WEB.H264-WAYNE")
    assert r["typ"] == "film"
    assert r["titel"] == "anora"
    assert r["jahr"] == 2024


def test_jahr_im_titel_wird_nicht_als_erscheinungsjahr_genommen():
    # 2049 gehoert zum Titel, 2017 ist das Erscheinungsjahr
    r = parser.parse("Blade.Runner.2049.2017.German.DL.1080p.BluRay.x265-BluRHD")
    assert r["titel"] == "blade runner 2049"
    assert r["jahr"] == 2017


def test_titel_der_mit_jahreszahl_beginnt():
    r = parser.parse("2001.Odyssee.im.Weltraum.1968.Remastered.German.DL.1080p.BluRay.x264-CONTRiBUTiON")
    assert r["titel"] == "2001 odyssee im weltraum"
    assert r["jahr"] == 1968


def test_film_ohne_jahr():
    r = parser.parse("Cloud.Atlas.German.DL.1080p.BluRay.x264-ETM")
    assert r["typ"] == "film"
    assert r["jahr"] is None
    assert r["titel"] == "cloud atlas"


def test_part_im_titel_ist_keine_temporaerdatei():
    # Regressionstest: Dune.Part.Two darf nicht als unfertig gelten
    r = parser.parse("Dune.Part.Two.2024.German.DL.1080p.BluRay.x264-DETAiLS")
    assert r["typ"] == "film"
    assert r["titel"] == "dune part two"
    assert r["jahr"] == 2024


def test_ist_video():
    assert parser.ist_video("a.mkv")
    assert parser.ist_video("A.MKV")
    assert not parser.ist_video("a.nfo")
    assert not parser.ist_video("a.mkv.part")


def test_basisname():
    assert parser.basisname("film.mkv") == "film"
    assert parser.basisname("film.german.dl.mkv") == "film.german.dl"


def test_sprechend_erkennt_release_ordner():
    assert parser.ist_sprechend("Blade.Runner.1982.German.DL.1080p.BluRay.x264-AVG")
    assert parser.ist_sprechend("Cloud.Atlas.German.DL.1080p.BluRay.x264-ETM")
    assert parser.ist_sprechend("lanterns.s01e01.german.dl.1080p.web.h264-wvf.mkv")


def test_sprechend_lehnt_nichtssagendes_ab():
    assert not parser.ist_sprechend("DolbyTests")
    assert not parser.ist_sprechend("Reservoir Dogs")
    assert not parser.ist_sprechend("bhd-blarun-x265.mkv")


def test_alle_bestandsnamen_ohne_absturz(bestand):
    """Kein Eintrag aus dem echten Bestand darf den Parser werfen lassen."""
    for eintrag in bestand:
        name = eintrag.rstrip("/").split("/")[-1]
        r = parser.parse(name)
        assert r["typ"] in ("episode", "film")


# Aus dem echten Bestand: Release-Ordner nennen mindestens drei Marker,
# Kurznamen der Release-Gruppen nur einen. Genau daran wird getrennt.
SPRECHEND = [
    "Cloud.Atlas.German.DL.1080p.BluRay.x264-ETM",
    "Berlin.Calling.German.1080p.BluRay.x264-MiGHTY",
    "Der.Ja.Sager.German.DL.1080p.BluRay.x264-DEFUSED",
    "Oben.German.DL.1080p.BluRay.x264-DEFUSED",
    "Mavericks.Lebe.deinen.Traum.German.DL.1080p.BluRay.x264.REPACK-EmpireHD",
    "Searching.for.Sugar.Man.German.Dubbed.DL.DOKU.1080p.BluRay.x264-DiETER",
]

STUMM = [
    "bhd-blarun-x265.mkv",
    "unfired-tdk-x265.mkv",
    "etm-cloudatlas-1080p.mkv",
    "dfd-oben-1080p.mkv",
    "mighty-bcalling-1080p.mkv",
    "empire-mavericks-1080p-rp.mkv",
    "dfd-der.ja.sager-1080p.mkv",
    "DolbyTests",
    "Reservoir Dogs",
]


@pytest.mark.parametrize("name", SPRECHEND)
def test_echte_release_ordner_sind_sprechend(name):
    assert parser.ist_sprechend(name)


@pytest.mark.parametrize("name", STUMM)
def test_echte_kurznamen_sind_nicht_sprechend(name):
    assert not parser.ist_sprechend(name)

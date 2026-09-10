import pytest

import parser


def test_episode_aus_scene_namen():
    r = parser.parse("example.s01e01.german.dl.1080p.web.h264-group.mkv")
    assert r["typ"] == "episode"
    assert r["titel"] == "example"
    assert r["staffel"] == 1
    assert r["episode"] == 1


def test_episode_mit_mehrwortigem_titel():
    r = parser.parse("deep.signal.die.rueckkehr.s02e01.german.dl.1080p.web.h264-crew.mkv")
    assert r["typ"] == "episode"
    assert r["titel"] == "deep signal die rueckkehr"
    assert r["staffel"] == 2
    assert r["episode"] == 1


def test_episode_grossgeschrieben_mit_folgentitel():
    r = parser.parse("Nebula.Station.S01E06.Das.Tribunal.German.720p.BluRay.x264-NSG")
    assert r["typ"] == "episode"
    assert r["titel"] == "nebula station"
    assert r["staffel"] == 1
    assert r["episode"] == 6


def test_episode_null_ist_special():
    r = parser.parse("Nebula.Station.S01E00.Pilot.Teil1.German.DL.BD.x264-TVS")
    assert r["episode"] == 0


def test_kurzname_mit_bindestrichen():
    r = parser.parse("nsg-nbs-s01e06-720p.mkv")
    assert r["typ"] == "episode"
    assert r["staffel"] == 1
    assert r["episode"] == 6


def test_film_mit_jahr():
    r = parser.parse("Solstice.2024.GERMAN.DL.1080P.WEB.H264-CREW")
    assert r["typ"] == "film"
    assert r["titel"] == "solstice"
    assert r["jahr"] == 2024


def test_jahr_im_titel_wird_nicht_als_erscheinungsjahr_genommen():
    # 2049 gehoert zum Titel, 2017 ist das Erscheinungsjahr
    r = parser.parse("Neon.Harbor.2049.2017.German.DL.1080p.BluRay.x265-BHX")
    assert r["titel"] == "neon harbor 2049"
    assert r["jahr"] == 2017


def test_titel_der_mit_jahreszahl_beginnt():
    r = parser.parse("1999.Reise.zum.Mond.1972.Remastered.German.DL.1080p.BluRay.x264-CTRB")
    assert r["titel"] == "1999 reise zum mond"
    assert r["jahr"] == 1972


def test_film_ohne_jahr():
    r = parser.parse("Silver.Coast.German.DL.1080p.BluRay.x264-STM")
    assert r["typ"] == "film"
    assert r["jahr"] is None
    assert r["titel"] == "silver coast"


def test_part_im_titel_ist_keine_temporaerdatei():
    # Regressionstest: Example.Part.Two darf nicht als unfertig gelten
    r = parser.parse("Example.Part.Two.2024.German.DL.1080p.BluRay.x264-DTLS")
    assert r["typ"] == "film"
    assert r["titel"] == "example part two"
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
    assert parser.ist_sprechend("Neon.Harbor.1982.German.DL.1080p.BluRay.x264-AVX")
    assert parser.ist_sprechend("Silver.Coast.German.DL.1080p.BluRay.x264-STM")
    assert parser.ist_sprechend("example.s01e01.german.dl.1080p.web.h264-group.mkv")


def test_sprechend_lehnt_nichtssagendes_ab():
    assert not parser.ist_sprechend("AudioTests")
    assert not parser.ist_sprechend("Handmade Folder")
    assert not parser.ist_sprechend("bhx-neohar-x265.mkv")


def test_alle_bestandsnamen_ohne_absturz(bestand):
    """Kein Eintrag aus dem echten Bestand darf den Parser werfen lassen."""
    for eintrag in bestand:
        name = eintrag.rstrip("/").split("/")[-1]
        r = parser.parse(name)
        assert r["typ"] in ("episode", "film")


# Aus dem echten Bestand: Release-Ordner nennen mindestens drei Marker,
# Kurznamen der Release-Gruppen nur einen. Genau daran wird getrennt.
SPRECHEND = [
    "Silver.Coast.German.DL.1080p.BluRay.x264-STM",
    "Night.Signal.German.1080p.BluRay.x264-MGTY",
    "Der.Gute.Rat.German.DL.1080p.BluRay.x264-DFSD",
    "Hoch.German.DL.1080p.BluRay.x264-DFSD",
    "Nordwand.Lebe.deinen.Traum.German.DL.1080p.BluRay.x264.REPACK-EmpHD",
    "Looking.for.the.Singer.German.Dubbed.DL.DOKU.1080p.BluRay.x264-DTR",
]

STUMM = [
    "bhx-neohar-x265.mkv",
    "unfx-tso-x265.mkv",
    "stm-silvercoast-1080p.mkv",
    "dfs-hoch-1080p.mkv",
    "mgty-nsignal-1080p.mkv",
    "emp-nordwand-1080p-rp.mkv",
    "dfs-der.gute.rat-1080p.mkv",
    "AudioTests",
    "Handmade Folder",
]


@pytest.mark.parametrize("name", SPRECHEND)
def test_echte_release_ordner_sind_sprechend(name):
    assert parser.ist_sprechend(name)


@pytest.mark.parametrize("name", STUMM)
def test_echte_kurznamen_sind_nicht_sprechend(name):
    assert not parser.ist_sprechend(name)

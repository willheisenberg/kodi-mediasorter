import resolver


BESTAND = [
    "Blade Runner 2049",
    "The Dark Knight",
    "Der Pate 3",
    "Cloud Atlas",
    "Dark Matter",
    "House of the Dragon",
    "Reacher",
    "Battlestar Galactica",
    "Interstellar",
]


def test_abkuerzung_wortanfangskette():
    assert resolver.passt_abkuerzung("blarun", "Blade Runner 2049")
    assert resolver.passt_abkuerzung("dar.ma", "Dark Matter")
    assert resolver.passt_abkuerzung("houdra", "House of the Dragon")
    assert resolver.passt_abkuerzung("inters", "Interstellar")


def test_abkuerzung_initialen():
    assert resolver.passt_abkuerzung("tdk", "The Dark Knight")


def test_silbenabkuerzung_wird_nicht_erkannt():
    """bsg ist eine Fan-Abkuerzung, keine Wortanfangskette. Dokumentiert die Grenze."""
    assert not resolver.passt_abkuerzung("bsg", "Battlestar Galactica")


def test_keine_falschzuordnung():
    assert not resolver.passt_abkuerzung("blarun", "Cloud Atlas")
    assert not resolver.passt_abkuerzung("tdk", "Reacher")


def test_exakter_treffer_schlaegt_abkuerzung():
    assert resolver.finde_bestehenden_ordner("reacher", BESTAND) == "Reacher"
    assert resolver.finde_bestehenden_ordner("REACHER", BESTAND) == "Reacher"


def test_abkuerzung_findet_ordner():
    assert resolver.finde_bestehenden_ordner("dar.ma", BESTAND) == "Dark Matter"
    assert resolver.finde_bestehenden_ordner("houdra", BESTAND) == "House of the Dragon"


def test_ohne_treffer_none():
    assert resolver.finde_bestehenden_ordner("bsg", BESTAND) is None
    assert resolver.finde_bestehenden_ordner("voellig neue serie", BESTAND) is None


def test_mehrdeutige_abkuerzung_liefert_none():
    doppelt = ["Dark Matter", "Dark Materials"]
    assert resolver.finde_bestehenden_ordner("dar.ma", doppelt) is None


def test_vorhandene_serien_liest_ordner(tmp_path):
    (tmp_path / "Reacher").mkdir()
    (tmp_path / "Dark Matter").mkdir()
    (tmp_path / "liesmich.txt").write_bytes(b"x")
    assert sorted(resolver.vorhandene_serien(str(tmp_path))) == ["Dark Matter", "Reacher"]


def test_cache_speichert_und_laedt(tmp_path):
    pfad = str(tmp_path / "cache.json")
    c = resolver.Cache(pfad)
    assert c.hole("bsg") is None
    c.setze("bsg", "Battlestar Galactica")
    c.speichere()

    c2 = resolver.Cache(pfad)
    assert c2.hole("bsg") == "Battlestar Galactica"


def test_cache_uebersteht_kaputte_datei(tmp_path):
    pfad = tmp_path / "cache.json"
    pfad.write_text("{kein json", encoding="utf-8")
    c = resolver.Cache(str(pfad))
    assert c.hole("irgendwas") is None      # darf nicht werfen


def test_titel_mit_jahr_matcht_ordner_ohne_jahr():
    """dark matter (2024) muss den Ordner Dark Matter finden."""
    assert resolver.finde_bestehenden_ordner("dark matter", BESTAND) == "Dark Matter"

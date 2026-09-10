import resolver


BESTAND = [
    "Neon Harbor 2049",
    "The Silent Order",
    "Der Lange Weg 3",
    "Silver Coast",
    "Deep Signal",
    "Palace of the Sun",
    "Ranger",
    "Nebula Station",
    "Wanderer",
]


def test_abkuerzung_wortanfangskette():
    assert resolver.passt_abkuerzung("neohar", "Neon Harbor 2049")
    assert resolver.passt_abkuerzung("dee.si", "Deep Signal")
    assert resolver.passt_abkuerzung("palsu", "Palace of the Sun")
    assert resolver.passt_abkuerzung("wande", "Wanderer")


def test_abkuerzung_initialen():
    assert resolver.passt_abkuerzung("tso", "The Silent Order")


def test_silbenabkuerzung_wird_nicht_erkannt():
    """nbs ist eine Fan-Abkuerzung, keine Wortanfangskette. Dokumentiert die Grenze."""
    assert not resolver.passt_abkuerzung("nbs", "Nebula Station")


def test_keine_falschzuordnung():
    assert not resolver.passt_abkuerzung("neohar", "Silver Coast")
    assert not resolver.passt_abkuerzung("tso", "Ranger")


def test_exakter_treffer_schlaegt_abkuerzung():
    assert resolver.finde_bestehenden_ordner("ranger", BESTAND) == "Ranger"
    assert resolver.finde_bestehenden_ordner("RANGER", BESTAND) == "Ranger"


def test_abkuerzung_findet_ordner():
    assert resolver.finde_bestehenden_ordner("dee.si", BESTAND) == "Deep Signal"
    assert resolver.finde_bestehenden_ordner("palsu", BESTAND) == "Palace of the Sun"


def test_ohne_treffer_none():
    assert resolver.finde_bestehenden_ordner("nbs", BESTAND) is None
    assert resolver.finde_bestehenden_ordner("voellig neue serie", BESTAND) is None


def test_mehrdeutige_abkuerzung_liefert_none():
    doppelt = ["Deep Signal", "Deep Signals"]
    assert resolver.finde_bestehenden_ordner("dee.si", doppelt) is None


def test_vorhandene_serien_liest_ordner(tmp_path):
    (tmp_path / "Ranger").mkdir()
    (tmp_path / "Deep Signal").mkdir()
    (tmp_path / "liesmich.txt").write_bytes(b"x")
    assert sorted(resolver.vorhandene_serien(str(tmp_path))) == ["Deep Signal", "Ranger"]


def test_cache_speichert_und_laedt(tmp_path):
    pfad = str(tmp_path / "cache.json")
    c = resolver.Cache(pfad)
    assert c.hole("nbs") is None
    c.setze("nbs", "Nebula Station")
    c.speichere()

    c2 = resolver.Cache(pfad)
    assert c2.hole("nbs") == "Nebula Station"


def test_cache_uebersteht_kaputte_datei(tmp_path):
    pfad = tmp_path / "cache.json"
    pfad.write_text("{kein json", encoding="utf-8")
    c = resolver.Cache(str(pfad))
    assert c.hole("irgendwas") is None      # darf nicht werfen


def test_titel_mit_jahr_matcht_ordner_ohne_jahr():
    """deep signal (2024) muss den Ordner Deep Signal finden."""
    assert resolver.finde_bestehenden_ordner("deep signal", BESTAND) == "Deep Signal"


def test_zusammengeschriebener_titel_findet_bestehenden_ordner():
    assert resolver.finde_bestehenden_ordner(
        "nightsignal", ["Night Signal", "Ranger"]
    ) == "Night Signal"

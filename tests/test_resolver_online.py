import io
import json
import struct
import urllib.error

import resolver


class FakeAntwort(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def oeffner_mit(nutzlast):
    def oeffnen(url, timeout=None):
        return FakeAntwort(json.dumps(nutzlast).encode("utf-8"))
    return oeffnen


def oeffner_404():
    def oeffnen(url, timeout=None):
        raise urllib.error.HTTPError("http://x", 404, "Not Found", {}, None)
    return oeffnen


# --- Stufe 1: NFO und IMDb ---

def test_imdb_id_aus_nfo(tmp_path):
    (tmp_path / "release.nfo").write_text(
        "Imdb : http://www.imdb.com/title/tt0407362/\n", encoding="utf-8"
    )
    assert resolver.imdb_id_aus_ordner(str(tmp_path)) == "tt0407362"


def test_imdb_id_aus_nfo_mit_laendercode(tmp_path):
    (tmp_path / "r.nfo").write_text(
        "URL : https://www.imdb.com/de/title/tt28607951\n", encoding="utf-8"
    )
    assert resolver.imdb_id_aus_ordner(str(tmp_path)) == "tt28607951"


def test_imdb_id_aus_cp437_nfo(tmp_path):
    """Scene-NFOs sind oft ASCII-Art in CP437 und muessen trotzdem lesbar sein."""
    inhalt = "██ Imdb: tt0407362 ▓▒".encode("cp437", errors="replace")
    (tmp_path / "art.nfo").write_bytes(inhalt)
    assert resolver.imdb_id_aus_ordner(str(tmp_path)) == "tt0407362"


def test_keine_nfo_keine_id(tmp_path):
    assert resolver.imdb_id_aus_ordner(str(tmp_path)) is None


def test_tvmaze_per_imdb_liefert_namen():
    oeffnen = oeffner_mit({"name": "Battlestar Galactica", "premiered": "2003-10-18"})
    assert resolver.tvmaze_per_imdb("tt0407362", oeffnen) == "Battlestar Galactica"


def test_tvmaze_per_imdb_404_bedeutet_kein_serientreffer():
    """Anoras IMDb-ID liefert 404, weil es ein Film ist."""
    assert resolver.tvmaze_per_imdb("tt28607951", oeffner_404()) is None


# --- Stufe 4: Namenssuche ---

def test_tvmaze_per_name_bei_klarem_vorsprung():
    treffer = [
        {"score": 1.60, "show": {"name": "House of the Dragon"}},
        {"score": 0.20, "show": {"name": "Enter the House of the Dragon"}},
    ]
    assert resolver.tvmaze_per_name("house of the dragon", oeffner_mit(treffer)) == "House of the Dragon"


def test_tvmaze_per_name_einziger_treffer_zaehlt():
    treffer = [{"score": 0.54, "show": {"name": "Dark Matter"}}]
    assert resolver.tvmaze_per_name(
        "dark matter der zeitenlaeufer", oeffner_mit(treffer)
    ) == "Dark Matter"


def test_tvmaze_per_name_lehnt_gleichstand_ab():
    """Battlestar Galactica 2003 und 1978 haben denselben Score."""
    treffer = [
        {"score": 1.18, "show": {"name": "Battlestar Galactica", "premiered": "2003-10-18"}},
        {"score": 1.18, "show": {"name": "Battlestar Galactica", "premiered": "1978-09-17"}},
    ]
    assert resolver.tvmaze_per_name("battlestar galactica", oeffner_mit(treffer)) is None


def test_tvmaze_per_name_ohne_treffer():
    assert resolver.tvmaze_per_name("gibtsnicht", oeffner_mit([])) is None


# --- Stufe 5: OpenSubtitles ---

def test_hash_ueber_bekannte_datei(tmp_path):
    """Groesse plus die ersten und letzten 64 KB, als 64-Bit-Summe."""
    p = tmp_path / "film.mkv"
    laenge = 65536 * 3
    p.write_bytes(b"\x00" * laenge)
    erwartet = "%016x" % laenge          # Nullinhalt addiert nichts
    assert resolver.opensubtitles_hash(str(p)) == erwartet


def test_hash_addiert_inhalt(tmp_path):
    p = tmp_path / "film.mkv"
    laenge = 65536 * 3
    daten = bytearray(b"\x00" * laenge)
    daten[0:8] = struct.pack("<q", 5)
    p.write_bytes(bytes(daten))
    assert resolver.opensubtitles_hash(str(p)) == "%016x" % (laenge + 5)


def test_hash_bei_zu_kleiner_datei(tmp_path):
    p = tmp_path / "winzig.mkv"
    p.write_bytes(b"\x00" * 1000)
    assert resolver.opensubtitles_hash(str(p)) is None


def test_opensubtitles_ohne_key_wird_uebersprungen():
    assert resolver.opensubtitles_per_hash("abc", "", oeffner_mit({})) is None


def test_opensubtitles_liefert_serie():
    antwort = {"data": [{"attributes": {"feature_details": {
        "title": "Dark Matter", "season_number": 2, "episode_number": 1,
        "feature_type": "Episode"}}}]}
    r = resolver.opensubtitles_per_hash("abc", "SCHLUESSEL", oeffner_mit(antwort))
    assert r["titel"] == "Dark Matter"
    assert r["staffel"] == 2
    assert r["episode"] == 1
    assert r["typ"] == "episode"


def test_tvmaze_akzeptiert_exakten_namen_trotz_geringen_vorsprungs():
    """Echter Fall: House of the Dragon 1.60 gegen die Doku Enter the... 1.33.

    Faktor 1.20 liegt unter der Untergrenze, aber der Suchbegriff trifft den
    Namen exakt. Frueher wurde das faelschlich abgelehnt.
    """
    treffer = [
        {"score": 1.60, "show": {"name": "House of the Dragon"}},
        {"score": 1.33, "show": {"name": "Enter the House of the Dragon"}},
    ]
    assert resolver.tvmaze_per_name(
        "house of the dragon", oeffner_mit(treffer)
    ) == "House of the Dragon"


def test_tvmaze_lehnt_namensgleichheit_auch_mit_vorsprung_ab():
    """Zwei Serien gleichen Namens sind nie per Score entscheidbar."""
    treffer = [
        {"score": 2.00, "show": {"name": "Dark Matter", "premiered": "2024-05-08"}},
        {"score": 0.10, "show": {"name": "Dark Matter", "premiered": "2015-06-12"}},
    ]
    assert resolver.tvmaze_per_name("dark matter", oeffner_mit(treffer)) is None


def test_tvmaze_nimmt_besten_bei_klarem_abstand_ohne_exakten_namen():
    treffer = [
        {"score": 0.89, "show": {"name": "Lanterns"}},
        {"score": 0.33, "show": {"name": "Patterns"}},
    ]
    assert resolver.tvmaze_per_name("lantern", oeffner_mit(treffer)) == "Lanterns"

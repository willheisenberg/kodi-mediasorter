import scanner
import pytest


@pytest.mark.parametrize("name", ["sample.mkv", "Film.2001-SAMPLE.mp4", "film_sample.avi"])
def test_lose_samples_werden_nicht_als_filme_einsortiert(tmp_path, name):
    (tmp_path / name).write_bytes(b"x")
    assert scanner.finde_kandidaten(str(tmp_path), set()) == []


def test_sample_im_filmordner_verhindert_nicht_dessen_mitnahme(tmp_path):
    ordner = tmp_path / "Film.2001"
    ordner.mkdir()
    (ordner / "sample.mkv").write_bytes(b"x")
    (ordner / "film.mkv").write_bytes(b"x")
    (tmp_path / "Resampled.2001.mkv").write_bytes(b"x")
    assert namen(scanner.finde_kandidaten(str(tmp_path), set())) == [
        "Film.2001", "Resampled.2001.mkv",
    ]


def baue_baum(tmp_path):
    (tmp_path / "Movies").mkdir()
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Musik").mkdir()
    (tmp_path / ".versteckt").mkdir()
    (tmp_path / "example.s01e01.german.dl.1080p.web.h264-group.mkv").write_bytes(b"x")
    (tmp_path / "film.mkv.part").write_bytes(b"x")
    (tmp_path / "notizen.txt").write_bytes(b"x")
    paket = tmp_path / "Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP"
    paket.mkdir()
    (paket / "ranger.s04e01.mkv").write_bytes(b"x")
    return tmp_path


def namen(kandidaten):
    return sorted(k["name"] for k in kandidaten)


def test_findet_lose_videodatei_und_ordner(tmp_path):
    baue_baum(tmp_path)
    gefunden = scanner.finde_kandidaten(str(tmp_path), {"Movies", "Serien", "Musik"})
    assert namen(gefunden) == [
        "Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP",
        "example.s01e01.german.dl.1080p.web.h264-group.mkv",
    ]


def test_ignorierte_ordner_werden_uebersprungen(tmp_path):
    baue_baum(tmp_path)
    gefunden = scanner.finde_kandidaten(str(tmp_path), {"Movies", "Serien", "Musik"})
    assert "Musik" not in namen(gefunden)
    assert "Movies" not in namen(gefunden)


def test_versteckte_eintraege_werden_uebersprungen(tmp_path):
    baue_baum(tmp_path)
    gefunden = scanner.finde_kandidaten(str(tmp_path), set())
    assert ".versteckt" not in namen(gefunden)


def test_temporaere_dateien_werden_uebersprungen(tmp_path):
    baue_baum(tmp_path)
    gefunden = scanner.finde_kandidaten(str(tmp_path), set())
    assert "film.mkv.part" not in namen(gefunden)


def test_nicht_video_dateien_werden_uebersprungen(tmp_path):
    baue_baum(tmp_path)
    gefunden = scanner.finde_kandidaten(str(tmp_path), set())
    assert "notizen.txt" not in namen(gefunden)


def test_ordner_markierung_stimmt(tmp_path):
    baue_baum(tmp_path)
    gefunden = {k["name"]: k["ist_ordner"] for k in scanner.finde_kandidaten(str(tmp_path), set())}
    assert gefunden["Ranger.S04.COMPLETE.German.DL.1080p.WEB.h264-GROUP"] is True
    assert gefunden["example.s01e01.german.dl.1080p.web.h264-group.mkv"] is False


def test_fehlender_ordner_liefert_leere_liste(tmp_path):
    assert scanner.finde_kandidaten(str(tmp_path / "gibtsnicht"), set()) == []


def test_ordner_ohne_video_ist_kein_kandidat(tmp_path):
    """Ein beliebiger Ordner darf nicht als Filmordner einsortiert werden.

    Aufgefallen im Trockenlauf: der Zustandsordner des Addons wurde als
    Kandidat gefuehrt und waere nach Movies gewandert.
    """
    (tmp_path / "Urlaubsbilder").mkdir()
    (tmp_path / "Urlaubsbilder" / "strand.jpg").write_bytes(b"x")
    (tmp_path / "daten").mkdir()
    (tmp_path / "daten" / "cache.json").write_text("{}", encoding="utf-8")

    gefunden = scanner.finde_kandidaten(str(tmp_path), set())

    assert gefunden == []


def test_ordner_mit_video_in_untertiefe_zaehlt(tmp_path):
    """Nebula-Muster: die Videodatei liegt eine Ebene tiefer."""
    ordner = tmp_path / "Serie.S01E06.German.720p.BluRay.x264-NSG"
    (ordner / "Subs").mkdir(parents=True)
    (ordner / "Subs" / "sub.idx").write_bytes(b"x")
    (ordner / "nsg-serie-s01e06.mkv").write_bytes(b"x")

    gefunden = scanner.finde_kandidaten(str(tmp_path), set())

    assert len(gefunden) == 1
    assert gefunden[0]["ist_ordner"] is True


def test_leerer_ordner_ist_kein_kandidat(tmp_path):
    (tmp_path / "leer").mkdir()
    assert scanner.finde_kandidaten(str(tmp_path), set()) == []

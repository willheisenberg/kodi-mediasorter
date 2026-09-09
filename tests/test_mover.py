import os

import mover
from planner import Verschiebung


def test_verschiebt_datei(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"inhalt")
    ziel = tmp_path / "Movies" / "Film" / "film.mkv"

    ergebnis = mover.verschiebe(Verschiebung(str(quelle), str(ziel), "Test"), dry_run=False)

    assert ergebnis == mover.ERFOLG
    assert ziel.read_bytes() == b"inhalt"
    assert not quelle.exists()


def test_legt_zielordner_an(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"x")
    ziel = tmp_path / "a" / "b" / "c" / "film.mkv"

    mover.verschiebe(Verschiebung(str(quelle), str(ziel), "Test"), dry_run=False)

    assert ziel.exists()


def test_dry_run_fasst_nichts_an(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"inhalt")
    ziel = tmp_path / "Movies" / "film.mkv"

    ergebnis = mover.verschiebe(Verschiebung(str(quelle), str(ziel), "Test"), dry_run=True)

    assert ergebnis == mover.TROCKEN
    assert quelle.exists()
    assert not ziel.exists()
    assert not (tmp_path / "Movies").exists(), "auch kein Ordner im Trockenlauf"


def test_kollision_ueberschreibt_nicht(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"neu")
    ziel = tmp_path / "Movies" / "film.mkv"
    ziel.parent.mkdir()
    ziel.write_bytes(b"alt")

    ergebnis = mover.verschiebe(Verschiebung(str(quelle), str(ziel), "Test"), dry_run=False)

    assert ergebnis == mover.KOLLISION
    assert ziel.read_bytes() == b"alt", "Zieldatei muss unberührt bleiben"
    assert quelle.read_bytes() == b"neu", "Quelle muss liegen bleiben"


def test_fehlende_quelle_meldet_fehler(tmp_path):
    v = Verschiebung(str(tmp_path / "gibtsnicht.mkv"), str(tmp_path / "z.mkv"), "Test")
    assert mover.verschiebe(v, dry_run=False) == mover.FEHLER


def test_protokoll_wird_geschrieben(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"x")
    ziel = tmp_path / "Movies" / "film.mkv"
    protokoll = tmp_path / "daten" / "moves.log"

    mover.verschiebe(
        Verschiebung(str(quelle), str(ziel), "Test"), dry_run=False, protokoll=str(protokoll)
    )

    inhalt = protokoll.read_text(encoding="utf-8")
    assert str(quelle) in inhalt
    assert str(ziel) in inhalt
    assert "ERFOLG" in inhalt


def test_protokoll_auch_im_trockenlauf(tmp_path):
    quelle = tmp_path / "film.mkv"
    quelle.write_bytes(b"x")
    protokoll = tmp_path / "daten" / "moves.log"

    mover.verschiebe(
        Verschiebung(str(quelle), str(tmp_path / "z" / "film.mkv"), "Test"),
        dry_run=True, protokoll=str(protokoll),
    )

    assert "TROCKEN" in protokoll.read_text(encoding="utf-8")


def test_protokoll_haengt_an_statt_zu_ueberschreiben(tmp_path):
    protokoll = tmp_path / "daten" / "moves.log"
    for nr in (1, 2):
        quelle = tmp_path / ("film%d.mkv" % nr)
        quelle.write_bytes(b"x")
        mover.verschiebe(
            Verschiebung(str(quelle), str(tmp_path / "z" / quelle.name), "Test"),
            dry_run=False, protokoll=str(protokoll),
        )
    assert len(protokoll.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_leerer_ordner_wird_entfernt(tmp_path):
    leer = tmp_path / "paket"
    leer.mkdir()
    assert mover.raeume_leeren_ordner(str(leer), dry_run=False) is True
    assert not leer.exists()


def test_ordner_mit_beiwerk_bleibt_stehen(tmp_path):
    rest = tmp_path / "paket"
    rest.mkdir()
    (rest / "release.nfo").write_bytes(b"x")

    assert mover.raeume_leeren_ordner(str(rest), dry_run=False) is False
    assert rest.exists(), "Beiwerk darf nie gelöscht werden"


def test_leerer_ordner_bleibt_im_trockenlauf(tmp_path):
    leer = tmp_path / "paket"
    leer.mkdir()
    assert mover.raeume_leeren_ordner(str(leer), dry_run=True) is True
    assert leer.exists(), "im Trockenlauf wird nichts entfernt"

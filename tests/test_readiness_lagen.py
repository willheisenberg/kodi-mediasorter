import os
import time

import readiness


# --- Lage 3: Endungsfilter ---

def test_temporaere_endungen_erkannt():
    assert readiness.ist_temporaer("film.mkv.part")
    assert readiness.ist_temporaer("film.mkv.jdtmp")
    assert readiness.ist_temporaer("film.mkv.!qB")      # Grossschreibung egal
    assert readiness.ist_temporaer("film.crdownload")


def test_part_im_titel_ist_nicht_temporaer():
    """Regressionstest: Example.Part.Two darf nie als unfertig gelten."""
    assert not readiness.ist_temporaer("Example.Part.Two.2024.German.DL.1080p.BluRay.x264-DTLS")
    assert not readiness.ist_temporaer("example.part.two.2024.german.dl.1080p.bluray.x264-dtls.mkv")


# --- Lage 2: RAR-Waechter ---

def test_rar_im_ordner_blockiert(tmp_path):
    (tmp_path / "release.rar").write_bytes(b"x")
    assert readiness.rar_aktiv(str(tmp_path), ruhe_sekunden=120) is True


def test_mehrteiliges_rar_blockiert(tmp_path):
    (tmp_path / "release.part01.rar").write_bytes(b"x")
    (tmp_path / "release.r00").write_bytes(b"x")
    assert readiness.rar_aktiv(str(tmp_path), ruhe_sekunden=120) is True


def test_altes_rar_blockiert_nicht_mehr(tmp_path):
    p = tmp_path / "release.rar"
    p.write_bytes(b"x")
    alt = time.time() - 9999
    os.utime(str(p), (alt, alt))
    assert readiness.rar_aktiv(str(tmp_path), ruhe_sekunden=120) is False


def test_ordner_ohne_rar(tmp_path):
    (tmp_path / "film.mkv").write_bytes(b"x")
    assert readiness.rar_aktiv(str(tmp_path), ruhe_sekunden=120) is False


# --- SFV ---

def test_sfv_vollstaendig(tmp_path):
    (tmp_path / "release.sfv").write_text("film.mkv 1a2b3c4d\n", encoding="utf-8")
    (tmp_path / "film.mkv").write_bytes(b"x")
    assert readiness.sfv_vollstaendig(str(tmp_path)) is True


def test_sfv_meldet_fehlende_datei(tmp_path):
    (tmp_path / "release.sfv").write_text(
        "; Kommentarzeile\nfilm.mkv 1a2b3c4d\nfehlt.mkv deadbeef\n", encoding="utf-8"
    )
    (tmp_path / "film.mkv").write_bytes(b"x")
    assert readiness.sfv_vollstaendig(str(tmp_path)) is False


def test_ohne_sfv_keine_aussage(tmp_path):
    assert readiness.sfv_vollstaendig(str(tmp_path)) is None


# --- Lage 4: Stabilitaetsfenster ---

def test_wachsende_datei_gilt_nie_als_stabil(tmp_path):
    p = tmp_path / "wachsend.mkv"
    p.write_bytes(b"x")
    stab = readiness.Stabilitaet(zyklen=2)

    assert stab.pruefe(str(p)) is False       # erster Takt, kein Vergleich
    p.write_bytes(b"xx")
    assert stab.pruefe(str(p)) is False       # gewachsen
    p.write_bytes(b"xxx")
    assert stab.pruefe(str(p)) is False


def test_ruhende_datei_wird_nach_n_takten_stabil(tmp_path):
    p = tmp_path / "fertig.mkv"
    p.write_bytes(b"x" * 100)
    stab = readiness.Stabilitaet(zyklen=2)

    assert stab.pruefe(str(p)) is False       # Takt 1: erstmals gesehen
    assert stab.pruefe(str(p)) is False       # Takt 2: 1x unveraendert
    assert stab.pruefe(str(p)) is True        # Takt 3: 2x unveraendert


def test_aenderung_setzt_zaehler_zurueck(tmp_path):
    p = tmp_path / "ruckelig.mkv"
    p.write_bytes(b"x" * 100)
    stab = readiness.Stabilitaet(zyklen=2)

    stab.pruefe(str(p))
    stab.pruefe(str(p))
    p.write_bytes(b"x" * 200)                 # Nachzuegler, etwa naechster RAR-Teil
    assert stab.pruefe(str(p)) is False
    assert stab.pruefe(str(p)) is False
    assert stab.pruefe(str(p)) is True


def test_vergiss_entfernt_zustand(tmp_path):
    p = tmp_path / "weg.mkv"
    p.write_bytes(b"x")
    stab = readiness.Stabilitaet(zyklen=1)
    stab.pruefe(str(p))
    stab.vergiss(str(p))
    assert stab.pruefe(str(p)) is False       # wieder wie beim ersten Mal

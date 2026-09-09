import struct

import pytest

import readiness


def _vint_laenge(wert):
    """Kodiert wert als EBML-Datenlaenge mit moeglichst wenigen Bytes."""
    for n in range(1, 9):
        grenze = (1 << (7 * n)) - 1
        if wert < grenze:
            roh = wert | (1 << (7 * n))
            return roh.to_bytes(n, "big")
    raise ValueError("zu gross")


def baue_mkv(tmp_path, nutzlast=1000, geschrieben=None, unknown=False):
    """Erzeugt eine MKV mit korrektem Header und wahlweise gekuerztem Inhalt."""
    ebml_daten = b"\x42\x86\x81\x01"           # EBMLVersion = 1
    kopf = b"\x1a\x45\xdf\xa3" + _vint_laenge(len(ebml_daten)) + ebml_daten

    if unknown:
        laenge = b"\x01" + b"\xff" * 7          # 8-Byte-VINT, alle Nutzbits 1
    else:
        laenge = _vint_laenge(nutzlast)
    segment_kopf = b"\x18\x53\x80\x67" + laenge

    voll = kopf + segment_kopf + b"\x00" * nutzlast
    if geschrieben is not None:
        voll = voll[:geschrieben]

    pfad = tmp_path / "test.mkv"
    pfad.write_bytes(voll)
    return str(pfad), len(kopf) + len(segment_kopf) + nutzlast


def test_sollgroesse_stimmt_bytegenau(tmp_path):
    pfad, gesamt = baue_mkv(tmp_path, nutzlast=5000)
    assert readiness.erwartete_groesse(pfad) == gesamt


def test_vollstaendige_datei_gilt_als_fertig(tmp_path):
    pfad, _ = baue_mkv(tmp_path, nutzlast=5000)
    assert readiness.ist_vollstaendig(pfad) is True


@pytest.mark.parametrize("anteil", [0.004, 0.011, 0.019, 0.5, 0.999])
def test_gekuerzte_datei_gilt_als_unfertig(tmp_path, anteil):
    """Entspricht dem realen Fall: 48 MB von 2,7 GB waehrend des Entpackens."""
    pfad, gesamt = baue_mkv(tmp_path, nutzlast=100000)
    teil = int(gesamt * anteil)
    pfad2 = tmp_path / "teil.mkv"
    pfad2.write_bytes(open(pfad, "rb").read()[:teil])
    assert readiness.ist_vollstaendig(str(pfad2)) is False


def test_unknown_size_liefert_keine_aussage(tmp_path):
    pfad, _ = baue_mkv(tmp_path, nutzlast=5000, unknown=True)
    assert readiness.erwartete_groesse(pfad) is None
    assert readiness.ist_vollstaendig(pfad) is None


def test_avi_ueber_riff_header(tmp_path):
    nutzlast = b"AVI " + b"\x00" * 2000
    daten = b"RIFF" + struct.pack("<I", len(nutzlast)) + nutzlast
    pfad = tmp_path / "film.avi"
    pfad.write_bytes(daten)
    assert readiness.erwartete_groesse(str(pfad)) == 8 + len(nutzlast)
    assert readiness.ist_vollstaendig(str(pfad)) is True


def test_mp4_liefert_keine_aussage(tmp_path):
    pfad = tmp_path / "film.mp4"
    pfad.write_bytes(b"\x00" * 64)
    assert readiness.erwartete_groesse(str(pfad)) is None


def test_kaputter_header_wirft_nicht(tmp_path):
    pfad = tmp_path / "kaputt.mkv"
    pfad.write_bytes(b"\x00" * 8)
    assert readiness.erwartete_groesse(str(pfad)) is None

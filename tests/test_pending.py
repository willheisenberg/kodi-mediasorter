import pending


def test_kollidiert_nicht_mit_der_standardbibliothek():
    """pending.py darf das stdlib-Modul queue nicht verdecken.

    service.py stellt resources/lib per sys.path.insert(0, ...) voran. Hiesse
    unser Modul queue.py, waere die Standardbibliothek fuer den gesamten
    Kodi-Prozess ersetzt.
    """
    import queue as stdlib_queue
    assert hasattr(stdlib_queue, "Queue")
    assert not hasattr(stdlib_queue, "Warteschlange")
    assert hasattr(pending, "Warteschlange")


def test_eintragen_und_lesen(tmp_path):
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.eintragen("/media/x.mkv", "kein Titel erkannt")

    assert w.anzahl() == 1
    assert w.eintraege()[0]["pfad"] == "/media/x.mkv"
    assert w.eintraege()[0]["versuche"] == 1


def test_wiederholtes_eintragen_zaehlt_versuche(tmp_path):
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.eintragen("/media/x.mkv", "kein Titel")
    w.eintragen("/media/x.mkv", "kein Titel")
    w.eintragen("/media/x.mkv", "immer noch nicht")

    assert w.anzahl() == 1, "kein Duplikat"
    assert w.eintraege()[0]["versuche"] == 3
    assert w.eintraege()[0]["grund"] == "immer noch nicht", "letzter Grund gewinnt"


def test_seit_bleibt_beim_ersten_zeitpunkt(tmp_path):
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.eintragen("/media/x.mkv", "grund")
    zuerst = w.eintraege()[0]["seit"]
    w.eintragen("/media/x.mkv", "anderer grund")
    assert w.eintraege()[0]["seit"] == zuerst


def test_entfernen(tmp_path):
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.eintragen("/media/x.mkv", "grund")
    w.entfernen("/media/x.mkv")
    assert w.anzahl() == 0


def test_entfernen_von_unbekanntem_wirft_nicht(tmp_path):
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.entfernen("/media/nie-eingetragen.mkv")
    assert w.anzahl() == 0


def test_ueberlebt_neustart(tmp_path):
    pfad = str(tmp_path / "q.json")
    w = pending.Warteschlange(pfad)
    w.eintragen("/media/x.mkv", "grund")
    w.speichere()

    w2 = pending.Warteschlange(pfad)
    assert w2.anzahl() == 1


def test_aufraeumen_entfernt_verschwundene(tmp_path):
    vorhanden = tmp_path / "da.mkv"
    vorhanden.write_bytes(b"x")
    w = pending.Warteschlange(str(tmp_path / "q.json"))
    w.eintragen(str(vorhanden), "grund")
    w.eintragen(str(tmp_path / "weg.mkv"), "grund")

    entfernt = w.aufraeumen()

    assert entfernt == 1
    assert w.anzahl() == 1


def test_kaputte_datei_wirft_nicht(tmp_path):
    pfad = tmp_path / "q.json"
    pfad.write_text("kaputt[", encoding="utf-8")
    w = pending.Warteschlange(str(pfad))
    assert w.anzahl() == 0

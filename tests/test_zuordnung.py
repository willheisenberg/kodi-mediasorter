import pytest

import zuordnung
from test_durchlauf import baue_umgebung, stabil_machen
import durchlauf
import resolver


def vorschlaege():
    return [
        {"id": "tvmaze:1", "ziel": "Example (2020)", "beschreibung": "Example | 2020 | Sender A"},
        {"id": "tvmaze:2", "ziel": "Example (2023)", "beschreibung": "Example | 2023 | Sender B"},
    ]


def baue_frage(tmp_path):
    obj = zuordnung.Zuordnungen(str(tmp_path), str(tmp_path / 'daten'))
    obj.vorschlagen('example', 'example.s01e01.mkv', vorschlaege())
    return obj, tmp_path / zuordnung.DATEINAME


@pytest.mark.parametrize('kreuz', ['x', 'X'])
def test_auswahl_ueberlebt_neustart_und_neue_frage(tmp_path, kreuz):
    obj, datei = baue_frage(tmp_path)
    text = datei.read_text().replace('\n[ ]', '\n[' + kreuz + ']', 1)
    datei.write_text(text)
    obj.vorschlagen('anders', 'anders.s01e01.mkv', vorschlaege())
    neu = zuordnung.Zuordnungen(str(tmp_path), str(tmp_path / 'daten'))
    assert neu.auswahl('example') == 'Example (2020)'
    assert neu.auswahl('anders') is None
    assert text in datei.read_text()


def test_mehrere_kreuze_oder_unbekannte_kennung_werden_nicht_angenommen(tmp_path):
    obj, datei = baue_frage(tmp_path)
    assert obj.auswahl('example') is None
    text = datei.read_text()
    datei.write_text(text.replace('[ ]', '[x]'))
    assert obj.auswahl('example') is None
    datei.write_text(text.replace('[ ] ', '[x] unbekannt ', 1))
    assert obj.auswahl('example') is None


def test_geaenderte_beschriftung_ist_kein_zielpfad(tmp_path):
    obj, datei = baue_frage(tmp_path)
    datei.write_text(datei.read_text().replace('\n[ ]', '\n[x]', 1).replace('Example (2020)', '../../falsch'))
    assert obj.auswahl('example') == 'Example (2020)'


def test_bom_und_windows_zeilenenden(tmp_path):
    obj, datei = baue_frage(tmp_path)
    datei.write_bytes(('\ufeff' + datei.read_text().replace('\n[ ]', '\n[x]', 1)).replace('\n', '\r\n').encode())
    assert obj.auswahl('example') == 'Example (2020)'


def test_keine_vorschlaege_keine_leere_frage(tmp_path):
    obj = zuordnung.Zuordnungen(str(tmp_path), str(tmp_path / 'daten'))
    obj.vorschlagen('xyz', 'xyz.s01e01.mkv', [])
    assert not (tmp_path / zuordnung.DATEINAME).exists()
    assert not obj.bekannt('xyz')


def test_auswahl_fuehrt_zum_verschieben_auch_bei_sperre_und_neustart(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, 'tvmaze_per_name', lambda *a: None)
    monkeypatch.setattr(resolver, 'tvmaze_zusammengeschrieben', lambda *a: None)
    aufrufe = []
    monkeypatch.setattr(resolver, 'serien_vorschlaege', lambda *a: aufrufe.append(a) or vorschlaege())
    cfg, zustand = baue_umgebung(tmp_path)
    quelle = tmp_path / 'example.s01e01.mkv'
    quelle.write_bytes(b'video')
    stabil_machen(cfg, zustand, takte=4)
    assert quelle.exists()
    assert zustand.gesperrt('titel:example')
    datei = tmp_path / zuordnung.DATEINAME
    text = datei.read_text().replace('\n[ ]', '\n[x]', 1)
    datei.write_text(text)
    durchlauf.einmal(cfg, zustand)
    assert (tmp_path / 'Serien/Example (2020)/Season 01' / quelle.name).exists()
    assert zustand.warteschlange.anzahl() == 0
    assert len(aufrufe) == 1
    neu = durchlauf.Zustand(cfg, str(tmp_path / 'daten'))
    (tmp_path / 'example.s01e02.mkv').write_bytes(b'folge2')
    stabil_machen(cfg, neu)
    assert (tmp_path / 'Serien/Example (2020)/Season 01/example.s01e02.mkv').exists()
    assert not datei.exists()
    assert len(aufrufe) == 1


def test_mehrere_kreuze_blockieren_auch_bereits_gecachete_auswahl(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    obj = zustand.zuordnungen
    obj.vorschlagen('example', 'example.s01e01.mkv', vorschlaege())
    datei = tmp_path / zuordnung.DATEINAME
    datei.write_text(datei.read_text().replace('[ ]', '[x]'))
    zustand.cache.setze('example', 'Example (2020)')
    quelle = tmp_path / 'example.s01e01.mkv'
    quelle.write_bytes(b'video')
    stabil_machen(cfg, zustand)
    assert quelle.exists()
    assert zustand.warteschlange.anzahl() == 1


def test_trockenlauf_liest_auswahl_aber_verschiebt_nichts(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path, dry_run=True)
    zustand.zuordnungen.vorschlagen('example', 'example.s01e01.mkv', vorschlaege())
    datei = tmp_path / zuordnung.DATEINAME
    datei.write_text(datei.read_text().replace('\n[ ]', '\n[x]', 1))
    quelle = tmp_path / 'example.s01e01.mkv'
    quelle.write_bytes(b'video')
    stabil_machen(cfg, zustand)
    assert quelle.exists()
    assert datei.exists()
    assert not (tmp_path / 'Serien/Example (2020)').exists()


def test_unvollstaendig_gespeicherte_auswahl_bleibt_wartend(tmp_path):
    obj, datei = baue_frage(tmp_path)
    text = datei.read_text().replace('\n[ ]', '\n[x]', 1)
    datei.write_text(text.split('ENDE')[0])
    assert obj.auswahl('example') is None
    zeilen = text.splitlines()
    datei.write_text('\n'.join(z for z in zeilen if not z.startswith('[ ]')))
    assert obj.auswahl('example') is None
    datei.write_text(text)
    assert obj.auswahl('example') == 'Example (2020)'


def test_aufraeumen_behaelt_offene_fragen_und_deren_kreuze(tmp_path):
    obj, datei = baue_frage(tmp_path)
    datei.write_text(datei.read_text().replace('\n[ ]', '\n[x]', 1))
    obj.vorschlagen('anders', 'anders.s01e01.mkv', vorschlaege())
    anderer_abschnitt = datei.read_text().split('SERIE ')[2]
    obj.erledigt('Example (2020)')
    obj.aufraeumen()
    assert 'Suchname: example' not in datei.read_text()
    assert anderer_abschnitt in datei.read_text()
    neu = zuordnung.Zuordnungen(str(tmp_path), str(tmp_path / 'daten'))
    assert neu.auswahl('example') == 'Example (2020)'
    assert neu.auswahl('anders') is None


def test_kollision_behaelt_auswahldatei(tmp_path):
    cfg, zustand = baue_umgebung(tmp_path)
    zustand.zuordnungen.vorschlagen('example', 'example.s01e01.mkv', vorschlaege())
    datei = tmp_path / zuordnung.DATEINAME
    datei.write_text(datei.read_text().replace('\n[ ]', '\n[x]', 1))
    quelle = tmp_path / 'example.s01e01.mkv'
    quelle.write_bytes(b'neu')
    ziel = tmp_path / 'Serien/Example (2020)/Season 01' / quelle.name
    ziel.parent.mkdir(parents=True)
    ziel.write_bytes(b'alt')
    stabil_machen(cfg, zustand)
    assert datei.exists()
    assert quelle.exists()
    assert not zustand.zuordnungen.daten['example'].get('ausgewaehlt')


def test_speicherfehler_loescht_keine_auswahl(tmp_path, monkeypatch):
    obj, datei = baue_frage(tmp_path)
    datei.write_text(datei.read_text().replace('\n[ ]', '\n[x]', 1))
    def fehler(*args):
        raise OSError('voll')
    monkeypatch.setattr(zuordnung.os, 'replace', fehler)
    obj.erledigt('Example (2020)')
    obj.aufraeumen()
    assert datei.exists()
    assert not obj.daten['example'].get('ausgewaehlt')

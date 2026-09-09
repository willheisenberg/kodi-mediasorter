import os

import pytest

import config


def basis(tmp_path, **abweichungen):
    werte = {
        "watch_path": str(tmp_path),
        "series_path": "Serien",
        "movies_path": "Movies",
        "ignore_list": "Musik,Training,youtubePlaylists,lost+found",
        "interval_seconds": 30,
        "stability_cycles": 2,
        "rar_quiet_seconds": 120,
        "dry_run": True,
        "notify": True,
        "library_scan": True,
        "opensubtitles_api_key": "",
    }
    werte.update(abweichungen)
    return config.Config.aus_dict(werte)


def test_relative_ziele_werden_unter_watch_path_aufgeloest(tmp_path):
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Movies").mkdir()
    c = basis(tmp_path)
    assert c.ziel_serien() == str(tmp_path / "Serien")
    assert c.ziel_filme() == str(tmp_path / "Movies")


def test_absolute_ziele_bleiben_absolut(tmp_path):
    anderswo = tmp_path / "woanders"
    anderswo.mkdir()
    c = basis(tmp_path, series_path=str(anderswo))
    assert c.ziel_serien() == str(anderswo)


def test_ignorierliste_wird_zerlegt(tmp_path):
    c = basis(tmp_path)
    assert "Musik" in c.ignore_list
    assert "lost+found" in c.ignore_list
    assert len(c.ignore_list) == 4


def test_gueltige_konfiguration(tmp_path):
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Movies").mkdir()
    assert basis(tmp_path).validiere() == []


def test_fehlender_watch_path(tmp_path):
    c = basis(tmp_path, watch_path=str(tmp_path / "gibtsnicht"))
    fehler = c.validiere()
    assert any("watch_path" in f for f in fehler)


def test_fehlendes_ziel_wird_nicht_angelegt(tmp_path):
    (tmp_path / "Serien").mkdir()
    c = basis(tmp_path)                      # Movies fehlt absichtlich
    fehler = c.validiere()
    assert any("Movies" in f for f in fehler)
    assert not (tmp_path / "Movies").exists(), "Ziel darf nicht angelegt werden"


def test_ziel_gleich_watch_path_abgelehnt(tmp_path):
    (tmp_path / "Movies").mkdir()
    c = basis(tmp_path, series_path=str(tmp_path))
    assert any("identisch" in f.lower() for f in c.validiere())


def test_ziel_als_elternverzeichnis_abgelehnt(tmp_path):
    unter = tmp_path / "unten"
    unter.mkdir()
    (unter / "Movies").mkdir()
    (unter / "Serien").mkdir()
    c = basis(unter, movies_path=str(tmp_path))
    assert any("eltern" in f.lower() for f in c.validiere())


def test_ziel_auf_anderer_platte_abgelehnt(tmp_path, monkeypatch):
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Movies").mkdir()
    c = basis(tmp_path)

    echtes_stat = os.stat

    class FakeStat:
        def __init__(self, st, dev):
            self._st = st
            self.st_dev = dev

        def __getattr__(self, name):
            return getattr(self._st, name)

    def gefaelscht(pfad, *a, **kw):
        st = echtes_stat(pfad, *a, **kw)
        if str(pfad).endswith("Movies"):
            return FakeStat(st, st.st_dev + 1)
        return st

    monkeypatch.setattr(os, "stat", gefaelscht)
    fehler = c.validiere()
    assert any("platte" in f.lower() for f in fehler)


def test_ignoriert_enthaelt_ziele_im_watch_ordner(tmp_path):
    (tmp_path / "Serien").mkdir()
    (tmp_path / "Movies").mkdir()
    ignoriert = basis(tmp_path).ignoriert()
    assert "Serien" in ignoriert
    assert "Movies" in ignoriert
    assert "Musik" in ignoriert


def test_externe_ziele_stehen_nicht_in_der_ignorierliste(tmp_path):
    anderswo = tmp_path.parent / "extern"
    anderswo.mkdir(exist_ok=True)
    c = basis(tmp_path, series_path=str(anderswo))
    assert "extern" not in c.ignoriert()

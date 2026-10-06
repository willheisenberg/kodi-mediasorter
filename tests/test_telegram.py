import json
import urllib.error
import urllib.parse

import config
import log
import telegram

FILM = {"typ": "film", "titel": "Blow (2001)"}
FOLGE = {"typ": "serie", "titel": "Nebula Station", "staffel": 4, "episoden": [8]}


class Antwort:
    def __init__(self, daten):
        self._roh = json.dumps(daten).encode("utf-8")

    def read(self):
        return self._roh

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def aktive_cfg(**abweichungen):
    werte = {
        "watch_path": "/tmp", "series_path": "Serien", "movies_path": "Movies",
        "interval_seconds": 30, "stability_cycles": 1, "rar_quiet_seconds": 0,
        "dry_run": False, "notify": False, "library_scan": False,
        "telegram_enabled": True, "telegram_token": "123:GEHEIM",
        "telegram_chat_id": "-100200300",
    }
    werte.update(abweichungen)
    return config.Config.aus_dict(werte)


def test_standardsatz_fuer_film():
    assert telegram.text_fuer(FILM) == "🎬 Der Film Blow (2001) wurde zu Kodi hinzugefügt."


def test_standardsatz_fuer_serie_nennt_staffel_und_episode():
    assert telegram.text_fuer(FOLGE) == (
        "📺 Die Serie Nebula Station Staffel 4 Episode 8 wurde zu Kodi hinzugefügt."
    )


def test_zusammenhaengende_episoden_als_bereich():
    paket = dict(FOLGE, episoden=[3, 1, 2])
    assert "Staffel 4 Episode 1–3 wurde" in telegram.text_fuer(paket)


def test_lueckenhafte_episoden_als_liste():
    paket = dict(FOLGE, episoden=[1, 2, 5])
    assert "Episode 1, 2, 5 wurde" in telegram.text_fuer(paket)


def test_eigene_vorlagen_werden_benutzt():
    assert telegram.text_fuer(FILM, vorlage_film="Neu: {titel}") == "Neu: Blow (2001)"
    assert telegram.text_fuer(
        FOLGE, vorlage_serie="{titel} S{staffel}E{episode}"
    ) == "Nebula Station S4E8"


def test_leere_vorlage_faellt_auf_standard_zurueck():
    assert telegram.text_fuer(FILM, vorlage_film="  ") == telegram.text_fuer(FILM)


def test_kaputte_vorlage_faellt_auf_standard_zurueck():
    for kaputt in ("{name} ist da", "{titel", "{0} ist da"):
        assert telegram.text_fuer(FILM, vorlage_film=kaputt) == telegram.text_fuer(FILM)


def test_sende_schickt_text_an_die_gruppe():
    anfragen = []

    def oeffner(anfrage, timeout=None):
        anfragen.append(anfrage)
        return Antwort({"ok": True})

    assert telegram.sende("123:GEHEIM", "-100200300", "Hallo ü", oeffner) is True
    anfrage = anfragen[0]
    assert anfrage.full_url == "https://api.telegram.org/bot123:GEHEIM/sendMessage"
    felder = urllib.parse.parse_qs(anfrage.data.decode("utf-8"))
    assert felder == {"chat_id": ["-100200300"], "text": ["Hallo ü"]}


def test_sende_meldet_ablehnung_von_telegram():
    def oeffner(anfrage, timeout=None):
        return Antwort({"ok": False, "description": "chat not found"})

    assert telegram.sende("123:GEHEIM", "1", "Hallo", oeffner) is False


def test_sende_ueberlebt_netzwerkfehler_und_verraet_den_token_nicht():
    gesammelt = []
    log.set_sink(lambda level, msg: gesammelt.append(msg))

    def oeffner(anfrage, timeout=None):
        raise urllib.error.URLError("keine Verbindung zu " + anfrage.full_url)

    try:
        assert telegram.sende("123:GEHEIM", "1", "Hallo", oeffner) is False
    finally:
        log.set_sink(None)
    assert gesammelt
    assert not any("GEHEIM" in msg for msg in gesammelt)


def test_melde_sendet_eine_nachricht_pro_eintrag():
    texte = []

    def oeffner(anfrage, timeout=None):
        texte.append(urllib.parse.parse_qs(anfrage.data.decode("utf-8"))["text"][0])
        return Antwort({"ok": True})

    cfg = aktive_cfg(telegram_text_film="Film: {titel}")
    assert telegram.melde(cfg, [FILM, FOLGE], oeffner) == 2
    assert texte == [
        "Film: Blow (2001)",
        "📺 Die Serie Nebula Station Staffel 4 Episode 8 wurde zu Kodi hinzugefügt.",
    ]


def test_melde_sendet_nichts_ohne_token_chat_oder_schalter():
    def oeffner(anfrage, timeout=None):
        raise AssertionError("darf nicht senden")

    for abweichung in ({"telegram_enabled": False}, {"telegram_token": " "},
                       {"telegram_chat_id": ""}):
        assert telegram.melde(aktive_cfg(**abweichung), [FILM], oeffner) == 0

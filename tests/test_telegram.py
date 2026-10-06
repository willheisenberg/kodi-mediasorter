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
    assert telegram.text_fuer(FILM) == "🎬 The movie Blow (2001) was added to Kodi."


def test_standardsatz_fuer_serie_nennt_staffel_und_episode():
    assert telegram.text_fuer(FOLGE) == (
        "📺 The series Nebula Station Season 4 Episode 8 was added to Kodi."
    )


def test_zusammenhaengende_episoden_als_bereich():
    paket = dict(FOLGE, episoden=[3, 1, 2])
    assert "Season 4 Episode 1–3 was" in telegram.text_fuer(paket)


def test_lueckenhafte_episoden_als_liste():
    paket = dict(FOLGE, episoden=[1, 2, 5])
    assert "Episode 1, 2, 5 was" in telegram.text_fuer(paket)


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
        "📺 The series Nebula Station Season 4 Episode 8 was added to Kodi.",
    ]


def test_melde_sendet_nichts_ohne_token_chat_oder_schalter():
    def oeffner(anfrage, timeout=None):
        raise AssertionError("darf nicht senden")

    for abweichung in ({"telegram_enabled": False}, {"telegram_token": " "},
                       {"telegram_chat_id": ""}):
        assert telegram.melde(aktive_cfg(**abweichung), [FILM], oeffner) == 0


class Gruppe:
    """Nimmt Anfragen an wie Telegram und merkt sich Methode und Felder."""

    def __init__(self, ablehnen=()):
        self.anfragen = []
        self.ablehnen = ablehnen

    def __call__(self, anfrage, timeout=None):
        methode = anfrage.full_url.rsplit("/", 1)[1]
        felder = {k: v[0] for k, v in
                  urllib.parse.parse_qs(anfrage.data.decode("utf-8")).items()}
        self.anfragen.append((methode, felder))
        if methode in self.ablehnen:
            return Antwort({"ok": False, "description": "abgelehnt"})
        return Antwort({"ok": True, "result": {"message_id": 100 + len(self.anfragen)}})

    def methoden(self):
        return [methode for methode, _felder in self.anfragen]


def folge(staffel, episode, titel="Nebula Station"):
    return {"typ": "serie", "titel": titel, "staffel": staffel, "episoden": [episode]}


def test_mehrere_staffeln_wiederholen_den_staffelblock():
    gesammelt = {"typ": "serie", "titel": "Nebula Station",
                 "staffeln": {2: [1, 2], 1: [1, 2, 3, 4]}}
    assert telegram.text_fuer(gesammelt) == (
        "📺 The series Nebula Station Season 1 Episode 1–4 & Season 2 Episode 1–2"
        " was added to Kodi."
    )
    assert telegram.text_fuer(
        dict(gesammelt, staffeln={1: [1], 2: [3], 3: [5, 7]}),
        vorlage_serie="{titel} S{staffel}E{episode} ist da",
    ) == "Nebula Station S1E1, S2E3 & S3E5, 7 ist da"


def test_vorlage_ohne_staffelblock_faellt_bei_mehreren_staffeln_auf_standard_zurueck():
    gesammelt = {"typ": "serie", "titel": "Nebula Station", "staffeln": {1: [1], 2: [1]}}
    assert telegram.text_fuer(gesammelt, vorlage_serie="Neues von {titel}") == (
        telegram.text_fuer(gesammelt)
    )


def test_weitere_folge_derselben_serie_ersetzt_die_letzte_nachricht(tmp_path):
    merk = str(tmp_path / "telegram.json")
    gruppe = Gruppe()
    cfg = aktive_cfg()

    for takt, eintrag in enumerate([folge(1, 6), folge(1, 7), folge(2, 1)]):
        assert telegram.melde(cfg, [eintrag], gruppe, merk, jetzt=1000 + 120 * takt) == 1

    assert gruppe.methoden() == [
        "sendMessage", "sendMessage", "deleteMessage", "sendMessage", "deleteMessage",
    ]
    assert "disable_notification" not in gruppe.anfragen[0][1]
    assert gruppe.anfragen[1][1] == {
        "chat_id": "-100200300", "disable_notification": "true",
        "text": "📺 The series Nebula Station Season 1 Episode 6–7 was added to Kodi.",
    }
    assert gruppe.anfragen[2][1] == {"chat_id": "-100200300", "message_id": "101"}
    assert "Season 1 Episode 6–7 & Season 2 Episode 1 was" in gruppe.anfragen[3][1]["text"]
    assert gruppe.anfragen[4][1]["message_id"] == "102"


def test_andere_serie_oder_film_beginnt_eine_neue_nachricht(tmp_path):
    merk = str(tmp_path / "telegram.json")
    gruppe = Gruppe()
    cfg = aktive_cfg()

    telegram.melde(cfg, [folge(1, 1), folge(1, 1, titel="Kupferstadt")], gruppe, merk, jetzt=1000)
    telegram.melde(cfg, [folge(1, 2)], gruppe, merk, jetzt=1100)
    telegram.melde(cfg, [folge(1, 2, titel="Kupferstadt"), FILM], gruppe, merk, jetzt=1200)
    telegram.melde(cfg, [folge(1, 3, titel="Kupferstadt")], gruppe, merk, jetzt=1300)

    assert gruppe.methoden() == [
        "sendMessage", "sendMessage", "sendMessage", "sendMessage", "sendMessage",
        "sendMessage",
    ]
    assert "Episode 3 was" in gruppe.anfragen[-1][1]["text"]


def test_alte_nachricht_wird_nicht_mehr_bearbeitet(tmp_path):
    merk = str(tmp_path / "telegram.json")
    gruppe = Gruppe()
    cfg = aktive_cfg()

    telegram.melde(cfg, [folge(1, 1)], gruppe, merk, jetzt=1000)
    telegram.melde(cfg, [folge(1, 2)], gruppe, merk, jetzt=1000 + 7 * 24 * 3600)

    assert gruppe.methoden() == ["sendMessage", "sendMessage"]
    assert "Episode 2 was" in gruppe.anfragen[1][1]["text"]


def test_nicht_mehr_loeschbare_nachricht_haelt_das_sammeln_nicht_auf(tmp_path):
    merk = str(tmp_path / "telegram.json")
    gruppe = Gruppe(ablehnen=("deleteMessage",))
    cfg = aktive_cfg()

    telegram.melde(cfg, [folge(1, 1)], gruppe, merk, jetzt=1000)
    assert telegram.melde(cfg, [folge(1, 2)], gruppe, merk, jetzt=1100) == 1
    telegram.melde(cfg, [folge(1, 3)], gruppe, merk, jetzt=1200)

    assert gruppe.methoden() == [
        "sendMessage", "sendMessage", "deleteMessage", "sendMessage", "deleteMessage",
    ]
    assert "Episode 1–3 was" in gruppe.anfragen[3][1]["text"]
    assert gruppe.anfragen[4][1]["message_id"] == "102"


def test_fehlgeschlagenes_senden_laesst_die_alte_nachricht_stehen(tmp_path):
    merk = str(tmp_path / "telegram.json")
    gruppe = Gruppe()
    cfg = aktive_cfg()

    telegram.melde(cfg, [folge(1, 1)], gruppe, merk, jetzt=1000)
    gruppe.ablehnen = ("sendMessage",)
    assert telegram.melde(cfg, [folge(1, 2)], gruppe, merk, jetzt=1100) == 0
    gruppe.ablehnen = ()
    telegram.melde(cfg, [folge(1, 3)], gruppe, merk, jetzt=1200)

    assert gruppe.methoden() == ["sendMessage", "sendMessage", "sendMessage", "deleteMessage"]
    assert "Episode 1, 3 was" in gruppe.anfragen[2][1]["text"]
    assert gruppe.anfragen[3][1]["message_id"] == "101"

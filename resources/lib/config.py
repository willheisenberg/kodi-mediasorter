"""Einstellungen lesen und Pfade validieren.

xbmcaddon wird bewusst erst innerhalb von aus_kodi() importiert, damit dieses
Modul ohne laufendes Kodi importierbar und damit testbar bleibt.
"""
import os

import log

SCHLUESSEL_TEXT = (
    "watch_path", "series_path", "movies_path", "ignore_list",
    "opensubtitles_api_key", "telegram_token", "telegram_chat_id",
    "telegram_text_film", "telegram_text_serie",
)
SCHLUESSEL_ZAHL = ("interval_seconds", "stability_cycles", "rar_quiet_seconds")
SCHLUESSEL_JA_NEIN = ("dry_run", "notify", "library_scan", "telegram_enabled")


def _byte(zeichen):
    try:
        return zeichen.encode("cp1252")
    except UnicodeEncodeError:
        if ord(zeichen) < 256:          # 0x81, 0x8d, 0x8f, 0x90, 0x9d
            return bytes([ord(zeichen)])
        raise


def entwirre(text):
    """Macht doppelt kodierten Text aus Kodi wieder lesbar.

    Eine von Hand bearbeitete settings.xml traegt keine Kodierungsangabe.
    Kodi liest ihre UTF-8-Bytes dann als Windows-1252, und aus hinzugefügt
    wird hinzugefÃ¼gt. Richtiger Text uebersteht den Rueckweg nicht als
    gueltiges UTF-8 und bleibt deshalb unveraendert.
    """
    try:
        return b"".join(_byte(z) for z in text).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


class Config:
    def __init__(self, werte):
        self.watch_path = werte["watch_path"]
        self.series_path = werte["series_path"]
        self.movies_path = werte["movies_path"]
        self.ignore_list = [
            t.strip() for t in str(werte.get("ignore_list", "")).split(",") if t.strip()
        ]
        self.interval_seconds = int(werte["interval_seconds"])
        self.stability_cycles = int(werte["stability_cycles"])
        self.rar_quiet_seconds = int(werte["rar_quiet_seconds"])
        self.dry_run = bool(werte["dry_run"])
        self.notify = bool(werte["notify"])
        self.library_scan = bool(werte["library_scan"])
        self.opensubtitles_api_key = (werte.get("opensubtitles_api_key") or "").strip()
        self.telegram_enabled = bool(werte.get("telegram_enabled"))
        self.telegram_token = (werte.get("telegram_token") or "").strip()
        self.telegram_chat_id = (werte.get("telegram_chat_id") or "").strip()
        self.telegram_text_film = (werte.get("telegram_text_film") or "").strip()
        self.telegram_text_serie = (werte.get("telegram_text_serie") or "").strip()

    @classmethod
    def aus_dict(cls, werte):
        return cls(werte)

    @classmethod
    def aus_kodi(cls):
        import xbmcaddon

        addon = xbmcaddon.Addon()
        werte = {}
        for k in SCHLUESSEL_TEXT:
            werte[k] = entwirre(addon.getSetting(k))
        for k in SCHLUESSEL_ZAHL:
            werte[k] = addon.getSettingInt(k)
        for k in SCHLUESSEL_JA_NEIN:
            werte[k] = addon.getSettingBool(k)
        return cls(werte)

    def telegram_aktiv(self):
        return bool(
            self.telegram_enabled and self.telegram_token and self.telegram_chat_id
        )

    def _absolut(self, pfad):
        if os.path.isabs(pfad):
            return os.path.normpath(pfad)
        return os.path.normpath(os.path.join(self.watch_path, pfad))

    def ziel_serien(self):
        return self._absolut(self.series_path)

    def ziel_filme(self):
        return self._absolut(self.movies_path)

    def ziele(self):
        return {"Serien": self.ziel_serien(), "Filme": self.ziel_filme()}

    def validiere(self):
        """Liste von Fehlermeldungen. Leer heisst gueltig."""
        fehler = []
        watch = os.path.normpath(self.watch_path)

        if not os.path.isdir(watch):
            fehler.append("watch_path existiert nicht: %s" % watch)
            log.error(fehler[-1])
            return fehler                     # ohne Wurzel ist der Rest sinnlos

        for bezeichnung, ziel in self.ziele().items():
            ziel = os.path.normpath(ziel)
            if not os.path.isdir(ziel):
                fehler.append(
                    "Ziel für %s existiert nicht und wird nicht angelegt: %s"
                    % (bezeichnung, ziel)
                )
                continue
            if ziel == watch:
                fehler.append(
                    "Ziel für %s ist identisch mit dem überwachten Ordner" % bezeichnung
                )
                continue
            if watch.startswith(ziel + os.sep):
                fehler.append(
                    "Ziel für %s ist ein Elternverzeichnis des überwachten Ordners"
                    % bezeichnung
                )
                continue
            try:
                if os.stat(ziel).st_dev != os.stat(watch).st_dev:
                    fehler.append(
                        "Ziel für %s liegt auf einer anderen Platte; es wird "
                        "ausschliesslich umbenannt, nicht kopiert: %s"
                        % (bezeichnung, ziel)
                    )
            except OSError as ausnahme:
                fehler.append("Ziel für %s nicht prüfbar: %s" % (bezeichnung, ausnahme))

        for meldung in fehler:
            log.error(meldung)
        return fehler

    def ignoriert(self):
        """Namen, die der Scanner ueberspringt: Liste plus Ziele im Watch-Ordner."""
        namen = set(self.ignore_list)
        watch = os.path.normpath(self.watch_path)
        for ziel in self.ziele().values():
            ziel = os.path.normpath(ziel)
            if ziel.startswith(watch + os.sep):
                namen.add(os.path.relpath(ziel, watch).split(os.sep)[0])
        return namen

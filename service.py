"""Kodi-Service: ruft durchlauf.einmal() im eingestellten Takt auf."""
import os
import sys

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
sys.path.insert(
    0,
    xbmcvfs.translatePath(
        os.path.join(ADDON.getAddonInfo("path"), "resources", "lib")
    ),
)

import config          # noqa: E402
import durchlauf       # noqa: E402
import library         # noqa: E402
import log             # noqa: E402

_KODI_LEVEL = {
    log.DEBUG: xbmc.LOGDEBUG,
    log.INFO: xbmc.LOGINFO,
    log.WARN: xbmc.LOGWARNING,
    log.ERROR: xbmc.LOGERROR,
}


def _nach_kodi(level, nachricht):
    xbmc.log("[service.mediasorter] " + nachricht, _KODI_LEVEL[level])


def main():
    log.set_sink(_nach_kodi)
    monitor = xbmc.Monitor()

    datenordner = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    if not os.path.isdir(datenordner):
        os.makedirs(datenordner, exist_ok=True)

    cfg = config.Config.aus_kodi()
    fehler = cfg.validiere()
    if fehler and cfg.notify:
        library.benachrichtige("Media Sorter", fehler[0], 8000)
    zustand = None if fehler else durchlauf.Zustand(cfg, datenordner)

    gemeldet_wartend = -1
    log.info("Dienst gestartet, Takt %d s, Trockenlauf %s"
             % (cfg.interval_seconds, "an" if cfg.dry_run else "aus"))

    while not monitor.abortRequested():
        neu = config.Config.aus_kodi()
        if neu.validiere():
            if monitor.waitForAbort(neu.interval_seconds):
                break
            continue

        if zustand is None or neu.watch_path != cfg.watch_path:
            zustand = durchlauf.Zustand(neu, datenordner)
        cfg = neu

        try:
            zaehler = durchlauf.einmal(cfg, zustand, library.spielt_gerade)
        except Exception as ausnahme:      # ein Takt darf den Dienst nie beenden
            log.error("Takt abgebrochen: %s" % ausnahme)
            zaehler = None

        if zaehler:
            if cfg.library_scan and not cfg.dry_run:
                for pfad in sorted(zaehler["zielpfade"]):
                    library.scanne(pfad)
            if cfg.notify and zaehler["verschoben"]:
                library.benachrichtige(
                    "Media Sorter", "%d Dateien einsortiert" % zaehler["verschoben"]
                )
            if cfg.notify and zaehler["wartend"] and zaehler["wartend"] != gemeldet_wartend:
                library.benachrichtige(
                    "Media Sorter", "%d Einträge brauchen Zuordnung" % zaehler["wartend"]
                )
            gemeldet_wartend = zaehler["wartend"]

        if monitor.waitForAbort(cfg.interval_seconds):
            break

    log.info("Dienst beendet")


if __name__ == "__main__":
    main()

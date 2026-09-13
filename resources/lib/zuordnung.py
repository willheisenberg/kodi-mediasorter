"""Manuelle Serienauswahl per Textdatei im Watch-Ordner.

Die Auswahlzeilen sind nur Verweise auf intern gespeicherte Vorschlaege.
Editierte Beschriftungen werden niemals als Zielpfade interpretiert.
Bestehende Abschnitte werden nicht neu geschrieben, damit Kreuze erhalten bleiben.
"""
import hashlib
import json
import os
import re

import log

DATEINAME = "Mediasorter-Zuordnung.txt"
_KOPF = """Media Sorter - Serien zuordnen
==============================
Pro Serie GENAU EIN [ ] durch [x] ersetzen und diese Datei speichern.
Der Sorter liest die Auswahl beim naechsten Takt (normalerweise 30 Sekunden).
Die Auswahl gilt auch fuer weitere Folgen dieses Suchnamens und bleibt erhalten.
Kein Kreuz oder mehrere Kreuze: Die Dateien bleiben liegen.
Nur die Klammern bearbeiten; Kennungen und Abschnittszeilen beibehalten.
Erledigte Abschnitte verschwinden nach dem Einsortieren. Ohne offene Fragen
wird diese Datei geloescht; die Zuordnungen bleiben intern gespeichert.

"""


def _kennung(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _zeile(text):
    return " ".join(str(text or "").split())


def sicherer_ordner(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name if name and name not in (".", "..") else "Serie"


class Zuordnungen:
    def __init__(self, watch_path, datenordner):
        self.pfad = os.path.join(watch_path, DATEINAME)
        self.speicher = os.path.join(datenordner, "zuordnungen.json")
        self.daten = {}
        try:
            with open(self.speicher, encoding="utf-8") as fh:
                geladen = json.load(fh)
                if isinstance(geladen, dict):
                    self.daten = geladen
        except (OSError, ValueError):
            pass

    def bekannt(self, titel):
        return titel in self.daten

    def auswahl(self, titel):
        frage = self.daten.get(titel)
        if not frage:
            return None
        if frage.get("ausgewaehlt"):
            return frage["ausgewaehlt"]
        try:
            with open(self.pfad, encoding="utf-8-sig") as fh:
                text = fh.read()
        except (OSError, UnicodeError):
            return None
        abschnitt = None
        kreuze = []
        gesehen = []
        abgeschlossen = False
        anzahl = 0
        for zeile in text.splitlines():
            kopf = re.fullmatch(r"SERIE ([a-f0-9]{20})", zeile.strip())
            if kopf:
                abschnitt = kopf.group(1)
                if abschnitt == frage["id"]:
                    anzahl += 1
            elif abschnitt == frage["id"]:
                if zeile.strip() == "ENDE":
                    abgeschlossen = True
                    abschnitt = None
                    continue
                option = re.match(r"\s*\[([ xX])\]\s+(\S+)", zeile)
                if option:
                    gesehen.append(option.group(2))
                    if option.group(1).lower() == "x":
                        kreuze.append(option.group(2))
        # Ein nur teilweise gespeicherter Abschnitt ist noch keine Auswahl.
        if (anzahl != 1 or not abgeschlossen or len(kreuze) != 1
                or sorted(gesehen) != sorted(frage["optionen"])):
            return None
        return frage["optionen"].get(kreuze[0], {}).get("ziel")

    def erledigt(self, ziel):
        """Erst nach erfolgreichem Verschieben die Auswahl dauerhaft bestaetigen."""
        neu = dict(self.daten)
        for titel, frage in self.daten.items():
            if not frage.get("ausgewaehlt") and self.auswahl(titel) == ziel:
                neu[titel] = dict(frage, ausgewaehlt=ziel)
        if neu == self.daten:
            return
        try:
            with open(self.speicher + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(neu, fh, ensure_ascii=False, indent=2)
            os.replace(self.speicher + ".tmp", self.speicher)
            self.daten = neu
        except OSError as fehler:
            log.warn("Bestaetigte Serienauswahl nicht gespeichert: %s" % fehler)

    def aufraeumen(self):
        """Erledigte Abschnitte entfernen, andere Auswahlen unveraendert erhalten."""
        fertig = {f["id"] for f in self.daten.values() if f.get("ausgewaehlt")}
        if not fertig:
            return
        try:
            with open(self.pfad, encoding="utf-8-sig", newline="") as fh:
                vorher = fh.read()
            muster = r"(?m)^SERIE ([a-f0-9]{20})\r?$[\s\S]*?^ENDE\r?$(?:\r?\n)?"
            nachher = re.sub(muster, lambda m: "" if m.group(1) in fertig else m.group(), vorher)
            if nachher == vorher:
                return
            # Nicht eine zwischenzeitlich gespeicherte Benutzerauswahl ersetzen.
            with open(self.pfad, encoding="utf-8-sig", newline="") as fh:
                if fh.read() != vorher:
                    return
            if not re.search(r"(?m)^SERIE ", nachher):
                os.unlink(self.pfad)
            else:
                with open(self.pfad + ".tmp", "w", encoding="utf-8", newline="") as fh:
                    fh.write(nachher)
                os.replace(self.pfad + ".tmp", self.pfad)
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError) as fehler:
            log.warn("Serienauswahldatei nicht aufgeraeumt: %s" % fehler)

    def vorschlagen(self, titel, quelle, vorschlaege):
        if not vorschlaege or titel in self.daten:
            return
        frage = {"id": _kennung(titel), "optionen": {}}
        zeilen = ["SERIE " + frage["id"], "Suchname: " + _zeile(titel),
                  "Beispiel: " + _zeile(quelle)]
        for v in vorschlaege:
            ziel = sicherer_ordner(v["ziel"])
            kennung = _kennung(titel + "\n" + v["id"])
            frage["optionen"][kennung] = dict(v, ziel=ziel)
            zeilen.append("[ ] %s  %s | Zielordner: %s" % (
                kennung, _zeile(v["beschreibung"]), ziel))
        zeilen.append("ENDE\n")
        try:
            # Intern zuerst sichern: Eine sichtbare Auswahl ist nur mit
            # gespeicherten Vorschlaegen verwendbar.
            neu = dict(self.daten, **{titel: frage})
            os.makedirs(os.path.dirname(self.speicher), exist_ok=True)
            with open(self.speicher + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(neu, fh, ensure_ascii=False, indent=2)
            os.replace(self.speicher + ".tmp", self.speicher)
            with open(self.pfad, "a", encoding="utf-8") as fh:
                if fh.tell() == 0:
                    fh.write(_KOPF)
                fh.write("\n" + "\n".join(zeilen) + "\n")
            self.daten = neu
            log.info("Serienauswahl bereit: %s (%s)" % (self.pfad, titel))
        except OSError as fehler:
            log.warn("Serienauswahl nicht gespeichert: %s" % fehler)

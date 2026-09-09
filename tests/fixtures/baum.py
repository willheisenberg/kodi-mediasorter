"""Baut einen Verzeichnisbaum aus Pfadangaben als 0-Byte-Attrappen nach."""
import os


def baue(ziel, eintraege):
    for eintrag in eintraege:
        pfad = os.path.join(ziel, eintrag.replace("/", os.sep))
        if eintrag.endswith("/"):
            os.makedirs(pfad, exist_ok=True)
            continue
        ordner = os.path.dirname(pfad)
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        with open(pfad, "wb") as fh:
            fh.write(b"")

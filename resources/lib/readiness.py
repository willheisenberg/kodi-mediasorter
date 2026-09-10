"""Prueft, ob eine Datei oder ein Ordner fertig geschrieben ist.

Lage 1 hier: die Sollgroesse steht im Containerheader und laesst sich exakt
gegen die Ist-Groesse pruefen. Weitere Lagen folgen unten.
"""
import os
import struct

import log

_MKV_MAGIC = b"\x1a\x45\xdf\xa3"
_SEGMENT_ID = b"\x18\x53\x80\x67"


def _lies_vint(daten, pos):
    """Liest ein EBML-VINT. Gibt (wert, laenge, ist_unknown) oder (None, 1, False)."""
    if pos >= len(daten):
        return None, 1, False
    erstes = daten[pos]
    if erstes == 0:
        return None, 1, False
    n = 1
    while n <= 8 and not (erstes & (0x80 >> (n - 1))):
        n += 1
    if n > 8 or pos + n > len(daten):
        return None, 1, False
    wert = erstes & ((0x80 >> (n - 1)) - 1)
    for i in range(1, n):
        wert = (wert << 8) | daten[pos + i]
    ist_unknown = wert == (1 << (7 * n)) - 1
    return wert, n, ist_unknown


def _mkv_sollgroesse(kopf):
    if kopf[:4] != _MKV_MAGIC:
        return None
    laenge, n, _ = _lies_vint(kopf, 4)
    if laenge is None:
        return None
    pos = 4 + n + laenge
    if kopf[pos : pos + 4] != _SEGMENT_ID:
        return None
    seg, n2, unknown = _lies_vint(kopf, pos + 4)
    if seg is None or unknown:
        return None
    return pos + 4 + n2 + seg


def _avi_sollgroesse(kopf):
    if kopf[:4] != b"RIFF" or len(kopf) < 8:
        return None
    (laenge,) = struct.unpack("<I", kopf[4:8])
    return 8 + laenge


def erwartete_groesse(pfad):
    """Sollgroesse in Bytes aus dem Containerheader, oder None."""
    try:
        with open(pfad, "rb") as fh:
            kopf = fh.read(64)
    except OSError as fehler:
        log.debug("Kopf nicht lesbar: %s (%s)" % (pfad, fehler))
        return None

    if len(kopf) < 8:
        return None

    endung = os.path.splitext(pfad)[1].lower()
    if endung == ".avi":
        return _avi_sollgroesse(kopf)
    if endung in (".mkv", ".mka", ".mks"):
        return _mkv_sollgroesse(kopf)
    # MP4 und alles Uebrige: keine Aussage, faellt auf Lage 4 zurueck
    return None


def ist_vollstaendig(pfad):
    """True, False, oder None wenn der Container keine Sollgroesse nennt."""
    soll = erwartete_groesse(pfad)
    if soll is None:
        return None
    try:
        ist = os.path.getsize(pfad)
    except OSError:
        return None
    return ist >= soll


# --- Lagen 2 bis 4 und SFV ---

import re
import time

TEMP_ENDUNGEN = (".part", ".jdtmp", ".tmp", ".!qb", ".crdownload", ".filepart")

# .rar, .r00 bis .r99, .partNN.rar — jeweils am Namensende
_RAR = re.compile(r"(?i)(\.rar|\.r\d{2}|\.part\d+\.rar)$")


def ist_temporaer(name):
    """Lage 3: Endung am Namensende deutet auf eine unfertige Datei.

    Die Verankerung mit endswith ist wesentlich. Ohne sie wuerde
    Example.Part.Two.2024... dauerhaft als unfertig gelten.
    """
    return name.lower().endswith(TEMP_ENDUNGEN)


def rar_aktiv(ordner, ruhe_sekunden, jetzt=None):
    """Lage 2: Liegt ein kuerzlich veraendertes RAR-Archiv im Ordner?"""
    jetzt = time.time() if jetzt is None else jetzt
    try:
        eintraege = os.listdir(ordner)
    except OSError:
        return False

    for name in eintraege:
        if not _RAR.search(name):
            continue
        try:
            alter = jetzt - os.path.getmtime(os.path.join(ordner, name))
        except OSError:
            continue
        if alter < ruhe_sekunden:
            return True
    return False


def sfv_vollstaendig(ordner):
    """Existieren alle in der SFV genannten Dateien? None ohne SFV."""
    try:
        eintraege = os.listdir(ordner)
    except OSError:
        return None

    sfvs = [n for n in eintraege if n.lower().endswith(".sfv")]
    if not sfvs:
        return None

    for sfv in sfvs:
        try:
            with open(os.path.join(ordner, sfv), encoding="utf-8", errors="replace") as fh:
                zeilen = fh.readlines()
        except OSError:
            continue
        for zeile in zeilen:
            zeile = zeile.strip()
            if not zeile or zeile.startswith(";"):
                continue
            # Format: <dateiname> <crc32>, Dateiname darf Leerzeichen enthalten
            teile = zeile.rsplit(None, 1)
            if len(teile) < 2:
                continue
            dateiname = teile[0]
            if not os.path.exists(os.path.join(ordner, dateiname)):
                log.info("SFV vermisst %s in %s" % (dateiname, ordner))
                return False
    return True


class Stabilitaet:
    """Lage 4: Groesse und mtime muessen ueber mehrere Takte gleich bleiben."""

    def __init__(self, zyklen):
        self.zyklen = zyklen
        self._zustand = {}          # pfad -> (groesse, mtime, unveraenderte_takte)

    def pruefe(self, pfad):
        try:
            st = os.stat(pfad)
        except OSError:
            self.vergiss(pfad)
            return False

        merkmal = (st.st_size, st.st_mtime)
        alt = self._zustand.get(pfad)

        if alt is None or alt[:2] != merkmal:
            self._zustand[pfad] = merkmal + (0,)
            return False

        takte = alt[2] + 1
        self._zustand[pfad] = merkmal + (takte,)
        return takte >= self.zyklen

    def vergiss(self, pfad):
        self._zustand.pop(pfad, None)

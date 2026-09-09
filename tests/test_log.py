import log


def test_sink_erhaelt_level_und_nachricht():
    gesammelt = []
    log.set_sink(lambda level, msg: gesammelt.append((level, msg)))
    try:
        log.info("hallo")
        log.error("kaputt")
    finally:
        log.set_sink(None)

    assert gesammelt == [(log.INFO, "hallo"), (log.ERROR, "kaputt")]


def test_ohne_sink_kein_absturz():
    log.set_sink(None)
    log.info("geht auf stderr")  # darf nicht werfen

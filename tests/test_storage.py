from monitor.storage import load_history, save_run


def test_sqlite_history_persists_and_avoids_duplicate_imports(tmp_path):
    database = tmp_path / "history.sqlite3"
    records = [
        {
            "classname": "suite",
            "name": "test_checkout",
            "status": "passed",
            "duration": 0.25,
            "message": "",
        }
    ]
    raw_xml = b"<testsuites><testsuite /></testsuites>"

    assert save_run(database, "run-1.xml", records, raw_xml) is True
    assert save_run(database, "run-1.xml", records, raw_xml) is False

    history = load_history(database)
    assert len(history) == 1
    assert history[0][0]["name"] == "test_checkout"
    assert history[0][0]["status"] == "passed"

from concurrent.futures import ThreadPoolExecutor

from monitor.storage import load_history, save_run


def test_concurrent_duplicate_import_is_idempotent(tmp_path):
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
    raw_xml = b"<testsuites><testsuite><testcase name='test_checkout'/></testsuite></testsuites>"

    def import_run(_):
        return save_run(database, "same-run.xml", records, raw_xml)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(import_run, range(16)))

    assert results.count(True) == 1
    assert results.count(False) == 15
    history = load_history(database)
    assert len(history) == 1
    assert len(history[0]) == 1

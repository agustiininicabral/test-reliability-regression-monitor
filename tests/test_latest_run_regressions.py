from monitor.analyzer import analyze_history


def _record(name: str, status: str) -> dict:
    return {
        "classname": "suite",
        "name": name,
        "status": status,
        "duration": 0.1,
        "message": "",
    }


def test_old_failure_is_not_reported_as_regression_when_absent_from_latest_run():
    history = [
        [_record("test_checkout", "passed")],
        [_record("test_checkout", "failed")],
        [_record("test_other", "passed")],
    ]

    report = analyze_history(history)

    assert report["newly_failing_tests"] == []
    assert report["flaky_tests"] == [
        {
            "test": "suite::test_checkout",
            "statuses": ["passed", "failed"],
        }
    ]


def test_failure_in_latest_run_after_an_earlier_pass_is_reported():
    history = [
        [_record("test_checkout", "passed")],
        [_record("test_checkout", "skipped")],
        [_record("test_checkout", "failed")],
    ]

    report = analyze_history(history)

    assert report["newly_failing_tests"] == [
        {
            "test": "suite::test_checkout",
            "statuses": ["passed", "skipped", "failed"],
        }
    ]

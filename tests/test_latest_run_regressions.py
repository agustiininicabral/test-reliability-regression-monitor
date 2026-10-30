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


def test_inventory_changes_do_not_distort_comparable_pass_rate():
    history = [
        [_record("test_shared", "passed"), _record("test_removed", "failed")],
        [_record("test_shared", "passed"), _record("test_added", "failed")],
    ]

    report = analyze_history(history)

    assert report["inventory_changes"] == {
        "added": ["suite::test_added"],
        "removed": ["suite::test_removed"],
    }
    assert report["comparable_test_count"] == 1
    assert report["comparable_pass_rate_delta_percentage_points"] == 0.0


def test_comparable_pass_rate_detects_regression_in_shared_tests():
    history = [
        [_record("test_shared", "passed"), _record("test_removed", "passed")],
        [_record("test_shared", "failed"), _record("test_added", "passed")],
    ]

    report = analyze_history(history)

    assert report["comparable_test_count"] == 1
    assert report["comparable_pass_rate_delta_percentage_points"] == -100.0
    assert report["pass_rate_delta_percentage_points"] == 0.0


def test_comparable_pass_rate_is_unavailable_without_shared_tests():
    history = [
        [_record("test_old", "passed")],
        [_record("test_new", "failed")],
    ]

    report = analyze_history(history)

    assert report["comparable_test_count"] == 0
    assert report["comparable_pass_rate_delta_percentage_points"] is None
    assert report["inventory_changes"] == {
        "added": ["suite::test_new"],
        "removed": ["suite::test_old"],
    }

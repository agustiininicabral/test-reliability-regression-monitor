import json

import pytest

from monitor.cli import main


def test_cli_persists_history_and_writes_all_report_formats(monkeypatch, tmp_path):
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"
    first.write_text(
        (
            '<testsuites><testsuite><testcase classname="a" name="t" '
            'time="0.1"/></testsuite></testsuites>'
        ),
        encoding="utf-8",
    )
    second.write_text(
        (
            '<testsuites><testsuite><testcase classname="a" name="t" '
            'time="0.1"><failure message="bad"/></testcase></testsuite></testsuites>'
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    database = tmp_path / "history.sqlite3"
    monkeypatch.setattr(
        "sys.argv",
        [
            "test-monitor",
            "--junit",
            str(first),
            str(second),
            "--out",
            str(out),
            "--db",
            str(database),
            "--fail-on-regression",
        ],
    )

    assert main() == 1
    report = json.loads((out / "reliability-report.json").read_text(encoding="utf-8"))
    assert report["newly_failing_tests"][0]["test"] == "a::t"
    assert len(report["runs"]) == 2
    assert (out / "reliability-report.md").is_file()
    html_report = (out / "reliability-report.html").read_text(encoding="utf-8")
    assert "Pass-rate trend" in html_report
    assert "<svg" in html_report
    assert database.is_file()


def test_cli_returns_zero_without_regression(monkeypatch, tmp_path):
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"
    passing_xml = (
        '<testsuites><testsuite><testcase classname="api" name="test_ok" '
        'time="0.1"/></testsuite></testsuites>'
    )
    first.write_text(passing_xml, encoding="utf-8")
    second.write_text(passing_xml, encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "test-monitor",
            "--junit",
            str(first),
            str(second),
            "--db",
            str(tmp_path / "history.sqlite3"),
            "--out",
            str(tmp_path / "out"),
            "--fail-on-regression",
        ],
    )
    assert main() == 0


def test_cli_rejects_missing_report(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        ["test-monitor", "--junit", str(tmp_path / "missing.xml")],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_cli_reports_malformed_junit_without_traceback(monkeypatch, tmp_path, capsys):
    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<testsuites><testsuite>", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["test-monitor", "--junit", str(malformed), "--db", str(tmp_path / "history.sqlite3")],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    assert "Unable to process JUnit file" in capsys.readouterr().err

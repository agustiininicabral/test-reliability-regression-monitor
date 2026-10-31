import xml.etree.ElementTree as ET

import pytest

from monitor.analyzer import (
    analyze_history,
    parse_junit,
    render_html,
    render_markdown,
    summarize,
    write_report,
)


def test_parse_junit_classifies_pass_fail_skip(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        """<testsuites><testsuite>
        <testcase classname="sample" name="ok" time="0.1" />
        <testcase classname="sample" name="bad" time="0.2">
          <failure message="assertion failed" />
        </testcase>
        <testcase classname="sample" name="later" time="0.0">
          <skipped />
        </testcase>
        </testsuite></testsuites>""",
        encoding="utf-8",
    )
    records = parse_junit(report)
    assert [item["status"] for item in records] == ["passed", "failed", "skipped"]
    assert records[1]["message"] == "assertion failed"


def test_parse_junit_supports_namespaces_and_failure_text(tmp_path):
    report = tmp_path / "namespaced.xml"
    report.write_text(
        """<j:testsuites xmlns:j="urn:junit">
        <j:testsuite>
          <j:testcase classname="api" name="test_error" time="0.2">
            <j:failure>assertion details</j:failure>
          </j:testcase>
          <j:testcase classname="api" name="test_ok" time="0.1" />
        </j:testsuite>
        </j:testsuites>""",
        encoding="utf-8",
    )

    records = parse_junit(report)

    assert [record["status"] for record in records] == ["failed", "passed"]
    assert records[0]["message"] == "assertion details"


def test_parse_junit_classifies_errors(tmp_path):
    report = tmp_path / "error.xml"
    report.write_text(
        '<testsuites><testsuite><testcase classname="api" name="test_error">'
        '<error message="unexpected exception"/></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    records = parse_junit(report)
    assert records[0]["status"] == "failed"
    assert records[0]["message"] == "unexpected exception"


def test_parse_junit_rejects_invalid_durations(tmp_path):
    for value in ("-0.1", "nan", "inf", "-inf", "not-a-number"):
        report = tmp_path / "invalid-duration.xml"
        report.write_text(
            f'<testsuites><testsuite><testcase classname="api" name="bad" time="{value}"/>'
            "</testsuite></testsuites>",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="[Dd]uration"):
            parse_junit(report)


def test_parse_junit_rejects_malformed_xml(tmp_path):
    report = tmp_path / "malformed.xml"
    report.write_text("<testsuites><testsuite>", encoding="utf-8")

    with pytest.raises(ET.ParseError):
        parse_junit(report)


def test_summary_calculates_pass_rate_and_duration():
    records = [
        {"status": "passed", "duration": 0.2},
        {"status": "failed", "duration": 0.4},
        {"status": "skipped", "duration": 0.0},
    ]
    result = summarize(records)
    assert result["total"] == 3
    assert result["pass_rate"] == 33.33
    assert result["duration_total"] == 0.6


def test_detects_flaky_candidate_and_new_failure():
    first = [
        {
            "classname": "suite",
            "name": "stable",
            "status": "passed",
            "duration": 0.1,
            "message": "",
        },
        {
            "classname": "suite",
            "name": "flaky",
            "status": "passed",
            "duration": 0.1,
            "message": "",
        },
    ]
    second = [
        {
            "classname": "suite",
            "name": "stable",
            "status": "failed",
            "duration": 0.1,
            "message": "x",
        },
        {
            "classname": "suite",
            "name": "flaky",
            "status": "failed",
            "duration": 0.1,
            "message": "x",
        },
    ]
    report = analyze_history([first, second])
    assert len(report["flaky_tests"]) == 2
    assert len(report["newly_failing_tests"]) == 2
    assert report["pass_rate_delta_percentage_points"] == -100.0


def test_stable_history_has_no_flaky_or_new_failures():
    record = {
        "classname": "suite",
        "name": "test_stable",
        "status": "passed",
        "duration": 0.1,
        "message": "",
    }
    report = analyze_history([[record], [record.copy()]])
    assert report["flaky_tests"] == []
    assert report["newly_failing_tests"] == []
    assert report["pass_rate_delta_percentage_points"] == 0.0


def test_empty_history_is_safe():
    report = analyze_history([])
    assert report["current"] is None
    assert report["flaky_tests"] == []


def test_empty_report_formats_and_files_are_valid(tmp_path):
    report = analyze_history([])
    markdown = render_markdown(report)
    html_report = render_html(report)
    assert "No flaky candidates" in markdown
    assert "No runs stored yet" in html_report
    assert "None detected" in html_report

    paths = write_report(report, tmp_path / "reports")
    assert len(paths) == 3
    assert all(path.is_file() for path in paths)

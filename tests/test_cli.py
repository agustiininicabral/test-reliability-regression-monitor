import json

from monitor.cli import main


def test_cli_writes_json_and_markdown(monkeypatch, tmp_path):
    first = tmp_path / "first.xml"
    second = tmp_path / "second.xml"
    first.write_text(
        '<testsuites><testsuite><testcase classname="a" name="t" time="0.1"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    second.write_text(
        '<testsuites><testsuite><testcase classname="a" name="t" time="0.1"><failure message="bad"/></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    out = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        ["test-monitor", "--junit", str(first), str(second), "--out", str(out), "--fail-on-regression"],
    )
    assert main() == 1
    report = json.loads((out / "reliability-report.json").read_text(encoding="utf-8"))
    assert report["newly_failing_tests"][0]["test"] == "a::t"
    assert (out / "reliability-report.md").is_file()

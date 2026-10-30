from __future__ import annotations

import html
import json
import statistics
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_junit(path: str | Path) -> list[dict[str, Any]]:
    """Parse a JUnit XML file into normalized test case records."""
    root = ET.parse(path).getroot()
    records: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        status = (
            "failed"
            if failure is not None or error is not None
            else "skipped"
            if skipped is not None
            else "passed"
        )
        records.append(
            {
                "name": case.get("name", "unknown"),
                "classname": case.get("classname", ""),
                "duration": float(case.get("time", "0") or 0),
                "status": status,
                "message": (
                    (failure.get("message") if failure is not None else None)
                    or (error.get("message") if error is not None else None)
                    or ""
                ),
            }
        )
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("passed", "failed", "skipped")
    }
    durations = [record["duration"] for record in records]
    return {
        "total": total,
        **counts,
        "pass_rate": round(counts["passed"] / total * 100, 2) if total else 0.0,
        "duration_total": round(sum(durations), 4),
        "duration_median": round(statistics.median(durations), 4) if durations else 0.0,
    }


def analyze_history(history: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Compare ordered runs and flag tests that fail in the latest run after a prior pass."""
    flattened: dict[str, list[str]] = defaultdict(list)
    previous_statuses: dict[str, list[str]] = defaultdict(list)
    latest_statuses: dict[str, list[str]] = defaultdict(list)
    run_summaries = []

    for index, run in enumerate(history, start=1):
        run_summaries.append({"run": index, **summarize(run)})
        for record in run:
            key = f"{record['classname']}::{record['name']}"
            flattened[key].append(record["status"])
            if index == len(history):
                latest_statuses[key].append(record["status"])
            else:
                previous_statuses[key].append(record["status"])

    flaky = []
    newly_failing = []
    for test_name, statuses in flattened.items():
        if "passed" in statuses and "failed" in statuses:
            flaky.append({"test": test_name, "statuses": statuses})
        # A test must be present and failing in the actual latest run. Its last
        # observed result in an older run is not evidence of a current failure.
        if "failed" in latest_statuses.get(test_name, []) and "passed" in previous_statuses.get(
            test_name, []
        ):
            newly_failing.append({"test": test_name, "statuses": statuses})

    previous = run_summaries[-2] if len(run_summaries) >= 2 else None
    current = run_summaries[-1] if run_summaries else None
    pass_rate_delta = (
        round(current["pass_rate"] - previous["pass_rate"], 2) if previous and current else None
    )

    inventory_changes = {"added": [], "removed": []}
    comparable_test_count = 0
    comparable_pass_rate_delta = None
    if len(history) >= 2:
        previous_records = {
            f"{record['classname']}::{record['name']}": record for record in history[-2]
        }
        latest_records = {
            f"{record['classname']}::{record['name']}": record for record in history[-1]
        }
        previous_names = set(previous_records)
        latest_names = set(latest_records)
        inventory_changes = {
            "added": sorted(latest_names - previous_names),
            "removed": sorted(previous_names - latest_names),
        }
        common_names = previous_names & latest_names
        comparable_test_count = len(common_names)
        if common_names:
            previous_rate = (
                sum(previous_records[name]["status"] == "passed" for name in common_names)
                / comparable_test_count
                * 100
            )
            latest_rate = (
                sum(latest_records[name]["status"] == "passed" for name in common_names)
                / comparable_test_count
                * 100
            )
            comparable_pass_rate_delta = round(latest_rate - previous_rate, 2)

    return {
        "runs": run_summaries,
        "flaky_tests": flaky,
        "newly_failing_tests": newly_failing,
        "pass_rate_delta_percentage_points": pass_rate_delta,
        "inventory_changes": inventory_changes,
        "comparable_test_count": comparable_test_count,
        "comparable_pass_rate_delta_percentage_points": comparable_pass_rate_delta,
        "current": current,
        "previous": previous,
    }


def render_markdown(report: dict[str, Any]) -> str:
    current = report["current"] or {}
    lines = [
        "# Test Reliability Report",
        "",
        f"- Latest run: **{current.get('run', 'n/a')}**",
        f"- Total tests: **{current.get('total', 0)}**",
        f"- Passed: **{current.get('passed', 0)}**",
        f"- Failed: **{current.get('failed', 0)}**",
        f"- Skipped: **{current.get('skipped', 0)}**",
        f"- Pass rate: **{current.get('pass_rate', 0)}%**",
        f"- Pass-rate change (all tests): "
        f"**{report['pass_rate_delta_percentage_points']} percentage points**",
        f"- Pass-rate change (common tests): "
        f"**{report['comparable_pass_rate_delta_percentage_points']} percentage points**",
        f"- Comparable tests: **{report['comparable_test_count']}**",
        "",
        "## Test inventory changes",
        "",
    ]
    if report["inventory_changes"]["added"]:
        lines.extend(f"- Added: `{name}`" for name in report["inventory_changes"]["added"])
    if report["inventory_changes"]["removed"]:
        lines.extend(f"- Removed: `{name}`" for name in report["inventory_changes"]["removed"])
    if not any(report["inventory_changes"].values()):
        lines.append("No test inventory changes between the latest two runs.")
    lines.extend(
        [
            "",
            "## Run history",
            "",
            "| Run | Total | Passed | Failed | Skipped | Pass rate | Duration (s) |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for run in report["runs"]:
        lines.append(
            f"| {run['run']} | {run['total']} | {run['passed']} | {run['failed']} | "
            f"{run['skipped']} | {run['pass_rate']}% | {run['duration_total']} |"
        )
    lines.extend(["", "## Flaky test candidates"])
    if report["flaky_tests"]:
        lines.extend(
            f"- `{item['test']}`: {', '.join(item['statuses'])}" for item in report["flaky_tests"]
        )
    else:
        lines.append("No flaky candidates detected in the supplied history.")
    lines.extend(["", "## Newly failing tests"])
    if report["newly_failing_tests"]:
        lines.extend(f"- `{item['test']}`" for item in report["newly_failing_tests"])
    else:
        lines.append("No newly failing tests detected.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "A flaky candidate has both passed and failed across supplied runs. "
            "A newly failing test must be present and fail in the latest run after passing "
            "in at least one earlier run. These are diagnostic heuristics, not proof of "
            "nondeterminism or root cause.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    runs = report["runs"]
    rows = []
    bars = []
    for index, run in enumerate(runs):
        rows.append(
            "<tr>"
            f"<td>{run['run']}</td><td>{run['total']}</td><td>{run['passed']}</td>"
            f"<td>{run['failed']}</td><td>{run['skipped']}</td>"
            f"<td>{run['pass_rate']:.2f}%</td><td>{run['duration_total']:.4f}</td>"
            "</tr>"
        )
        x = 54 + index * 78
        height = max(1, run["pass_rate"])
        y = 150 - height
        bars.append(
            f'<rect x="{x}" y="{y:.2f}" width="42" height="{height:.2f}" rx="3">'
            f"<title>Run {run['run']}: {run['pass_rate']:.2f}% pass rate</title></rect>"
        )
        bars.append(f'<text x="{x + 21}" y="170" text-anchor="middle">R{run["run"]}</text>')

    flaky_items = (
        "".join(
            f"<li><code>{html.escape(item['test'])}</code></li>" for item in report["flaky_tests"]
        )
        or "<li>None detected</li>"
    )
    failing_items = (
        "".join(
            f"<li><code>{html.escape(item['test'])}</code></li>"
            for item in report["newly_failing_tests"]
        )
        or "<li>None detected</li>"
    )
    table_rows = "".join(rows) or '<tr><td colspan="7">No runs stored yet</td></tr>'
    current = report["current"] or {}
    svg_width = max(560, 110 + len(runs) * 78)
    axis_end = max(520, 90 + len(runs) * 78)
    styles = """
body { font: 16px/1.5 system-ui, sans-serif; max-width: 1050px;
       margin: 2rem auto; padding: 0 1rem; color: #202124; }
h1, h2 { line-height: 1.2; }
.metrics { display: flex; flex-wrap: wrap; gap: 1rem; }
.metrics div { border: 1px solid #ddd; border-radius: 8px;
               padding: .8rem 1rem; min-width: 110px; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ddd; padding: .55rem; text-align: left; }
svg { width: 100%; max-width: 650px; height: auto;
      border: 1px solid #ddd; border-radius: 8px; }
rect { fill: #3478c8; }
text { font: 12px system-ui, sans-serif; fill: #202124; }
"""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Test Reliability Report</title>\n"
        f"<style>{styles}</style>\n</head>\n<body>\n"
        "<h1>Test Reliability Report</h1>\n"
        '<section class="metrics">\n'
        f"<div><strong>Latest pass rate</strong><br>{current.get('pass_rate', 0)}%</div>\n"
        f"<div><strong>Total tests</strong><br>{current.get('total', 0)}</div>\n"
        f"<div><strong>Failed</strong><br>{current.get('failed', 0)}</div>\n"
        "<div><strong>Pass-rate change (all)</strong><br>\n"
        f"{report['pass_rate_delta_percentage_points']}</div>\n"
        "<div><strong>Pass-rate change (common)</strong><br>\n"
        f"{report['comparable_pass_rate_delta_percentage_points']}</div>\n"
        f"<div><strong>Comparable tests</strong><br>{report['comparable_test_count']}</div>\n"
        "</section>\n<h2>Test inventory changes</h2>\n"
        f"<p>Added: {len(report['inventory_changes']['added'])} · "
        f"Removed: {len(report['inventory_changes']['removed'])}</p>\n"
        "<h2>Pass-rate trend</h2>\n"
        f'<svg viewBox="0 0 {svg_width} 190" role="img" '
        'aria-label="Pass rate by historical run">\n'
        f'<line x1="40" y1="150" x2="{axis_end}" y2="150" stroke="#777"/>\n'
        f'<line x1="40" y1="50" x2="{axis_end}" y2="50" '
        'stroke="#aaa" stroke-dasharray="4 4"/>\n'
        '<text x="5" y="54">100%</text><text x="12" y="154">0%</text>\n'
        f"{''.join(bars)}\n</svg>\n"
        "<h2>Historical runs</h2>\n"
        "<table><thead><tr><th>Run</th><th>Total</th><th>Passed</th>"
        "<th>Failed</th><th>Skipped</th><th>Pass rate</th><th>Duration (s)</th>"
        "</tr></thead>\n"
        f"<tbody>{table_rows}</tbody></table>\n"
        f"<h2>Flaky test candidates</h2><ul>{flaky_items}</ul>\n"
        f"<h2>Newly failing tests</h2><ul>{failing_items}</ul>\n"
        "<p>Flaky status is a heuristic: mixed pass/fail outcomes do not prove "
        "nondeterminism.</p>\n</body>\n</html>\n"
    )


def write_report(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "reliability-report.json"
    markdown_path = destination / "reliability-report.md"
    html_path = destination / "reliability-report.html"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return json_path, markdown_path, html_path

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
    """Compare ordered test runs (oldest to newest) and flag failures after prior passes."""
    flattened: dict[str, list[str]] = defaultdict(list)
    run_summaries = []
    for index, run in enumerate(history, start=1):
        run_summaries.append({"run": index, **summarize(run)})
        for record in run:
            key = f"{record['classname']}::{record['name']}"
            flattened[key].append(record["status"])

    flaky = []
    newly_failing = []
    for test_name, statuses in flattened.items():
        if "passed" in statuses and "failed" in statuses:
            flaky.append({"test": test_name, "statuses": statuses})
        if len(statuses) >= 2 and statuses[-1] == "failed" and "passed" in statuses[:-1]:
            newly_failing.append({"test": test_name, "statuses": statuses})

    previous = run_summaries[-2] if len(run_summaries) >= 2 else None
    current = run_summaries[-1] if run_summaries else None
    pass_rate_delta = (
        round(current["pass_rate"] - previous["pass_rate"], 2) if previous and current else None
    )
    return {
        "runs": run_summaries,
        "flaky_tests": flaky,
        "newly_failing_tests": newly_failing,
        "pass_rate_delta_percentage_points": pass_rate_delta,
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
        f"- Pass-rate change: **{report['pass_rate_delta_percentage_points']} percentage points**",
        "",
        "## Run history",
        "",
        "| Run | Total | Passed | Failed | Skipped | Pass rate | Duration (s) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
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
            "This heuristic is not proof of nondeterminism; environment changes, "
            "test data, and real regressions can produce the same pattern.",
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
            f'<rect x="{x}" y="{y:.2f}" width="42" height="{height:.2f}" '
            f'rx="3"><title>Run {run["run"]}: {run["pass_rate"]:.2f}% pass rate</title></rect>'
        )
        bars.append(
            f'<text x="{x + 21}" y="170" text-anchor="middle">R{run["run"]}</text>'
        )

    flaky_items = "".join(
        f"<li><code>{html.escape(item['test'])}</code></li>" for item in report["flaky_tests"]
    ) or "<li>None detected</li>"
    failing_items = "".join(
        f"<li><code>{html.escape(item['test'])}</code></li>"
        for item in report["newly_failing_tests"]
    ) or "<li>None detected</li>"
    table_rows = "".join(rows) or '<tr><td colspan="7">No runs stored yet</td></tr>'
    current = report["current"] or {}
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test Reliability Report</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#202124}}
h1,h2{{line-height:1.2}} .metrics{{display:flex;flex-wrap:wrap;gap:1rem}}
.metrics div{{border:1px solid #ddd;border-radius:8px;padding:.8rem 1rem;min-width:110px}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}} th,td{{border:1px solid #ddd;padding:.55rem;text-align:left}}
svg{{width:100%;max-width:650px;height:auto;border:1px solid #ddd;border-radius:8px}}
rect{{fill:#3478c8}} text{{font:12px system-ui,sans-serif;fill:#202124}}
</style>
</head>
<body>
<h1>Test Reliability Report</h1>
<section class="metrics">
<div><strong>Latest pass rate</strong><br>{current.get("pass_rate", 0)}%</div>
<div><strong>Total tests</strong><br>{current.get("total", 0)}</div>
<div><strong>Failed</strong><br>{current.get("failed", 0)}</div>
<div><strong>Pass-rate change</strong><br>{report["pass_rate_delta_percentage_points"]}</div>
</section>
<h2>Pass-rate trend</h2>
<svg viewBox="0 0 {max(560, 110 + len(runs) * 78)} 190" role="img" aria-label="Pass rate by historical run">
<line x1="40" y1="150" x2="{max(520, 90 + len(runs) * 78)}" y2="150" stroke="#777"/>
<line x1="40" y1="50" x2="{max(520, 90 + len(runs) * 78)}" y2="50" stroke="#aaa" stroke-dasharray="4 4"/>
<text x="5" y="54">100%</text><text x="12" y="154">0%</text>
{"".join(bars)}
</svg>
<h2>Historical runs</h2>
<table><thead><tr><th>Run</th><th>Total</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Pass rate</th><th>Duration (s)</th></tr></thead>
<tbody>{table_rows}</tbody></table>
<h2>Flaky test candidates</h2><ul>{flaky_items}</ul>
<h2>Newly failing tests</h2><ul>{failing_items}</ul>
<p>Flaky status is a heuristic: mixed pass/fail outcomes do not prove nondeterminism.</p>
</body></html>
"""


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

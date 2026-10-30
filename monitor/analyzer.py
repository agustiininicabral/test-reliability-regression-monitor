from __future__ import annotations

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
        status = "failed" if failure is not None or error is not None else (
            "skipped" if skipped is not None else "passed"
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
            key = f'{record["classname"]}::{record["name"]}'
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
        round(current["pass_rate"] - previous["pass_rate"], 2)
        if previous and current
        else None
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
        f'- Latest run: **{current.get("run", "n/a")}**',
        f'- Total tests: **{current.get("total", 0)}**',
        f'- Passed: **{current.get("passed", 0)}**',
        f'- Failed: **{current.get("failed", 0)}**',
        f'- Skipped: **{current.get("skipped", 0)}**',
        f'- Pass rate: **{current.get("pass_rate", 0)}%**',
        "",
        "## Flaky test candidates",
    ]
    if report["flaky_tests"]:
        lines.extend(f'- `{item["test"]}`: {", ".join(item["statuses"])}' for item in report["flaky_tests"])
    else:
        lines.append("No flaky candidates detected in the supplied history.")
    lines.extend(["", "## Newly failing tests"])
    if report["newly_failing_tests"]:
        lines.extend(f'- `{item["test"]}`' for item in report["newly_failing_tests"])
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


def write_report(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "reliability-report.json"
    markdown_path = destination / "reliability-report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path

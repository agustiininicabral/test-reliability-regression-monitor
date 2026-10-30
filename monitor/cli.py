from __future__ import annotations

import argparse
import sys
from pathlib import Path

from monitor.analyzer import analyze_history, parse_junit, write_report
from monitor.storage import load_history, save_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Store and analyze JUnit XML history (input files oldest first)."
    )
    parser.add_argument("--junit", nargs="+", required=True, help="JUnit XML files, oldest first")
    parser.add_argument("--out", default="reports/latest", help="Output directory")
    parser.add_argument(
        "--db",
        default="reports/history.sqlite3",
        help="SQLite history database (default: reports/history.sqlite3)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Return exit code 1 if the comparable latest pass rate drops",
    )
    args = parser.parse_args()

    paths = [Path(item) for item in args.junit]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        parser.error(f"JUnit file(s) not found: {', '.join(missing)}")

    for path in paths:
        records = parse_junit(path)
        inserted = save_run(args.db, str(path), records, path.read_bytes())
        state = "stored" if inserted else "already stored"
        print(f"{path}: {state}")

    history = load_history(args.db)
    report = analyze_history(history)
    report["database"] = str(args.db)
    json_path, markdown_path, html_path = write_report(report, args.out)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    print(f"HTML report: {html_path}")

    delta = report["comparable_pass_rate_delta_percentage_points"]
    comparison = "common tests"
    if delta is None:
        delta = report["pass_rate_delta_percentage_points"]
        comparison = "all tests (no shared test inventory)"

    if args.fail_on_regression and delta is not None and delta < 0:
        message = (
            f"Regression detected: pass rate for {comparison} changed by {delta} percentage points."
        )
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

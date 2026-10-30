from __future__ import annotations

import argparse
import sys
from pathlib import Path

from monitor.analyzer import analyze_history, parse_junit, write_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze one or more JUnit XML reports (oldest run first)."
    )
    parser.add_argument("--junit", nargs="+", required=True, help="JUnit XML files, oldest first")
    parser.add_argument("--out", default="reports/latest", help="Output directory")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Return exit code 1 if latest pass rate is lower than previous run",
    )
    args = parser.parse_args()

    paths = [Path(item) for item in args.junit]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        parser.error(f"JUnit file(s) not found: {', '.join(missing)}")

    history = [parse_junit(path) for path in paths]
    report = analyze_history(history)
    json_path, markdown_path = write_report(report, args.out)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")

    delta = report["pass_rate_delta_percentage_points"]
    if args.fail_on_regression and delta is not None and delta < 0:
        message = f"Regression detected: pass rate changed by {delta} percentage points."
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

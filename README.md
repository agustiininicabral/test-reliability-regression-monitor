# Test Reliability & Regression Monitor

A Python CLI that analyzes historical **JUnit XML** test reports to identify flaky-test candidates, newly failing tests, pass-rate movement, and execution-time summaries.

## Capabilities

- Parse JUnit XML produced by Pytest or compatible test runners.
- Normalize passed, failed, and skipped outcomes.
- Calculate pass rate, total duration, and median test duration.
- Compare multiple runs ordered oldest to newest.
- Flag tests that passed and failed across the supplied history.
- Flag tests that were previously passing and fail in the latest run.
- Generate machine-readable JSON and human-readable Markdown.
- Optional non-zero exit code when the latest pass rate drops.

## Install (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip check
ruff check monitor tests
ruff format --check monitor tests
pytest -v
```

## Generate a report

```powershell
python -m monitor.cli --junit examples/run-1.xml examples/run-2.xml --out reports/demo
```

Fail the command when the latest pass rate is lower than the previous run:

```powershell
python -m monitor.cli --junit examples/run-1.xml examples/run-2.xml --out reports/gate --fail-on-regression
```

The supplied example intentionally includes a regression, so the second command returns exit code `1`.

## Input format

Provide one or more JUnit XML files. Order matters: **oldest run first, newest run last**.

```powershell
pytest --junitxml=reports/current.xml
python -m monitor.cli --junit reports/history-1.xml reports/history-2.xml reports/current.xml --out reports/analysis
```

## CI

GitHub Actions runs the unit tests, Ruff, dependency checks, and a deterministic report-generation demo on pushes and pull requests. JSON and Markdown reports are uploaded as a workflow artifact for 14 days.

## How flaky candidates are defined

A test is flagged as a flaky candidate when its supplied history contains at least one pass and at least one failure. This is a heuristic, not proof of nondeterminism. A genuine code regression, environment instability, test-data collision, or dependency issue can produce the same pattern. Investigate logs and rerun under controlled conditions before classifying a test as flaky.

## Limitations

- The tool analyzes reports; it does not execute tests itself.
- Runs must be supplied in chronological order.
- JUnit XML variations outside the common `testsuite(s)/testcase` structure may require parser extensions.
- The sample XML files are synthetic demonstration data, not real production test evidence.
- Pass-rate regression compares the latest two run summaries; it does not normalize for changing test inventories.

## License

MIT.

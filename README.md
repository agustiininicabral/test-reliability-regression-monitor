# Test Reliability & Regression Monitor

A Python CLI that stores historical **JUnit XML** test results in SQLite and analyzes reliability trends. It identifies flaky-test candidates, newly failing tests, pass-rate changes, and execution-time metrics, then generates JSON, Markdown, and self-contained HTML reports with an SVG trend chart.

## Capabilities

- Parse JUnit XML produced by Pytest and compatible test runners.
- Store run summaries and individual test outcomes in a local SQLite database.
- Avoid importing the same source file and content more than once.
- Compare runs in chronological insertion order.
- Calculate passed, failed, skipped, pass rate, total duration, and median duration.
- Flag tests that passed and failed across supplied history.
- Identify tests that previously passed and fail in the latest run.
- Generate JSON, Markdown, and HTML reports, including a pass-rate chart.
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

## Analyze reports

Pass one or more JUnit XML files, ordered oldest to newest:

```powershell
python -m monitor.cli --junit examples/run-1.xml examples/run-2.xml --out reports/demo
```

The command stores the reports in `reports/history.sqlite3` by default and generates:

- `reports/demo/reliability-report.json`
- `reports/demo/reliability-report.md`
- `reports/demo/reliability-report.html`

Open the HTML file in a browser to view the historical pass-rate chart and test summaries.

Specify a different database with `--db`:

```powershell
python -m monitor.cli --junit reports/current.xml --db reports/team-history.sqlite3 --out reports/latest
```

The database is persistent across executions. New report files are appended to the history; the same source file with unchanged content is not imported twice. Keep the input files in chronological order when importing historical batches.

Fail the command when the latest pass rate is lower than the previous run:

```powershell
python -m monitor.cli --junit reports/current.xml --fail-on-regression
```

## Flaky-test interpretation

A test is flagged as a flaky candidate when its supplied history contains at least one pass and at least one failure. This is a heuristic, not proof of nondeterminism. A genuine code regression, environment instability, test-data collision, or dependency issue can produce the same pattern. Investigate logs and rerun under controlled conditions before classifying a test as flaky.

## CI

GitHub Actions runs tests, Ruff, dependency checks, and a deterministic historical-report demo. JUnit results, the SQLite database, and generated JSON/Markdown/HTML reports are uploaded as a workflow artifact for 14 days.

## Limitations

- The tool analyzes reports; it does not execute tests itself.
- Runs are ordered by database insertion time; import historical batches oldest first.
- Re-importing the same path and identical file content is ignored.
- JUnit XML variations outside the common `testsuite(s)/testcase` structure may require parser extensions.
- The sample XML files are synthetic demonstration data, not production test evidence.
- Pass-rate regression compares the latest two stored run summaries; it does not normalize for changing test inventories.

## License

MIT.

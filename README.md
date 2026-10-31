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
- Enforce a minimum 85% test coverage gate.
- Optional non-zero exit code when the comparable pass rate drops (falling back to the overall rate when no tests are shared between the latest runs).

## Install (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip check
ruff check monitor tests
ruff format --check monitor tests
pytest -v --cov=monitor --cov-report=term-missing
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

The database is persistent across local executions. New report files are appended to the history; the same source file with unchanged content is not imported twice. Keep input files in chronological order when importing historical batches.

## CI history

GitHub Actions restores and updates a SQLite history database through the Actions cache on the main branch. Each workflow execution adds its current JUnit result to the history, compares it with previous runs, and uploads the database and generated reports as a 14-day artifact. GitHub cache entries can expire when unused, so download the artifact if you need a durable archive outside the cache lifecycle.


## End-to-end integration with Quality Gates

The `quality-gates-integration.yml` workflow checks out the companion
[`continuous-testing-quality-gates`](https://github.com/agustiininicabral/continuous-testing-quality-gates)
repository, installs both projects, runs the API project's complete pytest suite,
and writes its JUnit XML and coverage evidence. The monitor imports that JUnit
report into a dedicated SQLite history, compares it with prior runs, and
generates JSON, Markdown, and HTML reliability reports.

The integration workflow runs on pushes and pull requests to this repository,
on manual dispatch, and daily. It retains history through the GitHub Actions
cache and uploads evidence as a 14-day artifact. The cache is an operational
convenience, not permanent storage; download the artifact for durable records.
Pull-request runs do not update the shared history cache.

On the first successful run, there is no prior Quality Gates run to compare.
Regression detection becomes meaningful after at least two distinct runs have
been recorded. A lower comparable pass rate fails the integration workflow.
Investigate the failing test and its logs before attributing a root cause.

To run the same flow locally from the monitor repository root:

```powershell
python -m pip install -e ".[dev]"
git clone https://github.com/agustiininicabral/continuous-testing-quality-gates.git quality-gates
python -m pip install -e "quality-gates[dev]"
New-Item -ItemType Directory -Force reports | Out-Null
Push-Location quality-gates
pytest --cov=src --cov-report=term-missing --junitxml=../reports/quality-gates-local.xml
Pop-Location
python -m monitor.cli --junit reports/quality-gates-local.xml --db reports/quality-gates-history.sqlite3 --out reports/quality-gates-integration
```

The companion API is an in-memory testing demo. This integration validates its
automated test suite; it does not deploy the API as a production service.


## Flaky-test interpretation

A test is flagged as a flaky candidate when its supplied history contains at least one pass and at least one failure. This is a heuristic, not proof of nondeterminism. A genuine code regression, environment instability, test-data collision, or dependency issue can produce the same pattern. Investigate logs and rerun under controlled conditions before classifying a test as flaky.

## CI

GitHub Actions runs tests with an 85% coverage gate, Ruff, dependency checks, and a historical-report demo. JUnit results, coverage XML, the SQLite database, and generated JSON/Markdown/HTML reports are uploaded as a workflow artifact for 14 days.

## Security and maintenance

- GitHub Actions runs with read-only repository contents permissions.
- CodeQL analyzes the Python code on pushes, pull requests, and a weekly schedule.
- Dependabot checks Python dependencies and GitHub Actions updates weekly.
- CI validates Python 3.11 and 3.12 on Ubuntu and Windows.

## Limitations

- The tool analyzes reports; it does not execute tests itself.
- Runs are ordered by database insertion time; import historical batches oldest first.
- Re-importing the same path and identical file content is ignored.
- JUnit XML variations outside the common `testsuite(s)/testcase` structure may require parser extensions.
- The sample XML files are synthetic demonstration data, not production test evidence.
- Pass-rate reporting includes both the overall change and a comparable change calculated only from tests present in both of the latest two runs. Added and removed tests are reported separately. If there are no shared tests, the comparable delta is unavailable; `--fail-on-regression` falls back to the overall delta.

## License

MIT.

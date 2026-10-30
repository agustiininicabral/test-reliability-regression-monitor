from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def _connect(database: str | Path) -> sqlite3.Connection:
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database: str | Path) -> None:
    with closing(_connect(database)) as connection:
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    total INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    skipped INTEGER NOT NULL,
                    duration_total REAL NOT NULL,
                    UNIQUE(source, fingerprint)
                );

                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
                    classname TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('passed', 'failed', 'skipped')),
                    duration REAL NOT NULL,
                    message TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_test_results_name
                    ON test_results(classname, name);
                CREATE INDEX IF NOT EXISTS idx_test_results_run
                    ON test_results(run_id);
                """
            )


def save_run(
    database: str | Path,
    source: str,
    records: list[dict[str, Any]],
    raw_xml: bytes,
) -> bool:
    """Persist a JUnit run; return False when the same source/content was imported before."""
    initialize_database(database)
    fingerprint = hashlib.sha256(raw_xml).hexdigest()
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("passed", "failed", "skipped")
    }
    duration_total = sum(float(record["duration"]) for record in records)

    with closing(_connect(database)) as connection:
        with connection:
            existing = connection.execute(
                "SELECT id FROM test_runs WHERE source = ? AND fingerprint = ?",
                (source, fingerprint),
            ).fetchone()
            if existing:
                return False

            cursor = connection.execute(
                """
                INSERT INTO test_runs
                    (source, fingerprint, total, passed, failed, skipped, duration_total)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    fingerprint,
                    len(records),
                    counts["passed"],
                    counts["failed"],
                    counts["skipped"],
                    duration_total,
                ),
            )
            run_id = cursor.lastrowid
            connection.executemany(
                """
                INSERT INTO test_results (run_id, classname, name, status, duration, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        record["classname"],
                        record["name"],
                        record["status"],
                        float(record["duration"]),
                        record.get("message", ""),
                    )
                    for record in records
                ],
            )
    return True


def load_history(database: str | Path) -> list[list[dict[str, Any]]]:
    """Load persisted test runs in their insertion order, oldest first."""
    initialize_database(database)
    history: list[list[dict[str, Any]]] = []
    with closing(_connect(database)) as connection:
        runs = connection.execute("SELECT id FROM test_runs ORDER BY id").fetchall()
        for run in runs:
            rows = connection.execute(
                """
                SELECT classname, name, status, duration, message
                FROM test_results WHERE run_id = ? ORDER BY id
                """,
                (run["id"],),
            ).fetchall()
            history.append([dict(row) for row in rows])
    return history

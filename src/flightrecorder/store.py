"""SQLite persistence for recorded agent runs."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .redact import redact


SCHEMA_VERSION = 1


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    error TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(run_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_steps_run_sequence ON steps(run_id, sequence);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at DESC);
"""


def _json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(redact(value), sort_keys=True, default=repr)


def _decode(value: Optional[str]) -> Any:
    return None if value is None else json.loads(value)


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def create_run(
        self, run_id: str, name: str, started_at: str, metadata: Dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO runs(id, name, status, started_at, metadata_json) "
                "VALUES (?, ?, 'running', ?, ?)",
                (run_id, name, started_at, _json(metadata)),
            )

    def finish_run(self, run_id: str, status: str, finished_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
                (status, finished_at, run_id),
            )

    def update_run_metadata(self, run_id: str, metadata: Dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE runs SET metadata_json = ? WHERE id = ?",
                (_json(metadata), run_id),
            )

    def add_step(self, step: Dict[str, Any]) -> int:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM steps WHERE run_id = ?",
                (step["run_id"],),
            ).fetchone()
            sequence = int(row["next"])
            connection.execute(
                """INSERT INTO steps(
                    run_id, sequence, kind, name, status, started_at, finished_at,
                    input_json, output_json, error, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step["run_id"],
                    sequence,
                    step["kind"],
                    step["name"],
                    step["status"],
                    step["started_at"],
                    step["finished_at"],
                    _json(step.get("input")),
                    _json(step.get("output")),
                    redact(step.get("error")),
                    _json(step.get("metadata", {})),
                ),
            )
        return sequence

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._run(row) for row in rows]

    def get_run(self, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM runs WHERE id = ?" if run_id else (
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT 1"
        )
        params = (run_id,) if run_id else ()
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            steps = connection.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY sequence", (row["id"],)
            ).fetchall()
        result = self._run(row)
        result["steps"] = [self._step(step) for step in steps]
        return result

    def prune_runs(
        self, older_than: str, keep_latest: int = 100, dry_run: bool = True
    ) -> List[str]:
        """List or delete old runs while retaining the newest requested count."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id FROM runs
                   WHERE started_at < ?
                      OR id NOT IN (
                         SELECT id FROM runs ORDER BY started_at DESC LIMIT ?
                     )
                   ORDER BY started_at""",
                (older_than, max(keep_latest, 0)),
            ).fetchall()
            run_ids = [row["id"] for row in rows]
            if run_ids and not dry_run:
                connection.executemany(
                    "DELETE FROM runs WHERE id = ?", [(item,) for item in run_ids]
                )
        return run_ids

    @staticmethod
    def _run(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result["metadata"] = _decode(result.pop("metadata_json"))
        return result

    @staticmethod
    def _step(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result["input"] = _decode(result.pop("input_json"))
        result["output"] = _decode(result.pop("output_json"))
        result["metadata"] = _decode(result.pop("metadata_json"))
        return result


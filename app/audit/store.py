"""Audit storage.

docs/architecture/04-security-governance-and-safety.md 4.8 requires the audit record to be append-only to application
users and replayable without the original conversational state. In-memory storage
satisfies "append-only" only by convention and loses everything on restart, which is
why AR-15 was the one requirement left unmet.

Two implementations behind one protocol:

- InMemoryAuditStore keeps the default fast and hermetic for tests and replay.
- SqliteAuditStore persists to a file and enforces append-only in the database with
  triggers, so a bug or a careless operator cannot rewrite history through the same
  connection the application uses.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Protocol

from app.domain.models import AuditEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT    NOT NULL,
    run_key        TEXT    NOT NULL,
    seq            INTEGER NOT NULL,
    at             TEXT    NOT NULL,
    stage          TEXT    NOT NULL,
    actor          TEXT    NOT NULL,
    summary        TEXT    NOT NULL,
    refs           TEXT    NOT NULL,
    UNIQUE (run_key, seq)
);
CREATE INDEX IF NOT EXISTS audit_by_correlation ON audit_entries (correlation_id, id);

-- Append-only is a control, not a convention. Enforce it where the data lives.
CREATE TRIGGER IF NOT EXISTS audit_entries_no_update
BEFORE UPDATE ON audit_entries
BEGIN SELECT RAISE(ABORT, 'the audit ledger is append-only'); END;

CREATE TRIGGER IF NOT EXISTS audit_entries_no_delete
BEFORE DELETE ON audit_entries
BEGIN SELECT RAISE(ABORT, 'the audit ledger is append-only'); END;
"""


class AuditStore(Protocol):
    def append(self, correlation_id: str, run_key: str, entry: AuditEntry) -> None: ...
    def entries_for_run(self, run_key: str) -> list[AuditEntry]: ...
    def entries_for_correlation(self, correlation_id: str) -> list[AuditEntry]: ...


def _to_entry(row: tuple) -> AuditEntry:
    seq, at, stage, actor, summary, refs = row
    return AuditEntry(seq=seq, at=at, stage=stage, actor=actor, summary=summary, refs=json.loads(refs))


class InMemoryAuditStore:
    """Default. Fast, hermetic, and gone when the process ends."""

    def __init__(self) -> None:
        self._rows: list[tuple[str, str, AuditEntry]] = []

    def append(self, correlation_id: str, run_key: str, entry: AuditEntry) -> None:
        self._rows.append((correlation_id, run_key, entry))

    def entries_for_run(self, run_key: str) -> list[AuditEntry]:
        return [e for _, key, e in self._rows if key == run_key]

    def entries_for_correlation(self, correlation_id: str) -> list[AuditEntry]:
        return [e for cid, _, e in self._rows if cid == correlation_id]


class SqliteAuditStore:
    """Durable. Survives a restart and refuses updates and deletes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    def append(self, correlation_id: str, run_key: str, entry: AuditEntry) -> None:
        self._connection.execute(
            "INSERT INTO audit_entries (correlation_id, run_key, seq, at, stage, actor, summary, refs)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                correlation_id, run_key, entry.seq, entry.at.isoformat(),
                entry.stage, entry.actor, entry.summary,
                json.dumps(entry.refs),
            ),
        )
        self._connection.commit()

    # Both queries are written out in full rather than built by interpolation. The
    # column name is internal, but a query assembled with an f-string is a habit worth
    # not having in a file whose whole purpose is an audit trail.
    _SELECT_BY_RUN = (
        "SELECT seq, at, stage, actor, summary, refs FROM audit_entries "
        "WHERE run_key = ? ORDER BY id"
    )
    _SELECT_BY_CORRELATION = (
        "SELECT seq, at, stage, actor, summary, refs FROM audit_entries "
        "WHERE correlation_id = ? ORDER BY id"
    )

    def entries_for_run(self, run_key: str) -> list[AuditEntry]:
        cursor = self._connection.execute(self._SELECT_BY_RUN, (run_key,))
        return [_to_entry(row) for row in cursor.fetchall()]

    def entries_for_correlation(self, correlation_id: str) -> list[AuditEntry]:
        cursor = self._connection.execute(self._SELECT_BY_CORRELATION, (correlation_id,))
        return [_to_entry(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()


def build_store(database_path: str | None) -> AuditStore:
    """A path means durability. No path keeps the default in-memory store."""
    return SqliteAuditStore(database_path) if database_path else InMemoryAuditStore()

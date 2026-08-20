"""Durable SQLite outbox.

This package form intentionally owns the public ``yujian_edge.outbox`` import.
Keeping all connection scopes here explicit also makes cleanup deterministic on
Windows development machines and Ubuntu deployments.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from ..envelope import canonical_json, mqtt_topic
from ..transports import EventTransport


@dataclass(frozen=True)
class OutboxItem:
    event_id: str
    event_type: str
    envelope: Mapping[str, Any]
    attempt_count: int
    next_attempt_at: float
    last_error: str | None


@dataclass(frozen=True)
class FlushResult:
    attempted: int
    delivered: int
    failed: int
    remaining: int


class SQLiteOutbox:
    """Durable at-least-once outbox with explicit connection cleanup."""

    def __init__(
        self,
        path: str | Path,
        *,
        batch_size: int = 50,
        retry_base_seconds: float = 2.0,
        retry_max_seconds: float = 300.0,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS outbox (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    next_attempt_at REAL NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_due
                    ON outbox(next_attempt_at, created_at);
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def next_sequence(self) -> int:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='last_sequence'"
            ).fetchone()
            sequence = int(row["value"]) + 1 if row else 1
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES('last_sequence', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(sequence),),
            )
            return sequence

    def enqueue(self, envelope: Mapping[str, Any]) -> bool:
        now = time.time()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO outbox(
                    event_id, event_type, envelope_json, created_at,
                    next_attempt_at, attempt_count, last_error
                ) VALUES(?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    str(envelope["eventId"]),
                    str(envelope["eventType"]),
                    canonical_json(envelope),
                    now,
                    now,
                ),
            )
            return cursor.rowcount == 1

    def pending_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM outbox").fetchone()
            return int(row["count"])

    def items(self, *, force: bool = False, limit: int | None = None) -> list[OutboxItem]:
        limit = limit or self.batch_size
        condition = "1=1" if force else "next_attempt_at <= ?"
        params: tuple[Any, ...] = (limit,) if force else (time.time(), limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT event_id, event_type, envelope_json, attempt_count,
                       next_attempt_at, last_error
                FROM outbox
                WHERE {condition}
                ORDER BY created_at ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            OutboxItem(
                event_id=row["event_id"],
                event_type=row["event_type"],
                envelope=json.loads(row["envelope_json"]),
                attempt_count=int(row["attempt_count"]),
                next_attempt_at=float(row["next_attempt_at"]),
                last_error=row["last_error"],
            )
            for row in rows
        ]

    def _mark_delivered(self, event_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM outbox WHERE event_id=?", (event_id,))

    def _mark_failed(self, item: OutboxItem, error: Exception) -> None:
        attempt = item.attempt_count + 1
        exponent = min(attempt - 1, 16)
        delay = min(self.retry_max_seconds, self.retry_base_seconds * (2**exponent))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE outbox
                SET attempt_count=?, next_attempt_at=?, last_error=?
                WHERE event_id=?
                """,
                (attempt, time.time() + delay, str(error)[:1000], item.event_id),
            )

    def flush(self, transport: EventTransport, *, force: bool = False) -> FlushResult:
        attempted = delivered = failed = 0
        with self._lock:
            for item in self.items(force=force):
                attempted += 1
                try:
                    transport.send(item.envelope, mqtt_topic(item.envelope))
                except Exception as exc:
                    failed += 1
                    self._mark_failed(item, exc)
                    break
                else:
                    delivered += 1
                    self._mark_delivered(item.event_id)
        return FlushResult(attempted, delivered, failed, self.pending_count())

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS pending,
                       COALESCE(MAX(attempt_count), 0) AS max_attempts,
                       MIN(next_attempt_at) AS next_attempt_at
                FROM outbox
                """
            ).fetchone()
        return {
            "sqlitePath": str(self.path),
            "pending": int(row["pending"]),
            "maxAttempts": int(row["max_attempts"]),
            "nextAttemptAtEpoch": row["next_attempt_at"],
        }

"""SQLite-backed store of listings already seen and per-portal failure counters."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Self

from carbotfinder.models import Listing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    key         TEXT PRIMARY KEY,
    portal      TEXT NOT NULL,
    listing_id  TEXT NOT NULL,
    search      TEXT NOT NULL,
    price       INTEGER,
    first_seen  TEXT NOT NULL,
    notified    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS portal_health (
    portal               TEXT PRIMARY KEY,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error           TEXT,
    last_alert_at        TEXT
);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


class State:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- lifecycle -----------------------------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- seen listings -------------------------------------------------------------------------
    def is_empty(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) FROM seen").fetchone()
        return bool(row is None or row[0] == 0)

    def has(self, key: str) -> bool:
        return self._conn.execute("SELECT 1 FROM seen WHERE key = ?", (key,)).fetchone() is not None

    def add(
        self, listing: Listing, *, search: str, notified: bool, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        self._conn.execute(
            "INSERT OR IGNORE INTO seen"
            " (key, portal, listing_id, search, price, first_seen, notified)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                listing.key,
                listing.portal,
                listing.id,
                search,
                listing.price,
                _iso(now),
                int(notified),
            ),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM seen").fetchone()
        return int(row[0]) if row else 0

    # -- portal health -------------------------------------------------------------------------
    def record_success(self, portal: str) -> None:
        self._conn.execute(
            "INSERT INTO portal_health (portal, consecutive_failures, last_error)"
            " VALUES (?, 0, NULL)"
            " ON CONFLICT(portal) DO UPDATE SET consecutive_failures = 0, last_error = NULL",
            (portal,),
        )
        self._conn.commit()

    def record_failure(self, portal: str, error: str) -> int:
        """Increment and return the consecutive failure count for ``portal``."""
        self._conn.execute(
            "INSERT INTO portal_health (portal, consecutive_failures, last_error) VALUES (?, 1, ?)"
            " ON CONFLICT(portal) DO UPDATE SET"
            " consecutive_failures = consecutive_failures + 1, last_error = excluded.last_error",
            (portal, error[:500]),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT consecutive_failures FROM portal_health WHERE portal = ?", (portal,)
        ).fetchone()
        return int(row[0]) if row else 1

    def should_alert(
        self, portal: str, min_interval: timedelta, now: datetime | None = None
    ) -> bool:
        now = now or datetime.now(UTC)
        row = self._conn.execute(
            "SELECT last_alert_at FROM portal_health WHERE portal = ?", (portal,)
        ).fetchone()
        if row is None or row[0] is None:
            return True
        last = datetime.fromisoformat(row[0])
        return now - last >= min_interval

    def mark_alerted(self, portal: str, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        self._conn.execute(
            "UPDATE portal_health SET last_alert_at = ? WHERE portal = ?", (_iso(now), portal)
        )
        self._conn.commit()

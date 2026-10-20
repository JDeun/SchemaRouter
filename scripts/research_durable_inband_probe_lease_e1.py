"""Default-off E1: one finite shared-host SQLite lease for real in-band probes.

One operator approves the lease ONCE; each native source canary callback must
reserve a nonrefundable GET attempt BEFORE contacting the external provider.
SQLite BEGIN IMMEDIATE serializes independent processes sharing the SAME
trusted local database file. Does NOT coordinate separate hosts/databases,
auto-renew expired permission, kill in-flight requests or qualify E2.
"""
from __future__ import annotations

import inspect
import math
import sqlite3
import time
from collections.abc import Awaitable, Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from scripts.research_live_health_model_menu_e1 import GEO, WEATHER

_ROUTES = (GEO, WEATHER)
_LEASE = "open_meteo_inband_canary_e1"


def _utc_seconds() -> float:
    return time.time()


class DurableInBandProbeLeaseE1:
    """Finite trusted operator lease; no store is silently created at runtime."""

    def __init__(self, database_path: Path) -> None:
        if (
            not isinstance(database_path, Path)
            or database_path.suffix != ".sqlite3"
            or not database_path.is_absolute()
        ):
            raise ValueError("explicit absolute local SQLite lease path required")
        self._path = database_path

    def _connect_existing(self) -> sqlite3.Connection:
        # URI mode=rw: a missing or deleted lease file must NOT be recreated
        # on a background probe, including across process restarts.
        connection = sqlite3.connect(
            self._path.as_uri() + "?mode=rw",
            uri=True,
            isolation_level=None,
            timeout=1.0,
        )
        connection.execute("PRAGMA busy_timeout=1000")
        return connection

    def initialize(
        self, *,
        operator_approved: bool,
        validity_seconds: int,
        attempts_per_route: int,
    ) -> None:
        """One-time explicit lease issuance; never refresh an existing lease.

        Re-running this operation against an expired/depleted lease FAILS.
        The caller must use a separately audited fresh operator lease path;
        deleting the old DB or copying leases is outside E1's trust boundary.
        """
        if operator_approved is not True:
            raise ValueError("explicit operator authorization required")
        if type(validity_seconds) is not int or not 1 <= validity_seconds <= 3600:
            raise ValueError("finite explicit approval duration 1-3600 seconds required")
        if type(attempts_per_route) is not int or not 1 <= attempts_per_route <= 2:
            raise ValueError("finite per-route allowance 1-2 required")
        if not self._path.parent.is_dir() or self._path.is_symlink():
            raise ValueError("trusted existing lease directory and non-symlink required")
        now = _utc_seconds()
        if not math.isfinite(now):
            raise ValueError("valid wall clock required")
        # Only the explicit initialize entrypoint has permission to create
        # the file. Insecure/untrusted directory ownership is not supported.
        with closing(sqlite3.connect(
            self._path,
            timeout=1.0,
            isolation_level=None,
        )) as conn:
            conn.execute("PRAGMA busy_timeout=1000")
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS lease ("
                    "id TEXT PRIMARY KEY, issued REAL NOT NULL, "
                    "expires REAL NOT NULL, last_seen REAL NOT NULL, "
                    "per_route_cap INTEGER NOT NULL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS claims ("
                    "lease_id TEXT NOT NULL, route TEXT NOT NULL, "
                    "spent INTEGER NOT NULL,"
                    "PRIMARY KEY (lease_id, route))"
                )
                if conn.execute(
                    "SELECT 1 FROM lease WHERE id = ?", (_LEASE,),
                ).fetchone() is not None:
                    raise ValueError("existing lease cannot be renewed or replaced")
                conn.execute(
                    "INSERT INTO lease VALUES (?, ?, ?, ?, ?)",
                    (_LEASE, now, now + validity_seconds, now, attempts_per_route),
                )
                conn.executemany(
                    "INSERT INTO claims VALUES (?, ?, ?)",
                    ((_LEASE, route, 0) for route in _ROUTES),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def try_claim(self, route: str) -> bool:
        """Atomic nonrefundable reservation. All failure modes deny access."""
        if type(route) is not str or route not in _ROUTES:
            return False
        if not self._path.is_file() or self._path.is_symlink():
            return False
        try:
            with closing(self._connect_existing()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT issued, expires, last_seen, per_route_cap "
                    "FROM lease WHERE id = ?", (_LEASE,),
                ).fetchone()
                now = _utc_seconds()
                if (
                    row is None or not math.isfinite(now)
                    or now < row[0] or now < row[2] or now >= row[1]
                ):
                    conn.rollback()
                    return False
                count = conn.execute(
                    "SELECT spent FROM claims WHERE lease_id=? AND route=?",
                    (_LEASE, route),
                ).fetchone()
                if count is None or count[0] >= row[3]:
                    conn.rollback()
                    return False
                updated = conn.execute(
                    "UPDATE claims SET spent=spent+1 "
                    "WHERE lease_id=? AND route=? AND spent=?",
                    (_LEASE, route, count[0]),
                )
                if updated.rowcount != 1:
                    conn.rollback()
                    return False
                conn.execute(
                    "UPDATE lease SET last_seen=? WHERE id=?",
                    (now, _LEASE),
                )
                conn.commit()
                return True
        except (sqlite3.Error, OSError, ValueError):
            # No silent fallback to per-process counters on I/O/corruption.
            return False

    def wrap_probe(
        self, route: str, callback: Callable[[], bool | Awaitable[bool]],
    ) -> Callable[[], Awaitable[bool]]:
        if route not in _ROUTES or not callable(callback):
            raise ValueError("only known authorized native canary callbacks")
        async def capped_callback() -> bool:
            # Reserve BEFORE any business endpoint GET; even a timeout consumes
            # this allowance, preventing retries after process interruption.
            if not self.try_claim(route):
                return False
            try:
                result: Any = callback()
                if inspect.isawaitable(result):
                    result = await result
                return result is True
            except Exception:
                return False
        return capped_callback

    def public_counts(self) -> dict[str, int]:
        """Only aggregate spent counts; never disclose DB path or probe args."""
        if not self._path.is_file() or self._path.is_symlink():
            return {}
        try:
            with closing(self._connect_existing()) as conn:
                records = conn.execute(
                    "SELECT route, spent FROM claims WHERE lease_id=?",
                    (_LEASE,),
                ).fetchall()
            if {route for route, _ in records} != set(_ROUTES):
                return {}
            return {
                "geocoding": dict(records)[GEO],
                "forecast": dict(records)[WEATHER],
            }
        except (sqlite3.Error, OSError, ValueError):
            return {}

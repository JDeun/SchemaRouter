"""Default-off E1: one finite shared-host SQLite lease for real in-band probes.

One operator approves the lease ONCE; each native source canary callback must
reserve a nonrefundable GET attempt BEFORE contacting the external provider.
SQLite BEGIN IMMEDIATE serializes independent processes sharing the SAME
trusted local database file. Does NOT coordinate separate hosts/databases,
auto-renew expired permission, kill in-flight requests or qualify E2.
"""
from __future__ import annotations

import asyncio
import inspect
import math
import os
import sqlite3
import time
from collections.abc import Awaitable, Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from schemarouter import SchemaRouter
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
        # Only explicit operator initialize can create the lease file. New
        # SQLite files start owner-only; an existing lease is never replaced.
        # The parent directory/filesystem must be operator-controlled.
        try:
            fd = os.open(
                self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(fd)
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

    def approval_active(self) -> bool:
        """Read-only validity gate for already-probed model-visible routes.

        Unlike try_claim this never spends a canary GET allowance. It does
        not grant source execution authority; the canonical scoped executor
        must still validate the route and principal. Missing, revoked,
        expired, rolled-back-clock and corrupt leases all deny visibility.
        This is a same-file observation, NOT a distributed atomic fence.
        """
        if not self._path.is_file() or self._path.is_symlink():
            return False
        try:
            with closing(self._connect_existing()) as conn:
                row = conn.execute(
                    "SELECT issued, expires, last_seen FROM lease WHERE id=?",
                    (_LEASE,),
                ).fetchone()
                now = _utc_seconds()
                return bool(
                    row is not None and math.isfinite(now)
                    and all(
                        type(value) in (int, float) and math.isfinite(value)
                        for value in row
                    )
                    and row[0] <= row[2] <= now < row[1]
                    and row[1] > row[0]
                )
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return False

    async def reconcile_if_approval_invalid(self, router: SchemaRouter) -> bool:
        """Withdraw stale E1 health menus on another router after revocation.

        The host calls this before exposing a model menu and again before
        each real source dispatch. Checking the local SQLite file performs
        no outbound request and consumes no canary budget. On invalid lease,
        replace only the two registered original source probes with local
        denial callbacks BEFORE a one-off monitor refresh, even if a
        misconfigured callback was unwrapped. The normal monitor may also
        remain running. Already in-flight requests cannot be cancelled.
        """
        if not isinstance(router, SchemaRouter):
            raise ValueError("trusted existing router required")
        if await asyncio.to_thread(self.approval_active):
            return True

        def denied_probe() -> bool:
            return False

        for route in _ROUTES:
            tool_key, endpoint = route.rsplit(".", 1)
            router.register_health_probe(tool_key, endpoint, denied_probe)
        await router.check_health_once()
        if any(
            snapshot.status == "healthy"
            and f"{snapshot.tool}.{snapshot.endpoint}" in _ROUTES
            for snapshot in router.health_snapshots()
        ):
            raise RuntimeError("router health did not reflect invalid lease")
        return False

    def revoke(self, *, operator_approved: bool) -> bool:
        """Operator-owned persistent revocation of ALL remaining canary claims.

        Does not invalidate other active routers' cached Healthy receipts by
        itself. A same-process router must be explicitly refreshed. In-flight
        HTTP GETs reserved BEFORE revocation are not cancelled or fenced.
        """
        if operator_approved is not True:
            raise ValueError("explicit operator approval for revocation required")
        if not self._path.is_file() or self._path.is_symlink():
            raise RuntimeError("cannot revoke absent trusted lease")
        try:
            with closing(self._connect_existing()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                # An irrevocable, schema-compatible sentinel: any legitimate
                # lease has expires > issued; setting expires=issued makes
                # every later try_claim fail, regardless of clock movement.
                # Serialized with every try_claim by SQLite BEGIN IMMEDIATE.
                modified = conn.execute(
                    "UPDATE lease SET expires=issued "
                    "WHERE id=? AND expires>issued",
                    (_LEASE,),
                )
                conn.commit()
                return modified.rowcount == 1
        except (sqlite3.Error, OSError, ValueError) as exc:
            # Never leak a local path or SQLite schema to a caller, and never
            # report revocation success when durable commit wasn't confirmed.
            raise RuntimeError("trusted operator lease revocation failed") from exc

    async def revoke_and_reconcile(
        self, router: SchemaRouter, *, operator_approved: bool,
    ) -> bool:
        """Revoke durable budget, then refresh THIS router's existing monitor.

        The application must use this operation on each affected local
        router and coordinate other workers; this is not cross-host fencing.
        """
        if not isinstance(router, SchemaRouter):
            raise ValueError("trusted existing router required")
        # Revocation I/O must never stall the active health event loop.
        changed = await asyncio.to_thread(
            self.revoke, operator_approved=operator_approved,
        )
        # A passed router may have stale or even mistakenly UNWRAPPED
        # callbacks. Re-running those original callbacks here would make
        # fresh external GETs AFTER operator revocation. Instead replace only
        # these two original read-only probe registrations with host-local
        # deny callbacks before rechecking. Re-enabling later requires a new
        # explicit trusted registration; this lease remains nonrenewable.
        def revoked_probe() -> bool:
            return False

        for route in _ROUTES:
            tool_key, endpoint = route.rsplit(".", 1)
            router.register_health_probe(tool_key, endpoint, revoked_probe)
        await router.check_health_once()
        # Never report a successful local withdrawal while either previously
        # authorized model-visible source remains Healthy.
        current = {
            f"{item.tool}.{item.endpoint}": item.status
            for item in router.health_snapshots()
        }
        if any(current.get(route) == "healthy" for route in _ROUTES):
            raise RuntimeError("router health did not reflect revoked lease")
        return changed

    def wrap_probe(
        self, route: str, callback: Callable[[], bool | Awaitable[bool]],
    ) -> Callable[[], Awaitable[bool]]:
        if route not in _ROUTES or not callable(callback):
            raise ValueError("only known authorized native canary callbacks")
        async def capped_callback() -> bool:
            # Reserve BEFORE any business endpoint GET; even a timeout consumes
            # this allowance, preventing retries after process interruption.
            if not await asyncio.to_thread(self.try_claim, route):
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

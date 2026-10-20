"""E0 only: durable same-host SQLite RESERVATION MODEL, not an egress proxy.

No network, actual identity verification, provider call, HTTP forwarding,
distributed filesystem, host ACL or authenticated operator. Returned decisions
MUST NEVER be accepted as permission for an external request: a reserve-then-
send race remains. This prototype tests restart/process/tenant persistence.
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal

from scripts.research_central_egress_admission_e0 import (
    _FIXED_ROUTES,
    SyntheticEgressRequestE0,
)

ReservationDecision = Literal[
    "synthetic_reservation", "operator_revoked", "stale_epoch",
    "identity_or_scope_denied", "allowance_exhausted", "duplicate_request",
    "synthetic_authority_unavailable",
]
HandoffDecision = Literal[
    "synthetic_handoff", "synthetic_handoff_failed",
    "synthetic_handoff_already_claimed", "synthetic_authority_unavailable",
    "operator_revoked", "stale_epoch", "identity_or_scope_denied",
]

_SCHEMA = """
CREATE TABLE authority (
    id INTEGER PRIMARY KEY CHECK(id=1),
    epoch INTEGER NOT NULL CHECK(epoch>=1),
    stopped INTEGER NOT NULL CHECK(stopped IN (0,1)),
    cap INTEGER NOT NULL CHECK(cap BETWEEN 1 AND 2)
);
CREATE TABLE allowed (
    tenant TEXT NOT NULL,
    workload TEXT NOT NULL,
    route TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    PRIMARY KEY(tenant, workload, route)
);
CREATE TABLE stopped_tenant (tenant TEXT PRIMARY KEY);
CREATE TABLE reservation (
    tenant TEXT NOT NULL,
    request_id TEXT NOT NULL,
    route TEXT NOT NULL,
    PRIMARY KEY(tenant, request_id)
);
CREATE INDEX reservation_by_tenant_route ON reservation(tenant, route);
CREATE TABLE synthetic_handoff_claim (
    tenant TEXT NOT NULL,
    request_id TEXT NOT NULL,
    PRIMARY KEY(tenant, request_id)
);
"""


def _safe_label(value: object) -> bool:
    return type(value) is str and 0 < len(value) <= 128


class DurableCentralReservationE0:
    """One-host SQLite state transition contract; NEVER a provider gateway."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("absolute trusted synthetic database path required")
        self._path = path

    def _existing_connection(self) -> sqlite3.Connection:
        # No implicit creation when absent/corrupted/replaced by symlink.
        if not self._path.is_file() or self._path.is_symlink():
            raise OSError("synthetic central DB unavailable")
        connection = sqlite3.connect(
            str(self._path), timeout=10.0, isolation_level=None,
        )
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def provision_once(
        self, *,
        allowed: Mapping[tuple[str, str, str], str],
        cap_per_tenant_route: int,
    ) -> None:
        """Create an E0 test fixture once; restarting never reissues authority."""
        if (
            type(cap_per_tenant_route) is not int
            or not 1 <= cap_per_tenant_route <= 2
            or not isinstance(allowed, Mapping)
            or not allowed
            or any(
                not isinstance(key, tuple)
                or len(key) != 3
                or not all(_safe_label(v) for v in key)
                or key[2] not in _FIXED_ROUTES
                or not _safe_label(fingerprint)
                for key, fingerprint in allowed.items()
            )
        ):
            raise ValueError("finite registered synthetic authority required")
        # Exclusive file creation rejects both re-provision and symlink.
        # If schema initialization is interrupted, future operations DENY;
        # the partial DB must never auto-heal or renew the old epoch.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self._path, flags, 0o600)
        os.close(fd)
        try:
            conn = self._existing_connection()
            try:
                # CREATE TABLE, authority row and ALL scoped registrations
                # form one transaction. A crash before COMMIT rolls back
                # the complete schema and the next opener denies the partial
                # one-shot file instead of granting a subset of identities.
                conn.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA)
                conn.execute(
                    "INSERT INTO authority VALUES(1, 1, 0, ?)",
                    (cap_per_tenant_route,),
                )
                conn.executemany(
                    "INSERT INTO allowed VALUES(?,?,?,?)",
                    [(*key, fingerprint) for key, fingerprint in allowed.items()],
                )
                conn.execute("COMMIT")
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            raise RuntimeError("synthetic central provision unavailable") from None

    def reserve(self, request: SyntheticEgressRequestE0) -> ReservationDecision:
        """Atomic durable quota/reservation only; NOT authorization to send."""
        if (
            not isinstance(request, SyntheticEgressRequestE0)
            or not all(_safe_label(v) for v in (
                request.tenant, request.workload, request.route_id,
                request.source_fingerprint, request.request_id,
            ))
            or request.route_id not in _FIXED_ROUTES
            or type(request.epoch) is not int
        ):
            return "identity_or_scope_denied"
        try:
            conn = self._existing_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                record = conn.execute(
                    "SELECT epoch, stopped, cap FROM authority WHERE id=1"
                ).fetchone()
                if record is None:
                    return "synthetic_authority_unavailable"
                identity = conn.execute(
                    "SELECT fingerprint FROM allowed "
                    "WHERE tenant=? AND workload=? AND route=?",
                    (request.tenant, request.workload, request.route_id),
                ).fetchone()
                if identity is None or identity[0] != request.source_fingerprint:
                    return "identity_or_scope_denied"
                if record[1] == 1 or conn.execute(
                    "SELECT 1 FROM stopped_tenant WHERE tenant=?",
                    (request.tenant,),
                ).fetchone() is not None:
                    return "operator_revoked"
                if request.epoch != record[0]:
                    return "stale_epoch"
                if conn.execute(
                    "SELECT 1 FROM reservation WHERE tenant=? AND request_id=?",
                    (request.tenant, request.request_id),
                ).fetchone() is not None:
                    return "duplicate_request"
                used = conn.execute(
                    "SELECT COUNT(*) FROM reservation WHERE tenant=? AND route=?",
                    (request.tenant, request.route_id),
                ).fetchone()
                if used is None or used[0] >= record[2]:
                    return "allowance_exhausted"
                conn.execute(
                    "INSERT INTO reservation VALUES(?,?,?)",
                    (request.tenant, request.request_id, request.route_id),
                )
                conn.execute("COMMIT")
                return "synthetic_reservation"
            finally:
                conn.close()
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return "synthetic_authority_unavailable"

    def _stop(self, tenant: str | None) -> bool:
        try:
            conn = self._existing_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT stopped FROM authority WHERE id=1"
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError("no authority")
                # Validate requested tenant even if a previous global stop
                # is already committed; unknown fixture labels must not be
                # silently accepted as an idempotent authorized stop.
                if tenant is not None:
                    exists = conn.execute(
                        "SELECT 1 FROM allowed WHERE tenant=? LIMIT 1", (tenant,)
                    ).fetchone()
                    if exists is None:
                        raise ValueError("preprovisioned synthetic tenant required")
                if row[0]:
                    return False
                if tenant is None:
                    conn.execute(
                        "UPDATE authority SET stopped=1, epoch=epoch+1 WHERE id=1"
                    )
                else:
                    already = conn.execute(
                        "SELECT 1 FROM stopped_tenant WHERE tenant=?", (tenant,)
                    ).fetchone()
                    if already:
                        return False
                    conn.execute(
                        "INSERT INTO stopped_tenant VALUES(?)", (tenant,)
                    )
                conn.execute("COMMIT")
                return True
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            raise RuntimeError("synthetic central revocation unavailable") from None

    def revoke_tenant(self, tenant: str) -> bool:
        """Test-only scoped stop; string is NOT authenticated operator identity."""
        if not _safe_label(tenant):
            raise ValueError("preprovisioned synthetic tenant required")
        return self._stop(tenant)

    def revoke_all(self) -> bool:
        """Test-only global stop; never reissues previously granted budgets."""
        return self._stop(None)

    def synthetic_handoff_after_reservation(
        self,
        request: SyntheticEgressRequestE0,
        *,
        synthetic_sink: Callable[[], None],
        test_after_intent_commit: Callable[[], None] | None = None,
    ) -> HandoffDecision:
        """E0 ONLY: persist a one-shot sink claim, then recheck under DB lock.

        There are deliberately TWO transactions: commit the non-refundable
        one-shot claim first; reacquire the writer lock and recheck revocation
        before executing the synthetic sink under that lock. If stop wins in
        between, there is no sink call and the claim cannot be replayed.
        A crash after claim commit also cannot replay an uncertain attempt.

        The sink is in-process TEST INSTRUMENTATION, never provider HTTP.
        Not a multi-host or production egress guarantee. Never call with an
        untrusted model-supplied callback or a network transport.
        """
        if (
            not isinstance(request, SyntheticEgressRequestE0)
            or not all(_safe_label(v) for v in (
                request.tenant, request.workload, request.route_id,
                request.source_fingerprint, request.request_id,
            ))
            or request.route_id not in _FIXED_ROUTES
            or type(request.epoch) is not int
            or not callable(synthetic_sink)
            or (
                test_after_intent_commit is not None
                and not callable(test_after_intent_commit)
            )
        ):
            return "identity_or_scope_denied"

        def current(conn: sqlite3.Connection) -> HandoffDecision | None:
            row = conn.execute(
                "SELECT epoch, stopped FROM authority WHERE id=1"
            ).fetchone()
            if row is None:
                return "synthetic_authority_unavailable"
            identity = conn.execute(
                "SELECT fingerprint FROM allowed "
                "WHERE tenant=? AND workload=? AND route=?",
                (request.tenant, request.workload, request.route_id),
            ).fetchone()
            if identity is None or identity[0] != request.source_fingerprint:
                return "identity_or_scope_denied"
            if row[1] == 1 or conn.execute(
                "SELECT 1 FROM stopped_tenant WHERE tenant=?",
                (request.tenant,),
            ).fetchone() is not None:
                return "operator_revoked"
            if request.epoch != row[0]:
                return "stale_epoch"
            reserved = conn.execute(
                "SELECT route FROM reservation WHERE tenant=? AND request_id=?",
                (request.tenant, request.request_id),
            ).fetchone()
            if reserved is None or reserved[0] != request.route_id:
                return "identity_or_scope_denied"
            return None

        try:
            conn = self._existing_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                denied = current(conn)
                if denied is not None:
                    return denied
                claimed = conn.execute(
                    "SELECT 1 FROM synthetic_handoff_claim "
                    "WHERE tenant=? AND request_id=?",
                    (request.tenant, request.request_id),
                ).fetchone()
                if claimed is not None:
                    return "synthetic_handoff_already_claimed"
                conn.execute(
                    "INSERT INTO synthetic_handoff_claim VALUES (?,?)",
                    (request.tenant, request.request_id),
                )
                # The once-only claim must survive even if the test sink
                # fails, crashes or revocation arrives before final check.
                conn.execute("COMMIT")
            finally:
                conn.close()
            if test_after_intent_commit is not None:
                test_after_intent_commit()
            conn = self._existing_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                denied = current(conn)
                if denied is not None:
                    return denied
                # Check durable intent again in case the file was replaced;
                # never invoke a sink without the once-only claim.
                claimed = conn.execute(
                    "SELECT 1 FROM synthetic_handoff_claim "
                    "WHERE tenant=? AND request_id=?",
                    (request.tenant, request.request_id),
                ).fetchone()
                if claimed is None:
                    return "synthetic_authority_unavailable"
                try:
                    synthetic_sink()
                except Exception:
                    return "synthetic_handoff_failed"
                return "synthetic_handoff"
            finally:
                # No modifications in the final phase; close releases its
                # writer lock regardless of simulated sink outcome.
                conn.close()
        except (sqlite3.Error, OSError, ValueError, TypeError):
            return "synthetic_authority_unavailable"

    def reserved_for_test(self, tenant: str, route: str) -> int:
        """Internal test counter, never log this as provider traffic."""
        if not _safe_label(tenant) or route not in _FIXED_ROUTES:
            raise ValueError("known E0 test labels required")
        try:
            with self._existing_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM reservation WHERE tenant=? AND route=?",
                    (tenant, route),
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError("missing reservation count")
                return int(row[0])
        except (sqlite3.Error, OSError):
            raise RuntimeError("synthetic central counts unavailable") from None

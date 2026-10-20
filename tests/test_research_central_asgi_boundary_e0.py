"""No-network ASGI protocol proof for the E0 synthetic egress boundary."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
import pytest

from scripts.research_central_asgi_boundary_e0 import (
    SyntheticScopeIdentityE0,
    make_synthetic_asgi_gateway_e0,
)
from scripts.research_central_durable_reservation_e0 import (
    DurableCentralReservationE0,
)
from scripts.research_central_egress_admission_e0 import (
    SyntheticEgressRequestE0,
)
from scripts.research_live_health_model_menu_e1 import GEO, WEATHER

_ASGI = Callable[[dict, Callable, Callable], Awaitable[None]]


def _store(path: Path) -> DurableCentralReservationE0:
    authority = DurableCentralReservationE0(path)
    authority.provision_once(
        allowed={
            ("church", "agent-a", GEO): "geo-1",
            ("church", "agent-b", GEO): "geo-1",
            ("school", "agent-a", GEO): "geo-1",
            ("church", "agent-a", WEATHER): "weather-1",
        },
        cap_per_tenant_route=2,
    )
    return authority


def _fixture_scope(app: _ASGI, identity: SyntheticScopeIdentityE0) -> _ASGI:
    """A trusted TEST harness, NEVER an unverified public identity middleware."""
    async def attach(scope: dict, receive: Callable, send: Callable) -> None:
        new_scope = dict(scope)
        new_scope["schemarouter.e0_fixture_identity"] = identity
        await app(new_scope, receive, send)

    return attach


def _payload(
    request_id: str, *, route: str = GEO, fingerprint: str = "geo-1",
    epoch: int = 1,
) -> dict[str, str | int]:
    return {
        "request_id": request_id, "route_id": route,
        "source_fingerprint": fingerprint, "epoch": epoch,
    }


@pytest.mark.asyncio
async def test_missing_identity_and_forged_headers_are_denied_before_handoff(
    tmp_path: Path,
):
    seen: list[str] = []
    store = _store(tmp_path / "default-deny.sqlite3")
    app = make_synthetic_asgi_gateway_e0(
        store, synthetic_sink=lambda req: seen.append(req.request_id),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        for endpoint in ("/e0/execute", "/e0/stop-tenant", "/e0/stop-all"):
            response = await client.post(
                endpoint, json={
                    **_payload("forged"),
                    "tenant": "church", "workload": "agent-a",
                },
                headers={
                    "x-tenant": "church",
                    "x-workload": "agent-a",
                    "x-role": "emergency_operator",
                    "authorization": "Bearer PRIVATE_UNTRUSTED",
                },
            )
            assert response.status_code == 403
            assert response.json() == {"decision": "identity_or_scope_denied"}
    assert seen == []
    assert store.reserved_for_test("church", GEO) == 0


@pytest.mark.asyncio
async def test_workload_identity_is_taken_from_scope_not_body_or_headers(tmp_path):
    store = _store(tmp_path / "identity.sqlite3")
    observed: list[SyntheticEgressRequestE0] = []
    app = make_synthetic_asgi_gateway_e0(
        store, synthetic_sink=observed.append,
    )
    agent = _fixture_scope(
        app, SyntheticScopeIdentityE0("workload", "church", "agent-a"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=agent),
        base_url="http://synthetic.invalid",
    ) as client:
        ok = await client.post(
            "/e0/execute", json=_payload("valid"),
            headers={"x-tenant": "school", "x-workload": "other"},
        )
        assert ok.status_code == 200
        assert ok.json() == {"decision": "synthetic_handoff"}
        assert observed[0].tenant == "church"
        assert observed[0].workload == "agent-a"
        duplicate = await client.post("/e0/execute", json=_payload("valid"))
        assert duplicate.status_code == 409
        assert duplicate.json() == {"decision": "duplicate_request"}
        unauthorized_source = await client.post(
            "/e0/execute", json=_payload("wrong-source", fingerprint="unknown"),
        )
        assert unauthorized_source.status_code == 403
        wrong_epoch = await client.post(
            "/e0/execute", json=_payload("wrong-epoch", epoch=2),
        )
        assert wrong_epoch.status_code == 403
    assert len(observed) == 1
    assert store.reserved_for_test("church", GEO) == 1


@pytest.mark.asyncio
async def test_tenant_stop_does_not_take_other_tenant_offline(tmp_path: Path):
    store = _store(tmp_path / "tenant-stop.sqlite3")
    observed: list[str] = []
    app = make_synthetic_asgi_gateway_e0(
        store, synthetic_sink=lambda request: observed.append(request.tenant),
    )
    church = _fixture_scope(
        app, SyntheticScopeIdentityE0("workload", "church", "agent-a"),
    )
    school = _fixture_scope(
        app, SyntheticScopeIdentityE0("workload", "school", "agent-a"),
    )
    church_operator = _fixture_scope(
        app, SyntheticScopeIdentityE0("tenant_operator", "church"),
    )
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=church),
            base_url="http://synthetic.invalid",
        ) as church_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=school),
            base_url="http://synthetic.invalid",
        ) as school_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=church_operator),
            base_url="http://synthetic.invalid",
        ) as operator,
    ):
        stopped = await operator.post(
            "/e0/stop-tenant", json={"tenant": "school"},
        )
        assert stopped.json() == {"decision": "operator_revoked", "changed": True}
        assert (
            await church_client.post("/e0/execute", json=_payload("c"))
        ).status_code == 403
        assert (
            await school_client.post("/e0/execute", json=_payload("s"))
        ).status_code == 200
    assert observed == ["school"]


@pytest.mark.asyncio
async def test_global_emergency_stop_requires_distinct_scope_role(tmp_path: Path):
    store = _store(tmp_path / "emergency.sqlite3")
    observed: list[str] = []
    app = make_synthetic_asgi_gateway_e0(
        store, synthetic_sink=lambda req: observed.append(req.request_id),
    )
    normal = _fixture_scope(
        app, SyntheticScopeIdentityE0("tenant_operator", "church"),
    )
    emergency = _fixture_scope(
        app, SyntheticScopeIdentityE0("emergency_operator", "church"),
    )
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=normal),
            base_url="http://synthetic.invalid",
        ) as normal_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=emergency),
            base_url="http://synthetic.invalid",
        ) as emergency_client,
    ):
        assert (
            await normal_client.post("/e0/stop-all")
        ).status_code == 403
        stop = await emergency_client.post("/e0/stop-all")
        assert stop.json() == {"decision": "operator_revoked", "changed": True}
        repeated = await emergency_client.post("/e0/stop-all")
        assert repeated.json() == {"decision": "operator_revoked", "changed": False}
    assert observed == []
    assert store.reserve(
        SyntheticEgressRequestE0(
            "church", "agent-a", GEO, "geo-1", "later", 2,
        )
    ) == "operator_revoked"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {},
    {"request_id": "x", "route_id": GEO, "source_fingerprint": "geo-1", "epoch": True},
    {"request_id": ["invalid"], "route_id": GEO, "source_fingerprint": "geo-1", "epoch": 1},
    {**_payload("forged"), "tenant": "church"},
])
async def test_malformed_or_body_derived_authority_is_not_accepted(
    tmp_path: Path, payload: dict,
):
    store = _store(tmp_path / "malformed.sqlite3")
    forwarded: list[str] = []
    app = _fixture_scope(
        make_synthetic_asgi_gateway_e0(
            store, synthetic_sink=lambda req: forwarded.append(req.request_id),
        ),
        SyntheticScopeIdentityE0("workload", "church", "agent-a"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        response = await client.post("/e0/execute", json=payload)
        assert response.status_code == 400
    assert forwarded == []


@pytest.mark.asyncio
async def test_two_simulated_asgi_clients_share_one_durable_quota(tmp_path: Path):
    store = _store(tmp_path / "concurrent.sqlite3")
    forwarded: list[str] = []
    app = make_synthetic_asgi_gateway_e0(
        store, synthetic_sink=lambda req: forwarded.append(req.request_id),
    )
    a = _fixture_scope(
        app, SyntheticScopeIdentityE0("workload", "church", "agent-a"),
    )
    b = _fixture_scope(
        app, SyntheticScopeIdentityE0("workload", "church", "agent-b"),
    )
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=a),
            base_url="http://synthetic.invalid",
        ) as client_a,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=b),
            base_url="http://synthetic.invalid",
        ) as client_b,
    ):
        results = await asyncio.gather(*[
            (client_a if i % 2 else client_b).post(
                "/e0/execute", json=_payload(f"candidate-{i}"),
            )
            for i in range(12)
        ])
    assert sum(response.status_code == 200 for response in results) == 2
    assert len(forwarded) == 2
    assert store.reserved_for_test("church", GEO) == 2


@pytest.mark.asyncio
async def test_closed_or_corrupt_authority_cannot_emit_from_http(tmp_path: Path):
    path = tmp_path / "absent.sqlite3"
    store = DurableCentralReservationE0(path)
    forwarded: list[str] = []
    app = _fixture_scope(
        make_synthetic_asgi_gateway_e0(
            store, synthetic_sink=lambda req: forwarded.append(req.request_id),
        ),
        SyntheticScopeIdentityE0("workload", "church", "agent-a"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://synthetic.invalid",
    ) as client:
        response = await client.post("/e0/execute", json=_payload("absent"))
        assert response.status_code == 503
        assert response.json() == {"decision": "synthetic_authority_unavailable"}
    assert forwarded == []

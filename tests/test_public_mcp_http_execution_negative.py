"""Source-audited registered streamable HTTP MCP execution denials.

Real local HTTP MCPServer subprocess and actual SDK executor, not an invoker
mock. Host/provider-independent E2 is NOT claimed by this DEV regression.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_mcp_integration import _free_port, _wait_for_port

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPolicy,
    PlanRequest,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
)
from schemarouter.errors import SchemaRouterError


@pytest.mark.asyncio
@pytest.mark.mcp_integration
async def test_mcp_http_registered_unavailable_recovery_stale_zero_handler_calls(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "http-mcp-handler-calls.log"
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    env["SCHEMAROUTER_MCP_HTTP_CALL_AUDIT"] = str(audit_path)
    server = Path(__file__).parent / "fixtures" / "mcp_http_server.py"
    process = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(
            rules=(AuthorizationRule(
                effect="allow", operation="*", roles_any=("admin",),
            ),),
            default_effect="deny",
        ),
    )
    try:
        await _wait_for_port(port, process)
        tool = await router.add_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            trusted_headers={"X-SchemaRouter-Test": "integration"},
        )
        admin = PrincipalContext(subject="owner", roles=("admin",))
        guest = PrincipalContext(subject="guest", roles=("guest",))
        plan = router.plan_authorized(
            PlanRequest(
                query="add result", preferred_tools=[tool.key],
                arguments={"a": 7, "b": 8},
            ),
            principal=admin,
        )
        assert plan.executable and len(plan.calls) == 1
        assert not audit_path.exists()

        with pytest.raises(PolicyViolationError):
            await router.execute(plan, config=RunConfig(principal=guest))
        assert not audit_path.exists(), "Guest reached MCP HTTP source handler"

        endpoint = plan.calls[0].endpoint
        router.mark_access_unavailable(tool.key, endpoint, cooldown_seconds=120)
        with pytest.raises(SchemaRouterError):
            await router.execute(plan, config=RunConfig(principal=admin))
        assert not audit_path.exists(), "Unavailable MCP HTTP route reached handler"

        router.mark_access_available(tool.key, endpoint)
        result = await router.execute(plan, config=RunConfig(principal=admin))
        assert result[0].data == {"result": 15}
        assert audit_path.read_text(encoding="utf-8").splitlines() == ["7,8"]

        await router.aremove_tool(tool.key)
        with pytest.raises(SchemaRouterError):
            await router.execute(plan, config=RunConfig(principal=admin))
        assert audit_path.read_text(encoding="utf-8").splitlines() == ["7,8"]
    finally:
        await router.aclose()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPolicy,
    PlanRequest,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
)
from schemarouter.errors import SchemaRouterError

pytestmark = pytest.mark.mcp_integration


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "MCP fixture server exited before becoming ready\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        writer.close()
        await writer.wait_closed()
        return
    raise RuntimeError("MCP fixture server did not become ready")


@pytest.mark.asyncio
async def test_real_streamable_http_mcp_discovery_and_execution() -> None:
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    server = Path(__file__).parent / "fixtures" / "mcp_http_server.py"

    process = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        await _wait_for_port(port, process)
        router = SchemaRouter(
            policy=ExecutionPolicy(allow_unclassified_remote=True)
        )
        tool = await router.add_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            trusted_headers={"X-SchemaRouter-Test": "integration"},
        )

        assert tool.metadata["adapter"] == "mcp"
        assert tool.metadata["protocol_version"]
        assert tool.metadata["authenticated_transport"] is True
        assert "integration" not in repr(tool.model_dump(mode="json"))
        assert [endpoint.name for endpoint in tool.endpoints] == ["add"]

        endpoint = tool.endpoints[0]
        assert endpoint.input_schema["properties"]["a"]["type"] == "integer"
        assert endpoint.input_schema["properties"]["b"]["type"] == "integer"
        assert endpoint.output_schema["properties"]["result"]["type"] == "integer"

        plan = router.plan(
            PlanRequest(
                query="add result",
                arguments={"a": 2, "b": 3},
            )
        )
        assert plan.executable

        results = await router.execute(plan)
        assert results[0].data == {"result": 5}
    finally:
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


@pytest.mark.asyncio
async def test_real_stdio_mcp_discovery_and_execution() -> None:
    server = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True)
    )

    tool = await router.add_mcp_stdio(
        sys.executable,
        args=[str(server)],
        allowed_commands=[sys.executable],
        name="stdio-fixture",
    )

    assert tool.metadata["adapter"] == "mcp"
    assert tool.metadata["transport"] == "stdio"
    assert tool.metadata["protocol_version"]
    assert tool.execution_metadata["transport"] == "stdio"
    assert tool.remote is True
    assert tool.access_mode == "mcp_stdio"
    assert sys.executable not in repr(tool.model_dump(mode="json"))
    assert str(server) not in repr(tool.model_dump(mode="json"))
    assert [endpoint.name for endpoint in tool.endpoints] == ["add"]

    plan = router.plan(
        PlanRequest(
            query="add result",
            preferred_tools=[tool.key],
            arguments={"a": 7, "b": 8},
        )
    )
    assert plan.executable

    results = await router.execute(plan)
    assert results[0].data == {"result": 15}


@pytest.mark.asyncio
async def test_real_http_mcp_rejects_invalid_arguments_before_execution() -> None:
    """Reject malformed arguments on a genuinely registered HTTP MCP route."""
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    server = Path(__file__).parent / "fixtures" / "mcp_http_server.py"
    process = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        await _wait_for_port(port, process)
        router = SchemaRouter(policy=ExecutionPolicy(allow_unclassified_remote=True))
        tool = await router.add_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            trusted_headers={"X-SchemaRouter-Test": "integration"},
        )
        with pytest.raises(SchemaValidationError):
            await router.ainvoke(
                PlanRequest(
                    query="add result",
                    preferred_tools=[tool.key],
                    arguments={"a": "not-an-integer", "b": 3},
                )
            )
    finally:
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


@pytest.mark.asyncio
async def test_real_http_mcp_denies_revoked_principal_before_execution() -> None:
    """A valid plan cannot be reused by an unauthorized principal."""
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    server = Path(__file__).parent / "fixtures" / "mcp_http_server.py"
    process = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        await _wait_for_port(port, process)
        router = SchemaRouter(
            policy=ExecutionPolicy(allow_unclassified_remote=True),
            authorization_policy=AuthorizationPolicy(
                rules=(
                    AuthorizationRule(
                        effect="allow",
                        operation="*",
                        roles_any=("admin",),
                    ),
                ),
                default_effect="deny",
            ),
        )
        tool = await router.add_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            trusted_headers={"X-SchemaRouter-Test": "integration"},
        )
        admin = PrincipalContext(subject="owner", roles=("admin",))
        denied = PrincipalContext(subject="guest", roles=("guest",))
        plan = router.plan_authorized(
            PlanRequest(
                query="add result",
                preferred_tools=[tool.key],
                arguments={"a": 2, "b": 3},
            ),
            principal=admin,
        )
        assert plan.executable and plan.calls
        result = await router.execute(plan, config=RunConfig(principal=admin))
        assert result[0].data == {"result": 5}

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=RunConfig(principal=denied))
    finally:
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


@pytest.mark.asyncio
async def test_real_stdio_mcp_public_denial_inputs_and_stale_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real MCP subprocess: denied requests do not reach its source tool."""
    audited = tmp_path / "stdio-tool-calls.txt"
    monkeypatch.setenv("SCHEMAROUTER_MCP_STDIO_CALL_AUDIT", str(audited))
    server = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
    admin = PrincipalContext(subject="owner", roles=("admin",))
    denied = PrincipalContext(subject="guest", roles=("guest",))
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(
            rules=(AuthorizationRule(
                effect="allow",
                operation="*",
                roles_any=("admin",),
            ),),
            default_effect="deny",
        ),
    )
    try:
        tool = await router.add_mcp_stdio(
            sys.executable,
            args=[str(server)],
            allowed_commands=[sys.executable],
            env={"SCHEMAROUTER_MCP_STDIO_CALL_AUDIT": str(audited)},
            name="stdio-negative-fixture",
        )
        assert tool.metadata["transport"] == "stdio"
        request = PlanRequest(
            query="add result", preferred_tools=[tool.key],
            arguments={"a": 7, "b": 8},
        )
        plan = router.plan_authorized(request, principal=admin)
        assert plan.executable and plan.calls

        with pytest.raises(PolicyViolationError, match="authorization denied"):
            await router.execute(plan, config=RunConfig(principal=denied))
        assert not audited.exists(), "Guest executed an MCP subprocess tool"

        malformed = plan.model_copy(deep=True)
        malformed.calls[0].arguments["a"] = "not-an-integer"
        with pytest.raises(SchemaValidationError):
            await router.execute(malformed, config=RunConfig(principal=admin))
        assert not audited.exists(), "Invalid MCP input crossed source boundary"

        missing_required = plan.model_copy(deep=True)
        missing_required.calls[0].arguments.pop("b")
        with pytest.raises(PlanValidationError, match="missing required arguments"):
            await router.execute(missing_required, config=RunConfig(principal=admin))
        assert not audited.exists(), "Missing MCP input crossed source boundary"

        output = await router.execute(plan, config=RunConfig(principal=admin))
        assert output[0].data == {"result": 15}
        assert audited.read_text(encoding="utf-8").splitlines() == ["7,8"]

        await router.aremove_tool(tool.key)
        with pytest.raises(SchemaRouterError):
            await router.execute(plan, config=RunConfig(principal=admin))
        assert audited.read_text(encoding="utf-8").splitlines() == ["7,8"]
    finally:
        await router.aclose()

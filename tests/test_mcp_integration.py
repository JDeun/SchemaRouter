from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter

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
        )

        assert tool.metadata["adapter"] == "mcp"
        assert tool.metadata["protocol_version"]
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

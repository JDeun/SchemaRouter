"""Pinned-reference example for MCP Streamable HTTP and stdio transports.

Run from a repository checkout after:
    pip install -e ".[mcp]"
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter


ROOT = Path(__file__).resolve().parents[1]
HTTP_SERVER = ROOT / "tests" / "fixtures" / "mcp_http_server.py"
STDIO_SERVER = ROOT / "tests" / "fixtures" / "mcp_stdio_server.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
    for _ in range(120):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "MCP reference server exited before becoming ready\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        del reader
        writer.close()
        await writer.wait_closed()
        return
    raise RuntimeError("MCP reference server did not become ready")


async def run_http_reference() -> None:
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, str(HTTP_SERVER)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    router: SchemaRouter | None = None
    try:
        await _wait_for_port(port, process)
        router = await SchemaRouter.from_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            policy=ExecutionPolicy(allow_unclassified_remote=True),
        )
        tool = router.registry.tools()[0]
        result = (
            await router.ainvoke(
                PlanRequest(
                    query="add result",
                    preferred_tools=[tool.key],
                    arguments={"a": 2, "b": 3},
                )
            )
        )[0]
        assert result.data == {"result": 5}
        print(f"streamable-http: {result.data}")
    finally:
        if router is not None:
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


async def run_stdio_reference() -> None:
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
    )
    try:
        tool = await router.add_mcp_stdio(
            sys.executable,
            args=[str(STDIO_SERVER)],
            allowed_commands=[sys.executable],
            provider="schemarouter-reference",
        )
        result = (
            await router.ainvoke(
                PlanRequest(
                    query="add result",
                    preferred_tools=[tool.key],
                    arguments={"a": 4, "b": 5},
                )
            )
        )[0]
        assert result.data == {"result": 9}
        print(f"stdio: {result.data}")
    finally:
        await router.aclose()


async def main() -> None:
    await run_http_reference()
    await run_stdio_reference()


if __name__ == "__main__":
    asyncio.run(main())

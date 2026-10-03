from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import (\n    ExecutionPolicy,\n    PlanRequest,\n    ProviderAccessMethod,\n    ProviderProfile,\n    SchemaRouter,\n)


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


async def run_smoke() -> dict[str, object]:
    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    server = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "mcp_http_server.py"
    )
    process = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    router: SchemaRouter | None = None

    try:
        await _wait_for_port(port, process)
        source = f"http://127.0.0.1:{port}/mcp"
        router = SchemaRouter(
            policy=ExecutionPolicy(allow_unclassified_remote=True)
        )
        router.register_provider_profile(
            ProviderProfile(
                provider_id="local-mcp-reference",
                display_name="SchemaRouter pinned MCP Streamable HTTP reference server",
                methods=(
                    ProviderAccessMethod(
                        method_id="mcp",
                        kind="mcp",
                        access_mode="mcp",
                        url=source,
                    ),
                ),
            )
        )

        started = perf_counter()
        registration = await router.add_provider("local-mcp-reference")
        discovery_ms = round((perf_counter() - started) * 1000, 2)
        assert registration.methods[0].status == "registered"
        assert len(registration.registered_tool_keys) == 1
        tool = router.registry.get(registration.registered_tool_keys[0])

        assert tool.metadata["adapter"] == "mcp"
        assert tool.provider == "local-mcp-reference"
        assert tool.access_mode == "mcp"
        assert tool.metadata["protocol_version"]
        endpoint = tool.endpoint("add")

        started = perf_counter()
        results = await router.ainvoke(
            PlanRequest(
                query="add result",
                preferred_tools=[tool.key],
                arguments={"a": 2, "b": 3},
            )
        )
        execution_ms = round((perf_counter() - started) * 1000, 2)

        assert results[0].data == {"result": 5}

        return {
            "evidence_kind": "pinned_reference_implementation",
            "provider": "SchemaRouter pinned MCP Streamable HTTP reference server",
            "provider_first": True,
            "protocol_version": tool.metadata["protocol_version"],
            "discovery_success": True,
            "tool_count": 1,
            "endpoint_count": len(tool.endpoints),
            "execution_bound": router.executor.is_binding_ready_for_contract(
                tool.key,
                tool.fingerprint,
            ),
            "execution_success": True,
            "safe_endpoint": endpoint.name,
            "returned_shape": "object",
            "discovery_latency_ms": discovery_ms,
            "execution_latency_ms": execution_ms,
            "auth_required": endpoint.auth_required,
            "known_quirks": [
                (
                    "Pinned local reference server is used instead of assuming "
                    "a stable public MCP endpoint."
                )
            ],
        }
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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    report = new_report(
        adapter="mcp",
        source="pinned-local-streamable-http-reference",
    )
    report["details"] = {
        "evidence_kind": "pinned_reference_implementation",
        "provider": "SchemaRouter pinned MCP Streamable HTTP reference server",
    }

    try:
        report["details"].update(await run_smoke())
        report["status"] = "success"
    except Exception as exc:
        report["status"] = "failure"
        report["error_type"] = type(exc).__name__
        write_report(args.json_out, report)
        raise

    write_report(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())

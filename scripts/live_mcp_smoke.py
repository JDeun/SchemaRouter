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

from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter

REFERENCE_SERVER = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mcp_http_server.py"


def _shape(value: object) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
    for _ in range(100):
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
        writer.close()
        await writer.wait_closed()
        return
    raise RuntimeError("MCP reference server did not become ready")


async def run_smoke(report: dict[str, object]) -> dict[str, object]:
    if not REFERENCE_SERVER.exists():
        raise RuntimeError(f"MCP reference server is missing: {REFERENCE_SERVER}")

    port = _free_port()
    env = dict(os.environ)
    env["SCHEMAROUTER_MCP_TEST_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, str(REFERENCE_SERVER)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    router: SchemaRouter | None = None

    try:
        await _wait_for_port(port, process)
        policy = ExecutionPolicy(allow_unclassified_remote=True)

        started = perf_counter()
        router = SchemaRouter(policy=policy)
        tool = await router.add_url(
            f"http://127.0.0.1:{port}/mcp",
            kind="mcp",
            trusted_headers={"X-SchemaRouter-Test": "compatibility"},
        )
        report["protocol_version"] = tool.metadata.get("protocol_version")
        report["discovery"] = {
            "success": True,
            "tool_count": len(router.registry.keys()),
            "endpoint_count": len(tool.endpoints),
            "execution_bound": (
                router.executor.binding_status_for_contract(
                    tool.key,
                    tool.fingerprint,
                )
                == "ready"
            ),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }

        endpoint = tool.endpoint("add")
        execution_started = perf_counter()
        plan = router.plan(
            PlanRequest(
                query="add result",
                preferred_tools=[tool.key],
                arguments={"a": 2, "b": 3},
            )
        )
        result = (await router.execute(plan))[0]
        report["execution"] = {
            "attempted": True,
            "safe_read_only": endpoint.read_only is True,
            "endpoint": endpoint.name,
            "success": result.data == {"result": 5},
            "latency_ms": round(
                (perf_counter() - execution_started) * 1000,
                2,
            ),
            "result_shape": _shape(result.data),
        }

        if result.data != {"result": 5}:
            raise AssertionError("MCP reference execution returned an unexpected result")

        return {
            "tool": tool.key,
            "endpoint": endpoint.name,
            "protocol_version": tool.metadata.get("protocol_version"),
            "result": result.data,
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
        source="local://tests/fixtures/mcp_http_server.py",
        provider="SchemaRouter pinned MCP reference server",
        evidence_mode="pinned-reference",
        authentication="local test header",
    )
    report["known_quirks"] = [
        (
            "No stable unauthenticated public MCP endpoint is assumed. "
            "Compatibility evidence uses the pinned Streamable HTTP reference server."
        ),
        (
            "Remote MCP annotations are not trusted as execution authority; "
            "the smoke opts into unclassified remote execution with local policy."
        ),
    ]

    try:
        report["details"] = await run_smoke(report)
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

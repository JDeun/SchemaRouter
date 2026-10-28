"""Source-specific, keyless public provider validation (opt-in live E1).

No model-derived arguments, credentials, source-owned permission claims or
cross-provider semantic gold are introduced by this research harness.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

import httpx

from schemarouter import ExecutionPlan, ExecutionPolicy, SchemaRouter, ToolCall, ToolSpec

DOI = "10.1038/nature12373"
REPO = "modelcontextprotocol/servers"
COD_FILTER = 'elements HAS ALL "Si","O" AND nelements=2'
COD_URL = "https://www.crystallography.net/cod/optimade"
DEEPWIKI_URL = "https://mcp.deepwiki.com/mcp"
EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MAX_MCP_CONTENT_BYTES = 131072
# Per HTTP response (including SSE events), before MCP SDK parsing/buffering.
MAX_MCP_WIRE_BYTES = 524288
MAX_HTTP_CONTENT_BYTES = 262144


async def limit_mcp_http_response(response: Any) -> None:
    """Restrict bytes read by the opt-in public MCP transport itself."""
    import httpx2

    # httpx2 transparently decompresses gzip/deflate before SDK buffering.
    # A tiny compressed chunk could otherwise bypass the on-wire byte bound.
    if response.headers.get("content-encoding", "identity").strip().lower() not in (
        "identity",
        "",
    ):
        raise ValueError("MCP compressed response encoding not approved")

    class _BoundedMCPStream(httpx2.AsyncByteStream):
        def __init__(self, upstream: httpx2.AsyncByteStream) -> None:
            self.upstream = upstream

        async def __aiter__(self) -> AsyncIterator[bytes]:
            total = 0
            async for chunk in self.upstream:
                total += len(chunk)
                if total > MAX_MCP_WIRE_BYTES:
                    raise ValueError("MCP wire response exceeded byte bound")
                yield chunk

        async def aclose(self) -> None:
            await self.upstream.aclose()

    response.stream = _BoundedMCPStream(response.stream)


@asynccontextmanager
async def bounded_public_mcp_client_factory(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
) -> AsyncIterator[Any]:
    """Official MCP client, pinned public host, wire cap and no DELETE teardown."""
    if url != DEEPWIKI_URL or headers:
        raise ValueError("public MCP source host or headers not approved")
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async with httpx2.AsyncClient(
        headers={"Accept-Encoding": "identity"},
        timeout=httpx2.Timeout(timeout, read=timeout),
        follow_redirects=False,
        limits=httpx2.Limits(max_connections=4, max_keepalive_connections=2),
        event_hooks={"response": [limit_mcp_http_response]},
    ) as http_client:
        transport = streamable_http_client(
            url,
            http_client=http_client,
            max_sse_event_size=MAX_MCP_WIRE_BYTES,
            terminate_on_close=False,
        )
        async with Client(transport) as session:
            yield session


def _doi(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        raise ValueError("source DOI missing or malformed")
    normalized = value.strip().lower()
    if not normalized.startswith("10.") or "/" not in normalized:
        raise ValueError("source DOI identifier is not valid")
    return normalized


def validate_crossref_work(payload: Any, *, expected_doi: str) -> str:
    """Read only source-reported DOI after verifying requested identity."""
    if not isinstance(payload, dict):
        raise ValueError("Crossref work metadata missing")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise ValueError("Crossref work metadata missing")
    original = _doi(message.get("DOI"))
    if original != _doi(expected_doi):
        raise ValueError("Crossref DOI mismatch")
    title = message.get("title")
    if (
        not isinstance(title, list)
        or not title
        or not isinstance(title[0], str)
        or not title[0].strip()
    ):
        raise ValueError("Crossref work title missing")
    return original


def validate_europe_pmc_doi(payload: Any, *, expected_doi: str) -> int:
    """A valid HTTP/JSON response with no matching DOI is a task failure."""
    if not isinstance(payload, dict):
        raise ValueError("Europe PMC result missing")
    count = payload.get("hitCount")
    result_list = payload.get("resultList")
    rows = result_list.get("result") if isinstance(result_list, dict) else None
    if type(count) is not int or count <= 0 or not isinstance(rows, list):
        raise ValueError("Europe PMC DOI result empty or invalid")
    expected = _doi(expected_doi)
    matches = sum(
        1
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("doi"), str)
        and _doi(row["doi"]) == expected
        and isinstance(row.get("id"), str)
        and bool(row["id"])
    )
    if matches <= 0:
        raise ValueError("Europe PMC DOI does not match original Crossref identity")
    return matches


def validate_optimade_structure(rows: Any) -> int:
    """Use original OPTIMADE crystal identities/elements, not HTTP 200 alone."""
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("OPTIMADE structure result must contain one source row")
    row = rows[0]
    if not isinstance(row.get("id"), str) or not row["id"].strip():
        raise ValueError("OPTIMADE structure identity missing")
    if type(row.get("nelements")) is not int or row["nelements"] != 2:
        raise ValueError("OPTIMADE structure element cardinality mismatch")
    elements = row.get("elements")
    if not isinstance(elements, list) or len(elements) != 2 or set(elements) != {"Si", "O"}:
        raise ValueError("OPTIMADE structure original elements disagree with filter")
    formula = row.get("chemical_formula_descriptive")
    if not isinstance(formula, str) or not 1 <= len(formula.strip()) <= 200:
        raise ValueError("OPTIMADE structure chemical formula missing")
    return 1


def validate_deepwiki_mcp_result(payload: Any) -> int:
    """Require source-shaped numbered pages, not a transport-success error string.

    This validates *already received* source data; the MCP SDK can buffer
    bytes before this check, so this does not claim a transport memory cap.
    """
    # FastMCP declares outputSchema.result as string; the native router's
    # explicit projection returns that source-owned object, not raw blocks.
    if not isinstance(payload, dict) or set(payload) != {"result"}:
        raise ValueError("MCP wiki source projection must contain only result")
    value = payload["result"]
    if (
        not isinstance(value, str)
        or len(value.strip()) < 20
        or len(value.encode("utf-8")) > MAX_MCP_CONTENT_BYTES
    ):
        raise ValueError("MCP wiki projected content invalid")
    lines = value.splitlines()
    if not lines or lines[0].strip() != f"Available pages for {REPO}:":
        raise ValueError("MCP wiki did not return a source-owned repository outline")
    numbered_pages = sum(
        1 for line in lines[1:] if re.fullmatch(r"\s*-\s+\d+(?:\.\d+)*\s+\S.*", line)
    )
    if numbered_pages < 2:
        raise ValueError("MCP wiki returned no verifiable numbered content outline")
    return 1


def checked_call(
    tool: ToolSpec,
    *,
    endpoint: str,
    arguments: dict[str, Any],
    fields: list[str],
    permitted_endpoint: str,
) -> ToolCall:
    """Only a host-pinned source endpoint/input/projection may be executed."""
    if endpoint != permitted_endpoint:
        raise ValueError("endpoint not on host allowlist")
    source_endpoint = tool.endpoint(endpoint)
    remote_mcp_read = (
        endpoint == "read_wiki_structure"
        and tool.metadata.get("adapter") == "mcp"
        and source_endpoint.method in (None, "MCP")
        and source_endpoint.destructive is not True
    )
    if not remote_mcp_read and (
        source_endpoint.method != "GET"
        or source_endpoint.read_only is not True
        or source_endpoint.destructive is True
    ):
        raise ValueError("endpoint is not a safe read operation")
    declared_fields = {field.name for field in source_endpoint.output_fields}
    if not fields or not set(fields) <= declared_fields:
        raise ValueError("projection includes undeclared source field")
    declared_params = {parameter.name for parameter in source_endpoint.parameters}
    input_schema_props = source_endpoint.input_schema.get("properties", {})
    if isinstance(input_schema_props, dict):
        declared_params.update(input_schema_props)
    if not set(arguments) <= declared_params:
        raise ValueError("input argument not in source schema")
    required = {parameter.name for parameter in source_endpoint.parameters if parameter.required}
    input_required = source_endpoint.input_schema.get("required", [])
    if isinstance(input_required, list):
        required.update(x for x in input_required if isinstance(x, str))
    if not required <= arguments.keys():
        raise ValueError("required source argument missing")
    return ToolCall(
        tool=tool.key,
        endpoint=source_endpoint.name,
        arguments=arguments,
        fields=fields,
        schema_fingerprint=source_endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("provider JSON duplicated an object key")
        output[key] = value
    return output


def _nonfinite(_: str) -> None:
    raise ValueError("provider JSON nonfinite value")


async def crosscheck_europe_pmc(client: httpx.AsyncClient, crossref_doi: str) -> int:
    """Independent public HTTP verification of a *Crossref-proven* identifier."""
    verified_doi = _doi(crossref_doi)
    async with client.stream(
        "GET",
        EUROPE_PMC_URL,
        params={"query": f"DOI:{verified_doi}", "format": "json", "pageSize": "1"},
    ) as response:
        response.raise_for_status()
        if "application/json" not in response.headers.get("content-type", "").lower():
            raise ValueError("provider response is not JSON content")
        # stream() does not eagerly buffer untrusted source bytes like get().
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > MAX_HTTP_CONTENT_BYTES:
                raise ValueError("provider response exceeded streamed byte bound")
            body.extend(chunk)
    try:
        payload = json.loads(
            body,
            object_pairs_hook=_unique_keys,
            parse_constant=_nonfinite,
        )
    except (TypeError, UnicodeError, ValueError) as exc:
        raise ValueError("provider response contained invalid JSON") from exc
    return validate_europe_pmc_doi(payload, expected_doi=verified_doi)


async def run_live_anonymous_source_matrix() -> dict[str, Any]:
    """One authentic 3-provider router; all four public network reads are real.

    Source identities and complete fixed task arguments are caller-independent.
    A task failure raises; no fixture fallback can emit a false live success.
    """
    router = SchemaRouter(policy=ExecutionPolicy(allow_unclassified_remote=True))
    started = perf_counter()
    try:
        crossref_registration = await router.add_provider(
            "crossref",
            timeout=20,
            trusted_headers_by_method={
                "rest": {
                    "User-Agent": "SchemaRouter public research (https://github.com/JDeun/SchemaRouter)"
                }
            },
        )
        if len(crossref_registration.registered_tool_keys) != 1:
            raise ValueError("Crossref native provider registration incomplete")
        crossref = router.registry.get(crossref_registration.registered_tool_keys[0])
        cod = await router.add_url(COD_URL, kind="optimade", name="cod_public", timeout=20)
        deepwiki = await router.add_url(
            DEEPWIKI_URL,
            kind="mcp",
            name="deepwiki_public",
            mcp_client_factory=bounded_public_mcp_client_factory,
            timeout=25,
        )
        if len(router.registry.keys()) != 3 or len({crossref.key, cod.key, deepwiki.key}) != 3:
            raise ValueError("heterogeneous source registry must contain 3 distinct tools")

        crossref_call = checked_call(
            crossref,
            endpoint="get_work",
            arguments={"doi": DOI},
            fields=["message"],
            permitted_endpoint="get_work",
        )
        cod_call = checked_call(
            cod,
            endpoint="search_structures",
            arguments={
                "filter": COD_FILTER,
                "page_limit": 1,
            },
            fields=["id", "chemical_formula_descriptive", "nelements", "elements"],
            permitted_endpoint="search_structures",
        )
        mcp_call = checked_call(
            deepwiki,
            endpoint="read_wiki_structure",
            arguments={"repoName": REPO},
            fields=["result"],
            permitted_endpoint="read_wiki_structure",
        )

        # Run all three through the unchanged native bound executor and the
        # same exact registry generation. Distinct semantics stay separate.
        plan = ExecutionPlan(
            query="host-pinned public source-specific interoperability checks",
            registry_version=router.registry.version,
            calls=[crossref_call, cod_call, mcp_call],
        )
        results = await router.execute(plan)
        if len(results) != 3 or any(
            result.tool != call.tool or result.endpoint != call.endpoint
            for result, call in zip(results, plan.calls, strict=True)
        ):
            raise ValueError("native multi-provider execution result mismatch")

        crossref_doi = validate_crossref_work(results[0].data, expected_doi=DOI)
        cod_rows = validate_optimade_structure(results[1].data)
        wiki_blocks = validate_deepwiki_mcp_result(results[2].data)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
            headers={
                "User-Agent": "SchemaRouter public research (https://github.com/JDeun/SchemaRouter)"
            },
        ) as client:
            pmc_matches = await crosscheck_europe_pmc(client, crossref_doi)

        return {
            "evidence_tier": "E1_LIVE_SOURCE_SHAPED_NO_INDEPENDENT_E2",
            "live": True,
            "registry_tool_count": len(router.registry.keys()),
            "registered_access_modes": sorted(
                {tool.access_mode or "undeclared" for tool in (crossref, cod, deepwiki)}
            ),
            "native_execution_count": len(results),
            # Registration/discovery performs additional real network reads.
            # Count only the 3 native task calls plus the 1 independent DOI hop.
            "task_endpoint_invocations": 4,
            "host_selected_calls": True,
            "model_selected_calls": 0,
            "independent_gold_e2": False,
            "tasks": {
                "crossref_europe_pmc_doi_match": {"passed": True, "matching_results": pmc_matches},
                "cod_optimade_si_o_structure": {"passed": True, "valid_source_rows": cod_rows},
                "deepwiki_remote_mcp_structure": {"passed": True, "validated_blocks": wiki_blocks},
            },
            "total_wall_seconds": round(perf_counter() - started, 2),
        }
    finally:
        await router.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="opt in to real unauthenticated HTTP/MCP reads"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("real-source matrix is opt-in: pass --live")
    # Some upstream MCP SDK exception logs embed the untrusted JSON instance.
    # Research receipts do not need those logs; keep public CI source-private.
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(run_live_anonymous_source_matrix())
    except Exception as exc:
        print(json.dumps({"live": True, "status": "failure", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    finally:
        logging.disable(previous_logging_disable)
    print(json.dumps({"status": "success", **result}, sort_keys=True))


if __name__ == "__main__":
    main()

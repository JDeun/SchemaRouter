"""Offline source-shaped safety regressions for anonymous real protocol tasks."""

from __future__ import annotations

import httpx
import pytest

from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec


def test_public_crossref_doi_is_verified_before_second_source() -> None:
    from scripts.research_public_heterogeneous_live_e1 import validate_crossref_work

    sample = {
        "status": "ok",
        "message-type": "work",
        "message": {
            "DOI": "10.1038/nature12373",
            "title": ["Nanometre-scale thermometry in a living cell"],
            "type": "journal-article",
        },
    }
    assert validate_crossref_work(sample, expected_doi="10.1038/nature12373") == (
        "10.1038/nature12373"
    )
    with pytest.raises(ValueError, match="DOI|mismatch"):
        validate_crossref_work(sample, expected_doi="10.1038/nature99999")
    with pytest.raises(ValueError, match="title|work|metadata"):
        validate_crossref_work(
            {"message": {"DOI": "10.1038/nature12373"}}, expected_doi="10.1038/nature12373"
        )


def test_europe_pmc_doi_requires_matching_actual_article() -> None:
    from scripts.research_public_heterogeneous_live_e1 import validate_europe_pmc_doi

    result = {
        "hitCount": 1,
        "resultList": {
            "result": [{"id": "23903748", "source": "MED", "doi": "10.1038/nature12373"}],
        },
    }
    assert validate_europe_pmc_doi(result, expected_doi="10.1038/nature12373") == 1
    with pytest.raises(ValueError, match="DOI|match|result"):
        validate_europe_pmc_doi(result, expected_doi="10.1038/nature99999")
    with pytest.raises(ValueError, match="DOI|match|result"):
        validate_europe_pmc_doi(
            {"hitCount": 0, "resultList": {"result": []}}, expected_doi="10.1038/nature12373"
        )


@pytest.mark.parametrize(
    "wrong_row",
    (
        {
            "id": "1010921",
            "chemical_formula_descriptive": "O2Si",
            "nelements": 3,
            "elements": ["O", "Si"],
        },
        {
            "id": "1010921",
            "chemical_formula_descriptive": "O2Si",
            "nelements": 2,
            "elements": ["O", "C"],
        },
        {"id": "", "chemical_formula_descriptive": "O2Si", "nelements": 2, "elements": ["O", "Si"]},
    ),
)
def test_optimade_structure_requires_real_si_o_identity(wrong_row: dict) -> None:
    from scripts.research_public_heterogeneous_live_e1 import validate_optimade_structure

    valid = {
        "id": "1010921",
        "chemical_formula_descriptive": "O2Si",
        "nelements": 2,
        "elements": ["O", "Si"],
    }
    assert validate_optimade_structure([valid]) == 1
    with pytest.raises(ValueError, match="structure|element|identity|formula"):
        validate_optimade_structure([wrong_row])


def test_mcp_wiki_result_rejects_error_and_oversized_payloads() -> None:
    from scripts.research_public_heterogeneous_live_e1 import validate_deepwiki_mcp_result

    valid = (
        "Available pages for modelcontextprotocol/servers:\n\n"
        "- 1 Introduction to Model Context Protocol Servers\n"
        "  - 1.1 MCP Protocol and Architecture\n"
        "- 2 Reference Servers Overview\n"
    )
    assert validate_deepwiki_mcp_result({"result": valid}) == 1
    with pytest.raises(ValueError, match="MCP|wiki|content"):
        validate_deepwiki_mcp_result([{"type": "error", "text": "not available"}])
    with pytest.raises(ValueError, match="MCP|wiki|content"):
        validate_deepwiki_mcp_result({"result": "x" * 200000})
    with pytest.raises(ValueError, match="MCP|wiki|content"):
        validate_deepwiki_mcp_result([])


def test_actual_fastmcp_declared_result_string_projection_is_validated() -> None:
    from scripts.research_public_heterogeneous_live_e1 import validate_deepwiki_mcp_result

    # Live DeepWiki tools/list advertises outputSchema.result: string;
    # SchemaRouter projects that declared field, not the raw MCP block list.
    projected = {
        "result": (
            "Available pages for modelcontextprotocol/servers:\n"
            "- 1 Introduction\n"
            "- 2 Reference Servers Overview"
        )
    }
    assert validate_deepwiki_mcp_result(projected) == 1
    with pytest.raises(ValueError, match="MCP|wiki|content"):
        validate_deepwiki_mcp_result({"result": "x" * 200000})
    with pytest.raises(ValueError, match="MCP|wiki|content"):
        validate_deepwiki_mcp_result(
            {"result": "a valid overview of the repository", "extra": True}
        )
    for wrong in (
        "Repository not found: modelcontextprotocol/servers",
        "The wiki is temporarily unavailable; please try again later",
        "Available pages for some-other-owner/repo:\n- 1 Introduction\n- 2 Contents",
        "Available pages for modelcontextprotocol/servers:\nNo pages available",
    ):
        with pytest.raises(ValueError, match="MCP|wiki|content"):
            validate_deepwiki_mcp_result({"result": wrong})


def test_source_pinned_calls_require_expected_read_endpoint_and_projection() -> None:
    from scripts.research_public_heterogeneous_live_e1 import checked_call

    endpoint = EndpointSpec(
        name="get_work",
        method="GET",
        path="/works/{doi}",
        read_only=True,
        destructive=False,
        parameters=[ParameterSpec(name="doi", location="path", required=True)],
        output_fields=[FieldSpec(name="message", json_schema={"type": "object"})],
    )
    write_endpoint = EndpointSpec(
        name="write_work",
        method="POST",
        path="/works",
        read_only=False,
        destructive=False,
        output_fields=[FieldSpec(name="message", json_schema={"type": "object"})],
    )
    tool = ToolSpec(name="crossref", provider="crossref", endpoints=[endpoint, write_endpoint])
    good = checked_call(
        tool,
        endpoint="get_work",
        arguments={"doi": "10.1038/nature12373"},
        fields=["message"],
        permitted_endpoint="get_work",
    )
    assert good.endpoint == "get_work" and good.schema_fingerprint == endpoint.fingerprint
    with pytest.raises(ValueError, match="allowlist|safe|endpoint"):
        checked_call(
            tool,
            endpoint="write_work",
            arguments={},
            fields=["message"],
            permitted_endpoint="get_work",
        )
    with pytest.raises(ValueError, match="projection|field"):
        checked_call(
            tool,
            endpoint="get_work",
            arguments={"doi": "10.1038/nature12373"},
            fields=["undeclared"],
            permitted_endpoint="get_work",
        )
    with pytest.raises(ValueError, match="input|argument"):
        checked_call(
            tool,
            endpoint="get_work",
            arguments={"doi": "10.1038/nature12373", "evil": "yes"},
            fields=["message"],
            permitted_endpoint="get_work",
        )


@pytest.mark.asyncio
async def test_europe_pmc_live_hop_is_checked_not_assumed_from_http_200() -> None:
    from scripts.research_public_heterogeneous_live_e1 import crosscheck_europe_pmc

    payload = {
        "hitCount": 1,
        "resultList": {"result": [{"id": "23903748", "doi": "10.1038/nature12373"}]},
    }
    observed = []

    def serve(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        assert await crosscheck_europe_pmc(client, "10.1038/nature12373") == 1
    assert len(observed) == 1
    assert str(observed[0].url).startswith(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
    )
    assert observed[0].url.params["pageSize"] == "1"

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"hitCount": 0, "resultList": {"result": []}})
        )
    ) as client:
        with pytest.raises(ValueError, match="DOI|match|result"):
            await crosscheck_europe_pmc(client, "10.1038/nature12373")


@pytest.mark.asyncio
async def test_europe_pmc_enforces_content_and_response_limits() -> None:
    from scripts.research_public_heterogeneous_live_e1 import crosscheck_europe_pmc

    for response in (
        httpx.Response(200, text="invalid", headers={"content-type": "text/plain"}),
        httpx.Response(200, content=b"x" * 300000, headers={"content-type": "application/json"}),
        httpx.Response(503, json={"message": "unavailable"}),
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _, r=response: r)
        ) as client:
            with pytest.raises(
                (ValueError, httpx.HTTPStatusError), match="provider|content|response|HTTP|status"
            ):
                await crosscheck_europe_pmc(client, "10.1038/nature12373")


@pytest.mark.asyncio
async def test_europe_pmc_streaming_stops_before_fetching_more_oversized_chunks() -> None:
    from scripts.research_public_heterogeneous_live_e1 import (
        MAX_HTTP_CONTENT_BYTES,
        crosscheck_europe_pmc,
    )

    class ChunkedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * (MAX_HTTP_CONTENT_BYTES + 1)
            raise AssertionError("over-budget provider bytes must never be pulled")

    def serve(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, stream=ChunkedBody(), headers={"content-type": "application/json"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        with pytest.raises(ValueError, match="provider|response|byte"):
            await crosscheck_europe_pmc(client, "10.1038/nature12373")


def test_live_cli_redacts_remote_failure_messages(monkeypatch, capsys) -> None:
    import sys

    from scripts import research_public_heterogeneous_live_e1 as research

    sentinel = "UNTRUSTED_WIKI_BODY_SENTINEL"

    async def fail():
        raise RuntimeError(f"invalid structured response: {sentinel}")

    monkeypatch.setattr(research, "run_live_anonymous_source_matrix", fail)
    monkeypatch.setattr(sys, "argv", ["research_public_heterogeneous_live_e1", "--live"])
    with pytest.raises(SystemExit) as exc:
        research.main()
    assert exc.value.code == 1
    output = capsys.readouterr()
    assert sentinel not in (output.out + output.err)
    assert '"status": "failure"' in output.out
    assert output.err == ""


@pytest.mark.asyncio
async def test_remote_mcp_http_stream_is_capped_before_sdk_buffers() -> None:
    try:
        import httpx2
    except ImportError:
        pytest.skip("requires optional mcp HTTP transport dependency")
    from scripts.research_public_heterogeneous_live_e1 import (
        MAX_MCP_WIRE_BYTES,
        limit_mcp_http_response,
    )

    class OversizedStream(httpx2.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * (MAX_MCP_WIRE_BYTES + 1)
            raise AssertionError("MCP transport must stop after first oversize chunk")

    def serve(_: httpx2.Request):
        return httpx2.Response(200, stream=OversizedStream())

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(serve),
        event_hooks={"response": [limit_mcp_http_response]},
    ) as client:
        with pytest.raises(ValueError, match="MCP|response|wire"):
            await client.get("https://mcp.deepwiki.com/mcp")


@pytest.mark.asyncio
async def test_mcp_rejects_compressed_responses_before_unbounded_decoding() -> None:
    import gzip

    try:
        import httpx2
    except ImportError:
        pytest.skip("requires optional mcp HTTP transport dependency")
    from scripts.research_public_heterogeneous_live_e1 import (
        MAX_MCP_WIRE_BYTES,
        limit_mcp_http_response,
    )

    bomb = gzip.compress(b"x" * (MAX_MCP_WIRE_BYTES * 4))
    assert len(bomb) < MAX_MCP_WIRE_BYTES

    def serve(_: httpx2.Request):
        return httpx2.Response(200, content=bomb, headers={"content-encoding": "gzip"})

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(serve),
        event_hooks={"response": [limit_mcp_http_response]},
    ) as client:
        with pytest.raises(ValueError, match="MCP|encoding|compressed"):
            await client.get("https://mcp.deepwiki.com/mcp")


@pytest.mark.asyncio
async def test_bounded_mcp_factory_rejects_another_host_before_connection() -> None:
    from scripts.research_public_heterogeneous_live_e1 import bounded_public_mcp_client_factory

    with pytest.raises(ValueError, match="MCP|host|source"):
        async with bounded_public_mcp_client_factory("https://evil.example/mcp"):
            raise AssertionError("a non-pinned MCP URL must never connect")

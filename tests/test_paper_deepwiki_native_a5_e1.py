"""Actual DeepWiki scalar-result MCP discovery → reviewed native A5 E1."""

from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    ExecutionPolicy,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import NonRetryableInvocationError, SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_deepwiki_registration import (
    DEEPWIKI_MCP_URL,
    inspect_deepwiki_paper_source,
    register_reviewed_deepwiki_paper_source,
)
from scripts.research_paper_deepwiki_native_e1 import (
    probe_deepwiki_paper_a5,
    run_deepwiki_paper_a5,
)

REPO = "modelcontextprotocol/servers"
OUTLINE = (
    f"Available pages for {REPO}:\n"
    "- 1 Overview\n- 2 Reference\n- 2.1 Tools\n"
)


class SourceShapedMCP:
    """Observed DeepWiki selected-tool schema; unrelated tools are synthetic."""

    def __init__(self) -> None:
        self.tools: list[dict[str, Any]] = [
            {
                "name": "read_wiki_structure",
                "description": "Get a list of documentation topics for a GitHub repository.",
                # Actual public tools/list omits behavior annotations.
                "inputSchema": {
                    "type": "object",
                    "properties": {"repoName": {
                        "type": "string",
                        "description": (
                            'GitHub repository in owner/repo format '
                            '(e.g. "facebook/react").'
                        ),
                    }},
                    "required": ["repoName"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "x-fastmcp-wrap-result": True,
                },
            },
            {
                "name": "ask_question",
                "inputSchema": {
                    "type": "object", "properties": {"question": {"type": "string"}},
                    "required": ["question"],
                },
                "outputSchema": {"type": "object", "properties": {}},
            },
        ]
        self.outline: object = OUTLINE
        self.discovery_calls = 0
        self.provider_calls: list[tuple[str, dict[str, Any]]] = []
        self.urls: list[str] = []
        self.client = SimpleNamespace(
            server_info=SimpleNamespace(name="deepwiki-mcp"),
            protocol_version="2026-06-18",
        )
        self.client.list_tools = self.list_tools
        self.client.call_tool = self.call_tool

    async def list_tools(self, *, cursor=None):
        assert cursor is None
        self.discovery_calls += 1
        return SimpleNamespace(tools=deepcopy(self.tools), next_cursor=None)

    async def call_tool(self, endpoint: str, arguments: dict[str, Any]):
        self.provider_calls.append((endpoint, dict(arguments)))
        return SimpleNamespace(
            is_error=False, structured_content={"result": self.outline},
        )

    @asynccontextmanager
    async def __call__(self, url: str, *, headers=None, timeout=20.0):
        assert headers is None
        assert timeout > 0
        self.urls.append(url)
        yield self.client


def _router() -> SchemaRouter:
    return SchemaRouter(
        network_policy=NetworkPolicy.trusted_internal(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation="deepwiki.read_wiki_structure",
                              roles_any=("reader",)),
        )),
    )


@pytest.mark.asyncio
async def test_two_phase_discovery_and_host_review_wires_only_native_scalar_result():
    source = SourceShapedMCP()
    probe = await inspect_deepwiki_paper_source(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    assert probe.url == DEEPWIKI_MCP_URL
    assert probe.source_fingerprint
    assert "read_wiki_structure" in probe.available_endpoints
    assert probe.output_fields == ("result",)
    assert source.provider_calls == []

    router = _router()
    approved = await register_reviewed_deepwiki_paper_source(
        router,
        expected_source_fingerprint=probe.source_fingerprint,
        expected_url=probe.url,
        license="source-license-unverified-research-only",
        reviewed_by="research-owner-manual-review",
        client_factory=source,
    )
    assert router.registry.keys() == ("deepwiki",)
    assert approved.source_type == "mcp_deepwiki"
    assert len(approved.endpoints) == 1
    endpoint = approved.endpoint("read_wiki_structure")
    assert endpoint.read_only is True and endpoint.destructive is False
    assert endpoint.output_fields[0].semantic_id == "wiki.outline"
    assert endpoint.output_fields[0].identifier is False
    assert endpoint.parameters[0].semantic_id == "wiki.repository_id"
    assert endpoint.input_schema["additionalProperties"] is False

    result = await router.execute(ExecutionPlan(
        query="source-owned wiki outline",
        registry_version=router.registry.version,
        calls=[ToolCall(
            tool="deepwiki", endpoint="read_wiki_structure",
            arguments={"repoName": REPO}, fields=["result"],
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=approved.fingerprint,
        )],
    ), config={"principal": PrincipalContext(
        subject="reviewed", roles=("reader",),
    ).model_dump()})
    assert result[0].data == {"result": OUTLINE}
    assert source.provider_calls == [("read_wiki_structure", {"repoName": REPO})]
    assert all(url == DEEPWIKI_MCP_URL for url in source.urls)


@pytest.mark.asyncio
async def test_stale_discovery_fingerprint_or_wrong_url_cannot_register():
    source = SourceShapedMCP()
    probe = await inspect_deepwiki_paper_source(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    source.tools[0]["outputSchema"]["properties"]["result"] = {"type": "integer"}
    router = _router()
    with pytest.raises(SchemaSourceError, match="fingerprint"):
        await register_reviewed_deepwiki_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_url=DEEPWIKI_MCP_URL,
            license="source-license-unverified-research-only", reviewed_by="owner",
            client_factory=source,
        )
    assert router.registry.keys() == ()
    assert source.provider_calls == []
    with pytest.raises(SchemaSourceError, match="URL"):
        await register_reviewed_deepwiki_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_url="https://other.example/mcp",
            license="source-license-unverified-research-only", reviewed_by="owner",
            client_factory=source,
        )


@pytest.mark.asyncio
async def test_mcp_annotation_drift_invalidates_separately_reviewed_source_snapshot():
    source = SourceShapedMCP()
    probe = await inspect_deepwiki_paper_source(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    source.tools[0]["annotations"] = {
        "readOnlyHint": False, "destructiveHint": True,
    }
    router = _router()
    with pytest.raises(SchemaSourceError, match="fingerprint"):
        await register_reviewed_deepwiki_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_url=DEEPWIKI_MCP_URL,
            license="source-license-unverified-research-only", reviewed_by="owner",
            client_factory=source,
        )
    assert router.registry.keys() == ()
    assert source.provider_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("alteration", [
    "missing_result", "extra_input", "complex_result", "constrained_parameter",
    "constrained_envelope", "constrained_output",
])
async def test_unreviewable_source_contract_abstains_without_execution(alteration: str):
    source = SourceShapedMCP()
    current = source.tools[0]
    if alteration == "missing_result":
        current["outputSchema"] = {"type": "object", "properties": {}}
    elif alteration == "extra_input":
        current["inputSchema"]["properties"]["path"] = {"type": "string"}
    elif alteration == "constrained_parameter":
        current["inputSchema"]["properties"]["repoName"]["pattern"] = "^private/"
    elif alteration == "constrained_envelope":
        current["inputSchema"]["allOf"] = [{"required": ["hidden"]}]
    elif alteration == "constrained_output":
        current["outputSchema"]["oneOf"] = [{"required": ["secret"]}]
    else:
        current["outputSchema"]["properties"]["result"] = {"type": "array"}
    probe = await inspect_deepwiki_paper_source(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    router = _router()
    with pytest.raises(SchemaSourceError, match="contract"):
        await register_reviewed_deepwiki_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_url=DEEPWIKI_MCP_URL,
            license="source-license-unverified-research-only", reviewed_by="owner",
            client_factory=source,
        )
    assert router.registry.keys() == ()
    assert source.provider_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [
    "Available pages for attacker/other:\n- 1 Overview\n- 2 Reference",
    f"Available pages for {REPO}:\nno pages",
    "x" * 131073,
])
async def test_native_invoker_rejects_wrong_identity_or_invalid_outline(output: str):
    source = SourceShapedMCP()
    probe = await inspect_deepwiki_paper_source(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    router = _router()
    approved = await register_reviewed_deepwiki_paper_source(
        router, expected_source_fingerprint=probe.source_fingerprint,
        expected_url=probe.url,
        license="source-license-unverified-research-only", reviewed_by="owner",
        client_factory=source,
    )
    source.outline = output
    with pytest.raises(NonRetryableInvocationError, match="outline"):
        await router.execute(ExecutionPlan(
            query="read wiki", registry_version=router.registry.version,
            calls=[ToolCall(
                tool="deepwiki", endpoint="read_wiki_structure",
                arguments={"repoName": REPO}, fields=["result"],
                schema_fingerprint=approved.endpoint("read_wiki_structure").fingerprint,
                tool_fingerprint=approved.fingerprint,
            )],
        ), config={"principal": PrincipalContext(
            subject="reader", roles=("reader",),
        ).model_dump()})
    assert len(source.provider_calls) == 1


@pytest.mark.asyncio
async def test_original_understand_p2_a5_executes_host_repo_not_agent_forgery():
    source = SourceShapedMCP()
    probe = await probe_deepwiki_paper_a5(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    assert source.provider_calls == []
    receipt = await run_deepwiki_paper_a5(
        expected_source_fingerprint=probe.source_fingerprint,
        host_repo=REPO,
        client_factory=source,
        network_policy=NetworkPolicy.trusted_internal(),
    )
    assert receipt.repository == REPO
    assert receipt.outline == OUTLINE
    assert receipt.route_id == "deepwiki.read_wiki_structure"
    assert receipt.host_bound_tool_calls == 1
    assert receipt.independent_e2 is False
    assert source.provider_calls == [("read_wiki_structure", {"repoName": REPO})]


@pytest.mark.asyncio
async def test_invalid_host_repository_abstains_before_mcp_discovery():
    source = SourceShapedMCP()
    with pytest.raises(SchemaSourceError, match="repository"):
        await run_deepwiki_paper_a5(
            expected_source_fingerprint="0" * 64,
            host_repo="https://127.0.0.1/admin",
            client_factory=source,
            network_policy=NetworkPolicy.trusted_internal(),
        )
    assert source.urls == []


@pytest.mark.asyncio
async def test_paper_e1_refuses_unverified_runtime_outline_not_a_success_receipt():
    source = SourceShapedMCP()
    probe = await probe_deepwiki_paper_a5(
        client_factory=source, network_policy=NetworkPolicy.trusted_internal(),
    )
    source.outline = f"Available pages for {REPO}:\nno pages"
    with pytest.raises(NonRetryableInvocationError, match="outline"):
        await run_deepwiki_paper_a5(
            expected_source_fingerprint=probe.source_fingerprint,
            host_repo=REPO,
            client_factory=source,
            network_policy=NetworkPolicy.trusted_internal(),
        )
    assert len(source.provider_calls) == 1

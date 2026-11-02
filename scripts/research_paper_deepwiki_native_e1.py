"""Manual keyless DeepWiki MCP → original P2/A5 → native ToolCall E1.

Probe only discovers untrusted remote tools/list. Run requires a fingerprint
reviewed separately by the host; neither phase is independent model E2.

    python -m scripts.research_paper_deepwiki_native_e1 probe
    python -m scripts.research_paper_deepwiki_native_e1 run \
      --expected-source-fingerprint <approved-digest> \
      --host-repo modelcontextprotocol/servers
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    ExecutionPolicy,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PrincipalContext,
    SchemaRouter,
    inspect_deepwiki_paper_source,
    register_reviewed_deepwiki_paper_source,
)
from schemarouter.adapters.mcp import MCPClientFactory
from schemarouter.errors import SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_deepwiki_registration import (
    DEEPWIKI_MCP_URL,
    DEEPWIKI_RESEARCH_LICENSE,
    DeepWikiPaperSourceProbe,
    validate_deepwiki_outline,
    validate_host_deepwiki_repo,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_scoped_native_direct_e1 import (
    run_paper_scoped_native_direct_e1,
)

ROUTE = "deepwiki.read_wiki_structure"
INTENT = "wiki.lookup"
CONCEPT = "wiki.outline"
DEFAULT_REPO = "modelcontextprotocol/servers"
PRINCIPAL = PrincipalContext(subject="deepwiki-paper-a5-research", roles=("reader",))


@dataclass(frozen=True, slots=True)
class DeepWikiPaperA5E1:
    repository: str
    outline: str
    route_id: str
    host_bound_tool_calls: int
    independent_e2: bool = False


class _ScriptedDeepWikiAgent:
    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del messages
        # Generated/provider parameters are NOT the trusted host argument.
        forged = {"name": tools[0]["name"],
                  "arguments": {"repoName": "attacker/forged"}}
        return {
            "text": f"<tool_call>{json.dumps(forged)}</tool_call>",
            "context_overflow": False,
        }


def _scripted_understanding(_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_id": INTENT,
        "concept_ids": [CONCEPT],
        "named_tools": ["deepwiki"],
        "parameter_hints": {"repoName": "attacker/forged"},
    }


async def probe_deepwiki_paper_a5(
    *,
    client_factory: MCPClientFactory | None = None,
    network_policy: NetworkPolicy | None = None,
) -> DeepWikiPaperSourceProbe:
    return await inspect_deepwiki_paper_source(
        client_factory=client_factory, network_policy=network_policy,
    )


async def run_deepwiki_paper_a5(
    *,
    expected_source_fingerprint: str,
    host_repo: str,
    client_factory: MCPClientFactory | None = None,
    network_policy: NetworkPolicy | None = None,
) -> DeepWikiPaperA5E1:
    """Host-pin one reviewed repository through original P2/A5 native E1."""
    validated_repo = validate_host_deepwiki_repo(host_repo)
    router = SchemaRouter(
        network_policy=network_policy or NetworkPolicy.public_only(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(
                effect="allow", operation=ROUTE, roles_any=("reader",),
            ),
        )),
    )
    approved = await register_reviewed_deepwiki_paper_source(
        router,
        expected_source_fingerprint=expected_source_fingerprint,
        expected_url=DEEPWIKI_MCP_URL,
        license=DEEPWIKI_RESEARCH_LICENSE,
        reviewed_by="deepwiki-native-a5-research-host",
        client_factory=client_factory,
    )
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=CONCEPT,
        aliases=("repository wiki outline", "저장소 위키 구조", "リポジトリ目次"),
        required_fields=(CapabilityFieldContract(
            semantic_id=CONCEPT, json_schema={"type": "string"},
        ),),
        source_type="mcp_deepwiki", license=DEEPWIKI_RESEARCH_LICENSE,
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id=INTENT, required_concept_ids=(CONCEPT,),
    ),))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({ROUTE}),
    )
    if graph.graph.edges:
        raise SchemaSourceError("DeepWiki scalar-only source cannot justify G5 joins")
    view = capture_authorized_agent_tool_surface(
        router, "Read the wiki outline for the independently host-selected repository",
        principal=PRINCIPAL,
    )
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _scripted_understanding, _ScriptedDeepWikiAgent(),
        view=view, catalog=catalog, intent_registry=intents, index=graph,
        model_visible_intent_ids=(INTENT,),
        model_visible_concept_ids=(CONCEPT,),
        expected_route_id=ROUTE,
        host_source_arguments={ROUTE: {"repoName": validated_repo}},
    )
    if decision != "offer" or receipt is None or receipt.route_id != ROUTE:
        raise SchemaSourceError("DeepWiki original P2/A5 refused reviewed source route")
    result = receipt.result.data
    outline = validate_deepwiki_outline(validated_repo, result)
    if approved.key != "deepwiki":
        raise SchemaSourceError("DeepWiki reviewed tool identity changed")
    return DeepWikiPaperA5E1(
        repository=validated_repo,
        outline=outline,
        route_id=receipt.route_id,
        host_bound_tool_calls=receipt.host_bound_tool_calls,
    )


async def _cli(args: argparse.Namespace) -> None:
    # All calls are anonymous, read-only, bounded Streamable HTTP.
    from scripts.research_public_heterogeneous_live_e1 import (
        bounded_public_mcp_client_factory,
    )

    if args.phase == "probe":
        result = await probe_deepwiki_paper_a5(
            client_factory=bounded_public_mcp_client_factory,
        )
    else:
        if not args.expected_source_fingerprint:
            raise ValueError("--expected-source-fingerprint from prior host review required")
        result = await run_deepwiki_paper_a5(
            expected_source_fingerprint=args.expected_source_fingerprint,
            host_repo=args.host_repo,
            client_factory=bounded_public_mcp_client_factory,
        )
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "run"))
    parser.add_argument("--expected-source-fingerprint")
    parser.add_argument("--host-repo", default=DEFAULT_REPO)
    asyncio.run(_cli(parser.parse_args()))

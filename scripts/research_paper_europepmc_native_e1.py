"""Keyless Europe PMC DOI search → original P2 → native A5 ToolCall (E1).

    python -m scripts.research_paper_europepmc_native_e1 probe
    python -m scripts.research_paper_europepmc_native_e1 run \
      --expected-source-fingerprint <host-reviewed-digest> \
      --host-doi 10.1038/nature12373

Scripted model output is a deterministic E1 adversarial fixture, not E2.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx

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
    inspect_europepmc_paper_source,
    register_reviewed_europepmc_paper_source,
)
from schemarouter.errors import SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_europepmc_registration import (
    EUROPEPMC_BASE_URL,
    EUROPEPMC_LICENSE,
    EuropePMCPaperSourceProbe,
    validate_host_europepmc_query,
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

EUROPEPMC_DOI = "10.1038/nature12373"
ROUTE = "europepmc.search_doi"
INTENT = "paper.lookup"
CONCEPT = "paper.europepmc_verified_search"
PRINCIPAL = PrincipalContext(subject="europepmc-paper-a5-research", roles=("reader",))


@dataclass(frozen=True, slots=True)
class EuropePMCPaperA5E1:
    doi: str
    record_id: str
    hit_count: int
    route_id: str
    host_bound_tool_calls: int
    independent_e2: bool = False


class _ForgedParameterAgent:
    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del messages
        forged = {
            "name": tools[0]["name"],
            "arguments": {"query": "DOI:10.0000/agent-forged", "format": "xml",
                          "pageSize": 99},
        }
        return {
            "text": f"<tool_call>{json.dumps(forged)}</tool_call>",
            "context_overflow": False,
        }


def _scripted_understanding(_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_id": INTENT,
        "concept_ids": [CONCEPT],
        "named_tools": ["europepmc"],
        "parameter_hints": {"query": "DOI:10.0000/agent-forged"},
    }


async def probe_europepmc_paper_a5() -> EuropePMCPaperSourceProbe:
    """Inspect only the curated local manifest; no remote schema verification."""
    return inspect_europepmc_paper_source()


async def run_europepmc_paper_a5(
    *,
    expected_source_fingerprint: str,
    host_doi: str,
    http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
) -> EuropePMCPaperA5E1:
    """Execute one source-checked native GET after explicit host review."""
    doi = validate_host_europepmc_query(f"DOI:{host_doi}")
    router = SchemaRouter(
        http_client=http_client,
        network_policy=network_policy or NetworkPolicy.public_only(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation=ROUTE, roles_any=("reader",)),
        )),
    )
    approved = register_reviewed_europepmc_paper_source(
        router,
        expected_source_fingerprint=expected_source_fingerprint,
        expected_base_url=EUROPEPMC_BASE_URL,
        license=EUROPEPMC_LICENSE,
        reviewed_by="europepmc-native-a5-research-host",
    )
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=CONCEPT,
        aliases=("Europe PMC paper DOI", "유럽 PMC 논문 DOI", "欧州PMC論文DOI"),
        required_fields=(
            CapabilityFieldContract(
                semantic_id="paper.doi", json_schema={"type": "string"},
            ),
            CapabilityFieldContract(
                semantic_id="paper.europepmc_record_id", json_schema={"type": "string"},
            ),
            CapabilityFieldContract(
                semantic_id="paper.search_hit_count", json_schema={"type": "integer"},
            ),
        ),
        source_type="europepmc",
        license=EUROPEPMC_LICENSE,
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id=INTENT,
        required_concept_ids=(CONCEPT,),
    ),))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({ROUTE}),
    )
    view = capture_authorized_agent_tool_surface(
        router, "Look up the host-selected Europe PMC DOI", principal=PRINCIPAL,
    )
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _scripted_understanding, _ForgedParameterAgent(),
        view=view,
        index=graph,
        catalog=catalog,
        intent_registry=intents,
        model_visible_intent_ids=(INTENT,),
        model_visible_concept_ids=(CONCEPT,),
        expected_route_id=ROUTE,
        host_source_arguments={ROUTE: {
            "query": f"DOI:{doi}", "format": "json", "pageSize": 1,
        }},
    )
    if decision != "offer" or receipt is None or receipt.route_id != ROUTE:
        raise SchemaSourceError("Europe PMC original P2/A5 refused reviewed typed route")
    data = receipt.result.data
    if not isinstance(data, dict):
        raise SchemaSourceError("Europe PMC A5 receipt must be an object")
    result_list = data.get("resultList")
    rows = result_list.get("result") if isinstance(result_list, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise SchemaSourceError("Europe PMC A5 receipt lacks provider DOI row")
    record = rows[0]
    if (
        type(data.get("hitCount")) is not int
        or data["hitCount"] < 1
        or type(record.get("doi")) is not str
        or record["doi"].casefold() != doi.casefold()
        or type(record.get("id")) is not str
        or not record["id"].strip()
        or approved.key != "europepmc"
    ):
        raise SchemaSourceError("Europe PMC A5 source identity is invalid")
    return EuropePMCPaperA5E1(
        doi=record["doi"],
        record_id=record["id"],
        hit_count=data["hitCount"],
        route_id=receipt.route_id,
        host_bound_tool_calls=receipt.host_bound_tool_calls,
    )


async def _cli(args: argparse.Namespace) -> None:
    if args.phase == "probe":
        result = await probe_europepmc_paper_a5()
    else:
        if not args.expected_source_fingerprint:
            raise ValueError("a separately host-approved source fingerprint is required")
        result = await run_europepmc_paper_a5(
            expected_source_fingerprint=args.expected_source_fingerprint,
            host_doi=args.host_doi,
        )
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "run"))
    parser.add_argument("--expected-source-fingerprint")
    parser.add_argument("--host-doi", default=EUROPEPMC_DOI)
    asyncio.run(_cli(parser.parse_args()))

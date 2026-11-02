"""Keyless COD OPTIMADE A5 real-provider E1 pilot (explicit opt-in only).

``probe`` inspects unreviewed source metadata. ``run`` requires its **prior
host-approved** fingerprint; it searches for one source ID using a host-owned
filter and runs the existing original-paper P2 → agent A5 → native GET path.
The example's model/agent are deterministic scripts, not independent E2.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    ExecutionPlan,
    ExecutionPolicy,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
)
from schemarouter.errors import SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_optimade_registration import (
    discover_optimade_paper_source,
    register_reviewed_optimade_paper_source,
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
from scripts.research_public_heterogeneous_live_e1 import (
    COD_FILTER,
    validate_optimade_structure,
)

COD_OPTIMADE_URL = "https://www.crystallography.net/cod/optimade"
COD_VERSIONED_URL = f"{COD_OPTIMADE_URL}/v1"
COD_TOOL_NAME = "cod_a5"
COD_RESEARCH_LICENSE = "source-license-unverified-research-only"
COD_FORMULA = "chemical_formula_descriptive"
COD_ROUTE = f"{COD_TOOL_NAME}.get_structures"
COD_SEARCH_ROUTE = f"{COD_TOOL_NAME}.search_structures"
COD_INTENT = "materials.lookup"
COD_CONCEPT = "materials.formula"
PRINCIPAL = PrincipalContext(subject="cod-paper-a5-research", roles=("reader",))


@dataclass(frozen=True, slots=True)
class CODPaperSourceProbe:
    source_fingerprint: str
    versioned_base_url: str
    available_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CODPaperA5E1:
    route_id: str
    source_id: str
    formula: str
    host_bound_tool_calls: int
    independent_e2: bool = False


class _ScriptedA5Agent:
    def generate(self, messages: list[dict[str, str]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        del messages
        # Deliberately forge an ID. Host-owned P2 binding must overwrite it.
        payload = {"name": tools[0]["name"], "arguments": {"id": "model-forged-id"}}
        return {"text": f"<tool_call>{json.dumps(payload)}</tool_call>",
                "context_overflow": False}


def _scripted_understanding(_payload: dict[str, Any]) -> dict[str, Any]:
    return {"intent_id": COD_INTENT, "concept_ids": [COD_CONCEPT],
            "named_tools": [COD_TOOL_NAME], "parameter_hints": {}}


async def probe_cod_optimade_paper_a5(
    *, http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
) -> CODPaperSourceProbe:
    tool, _invoker = await discover_optimade_paper_source(
        url=COD_OPTIMADE_URL, name=COD_TOOL_NAME,
        http_client=http_client, network_policy=network_policy,
    )
    get = tool.endpoint("get_structures")
    return CODPaperSourceProbe(
        source_fingerprint=tool.fingerprint,
        versioned_base_url=str(tool.metadata["versioned_base_url"]),
        available_fields=tuple(field.name for field in get.output_fields),
    )


async def run_cod_optimade_paper_a5(
    *, expected_source_fingerprint: str,
    http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
) -> CODPaperA5E1:
    """Host-approved live single-record A5; source-of-truth stays native COD.

    Search is a distinct *host-selected* preflight request, not an A5 call.
    ``expected_source_fingerprint`` must come from a prior probe/review.
    """
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation=COD_ROUTE, roles_any=("reader",)),
            AuthorizationRule(effect="allow", operation=COD_SEARCH_ROUTE,
                              roles_any=("reader",)),
        )),
    )
    reviewed = await register_reviewed_optimade_paper_source(
        router, url=COD_OPTIMADE_URL, name=COD_TOOL_NAME,
        expected_fingerprint=expected_source_fingerprint,
        expected_versioned_base_url=COD_VERSIONED_URL,
        license=COD_RESEARCH_LICENSE,
        field_semantic_ids={COD_FORMULA: COD_CONCEPT},
        identifier_semantic_id="materials.entry_id",
        reviewed_nonnull_string_fields=(COD_FORMULA,),
        http_client=http_client, network_policy=network_policy,
    )
    get = reviewed.endpoint("get_structures")
    declared = {field.name: field for field in get.output_fields}
    if (
        COD_FORMULA not in declared
        or declared[COD_FORMULA].json_schema != {"type": "string"}
        or "id" not in declared or declared["id"].identifier is not True
    ):
        raise SchemaSourceError("COD A5 source formula/identifier contract changed")

    search = reviewed.endpoint("search_structures")
    requested_fields = ["id", COD_FORMULA, "nelements", "elements"]
    if not set(requested_fields) <= {field.name for field in search.output_fields}:
        raise SchemaSourceError("COD A5 source search fields no longer declared")
    # Source-owned ID discovery, independently host-selected; no model input.
    results = await router.execute(ExecutionPlan(
        query="host-approved SiO2 structure preflight",
        registry_version=router.registry.version,
        calls=[ToolCall(
            tool=reviewed.key, endpoint=search.name,
            arguments={"filter": COD_FILTER, "page_limit": 1},
            fields=requested_fields,
            schema_fingerprint=search.fingerprint,
            tool_fingerprint=reviewed.fingerprint,
        )],
    ), config={"principal": PRINCIPAL.model_dump()})
    if len(results) != 1 or validate_optimade_structure(results[0].data) != 1:
        raise SchemaSourceError("COD host search returned no valid source identity")
    source_id = results[0].data[0]["id"]
    source_formula = results[0].data[0][COD_FORMULA]

    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=COD_CONCEPT,
        aliases=("materials formula", "화학식", "化学式"),
        required_fields=(
            CapabilityFieldContract(semantic_id=COD_CONCEPT,
                                    json_schema={"type": "string"}),
            CapabilityFieldContract(semantic_id="materials.entry_id",
                                    json_schema={"type": "string"}),
        ),
        source_type="optimade", license=COD_RESEARCH_LICENSE,
    ),))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id=COD_INTENT, required_concept_ids=(COD_CONCEPT,),
    ),))
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({COD_ROUTE}),
    )
    view = capture_authorized_agent_tool_surface(
        router, "Read the reviewed COD chemical formula for the host-selected record",
        principal=PRINCIPAL,
    )
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _scripted_understanding, _ScriptedA5Agent(),
        view=view, index=index, catalog=catalog, intent_registry=intents,
        model_visible_intent_ids=(COD_INTENT,),
        model_visible_concept_ids=(COD_CONCEPT,),
        expected_route_id=COD_ROUTE,
        host_source_arguments={COD_ROUTE: {"id": source_id}},
    )
    if decision != "offer" or receipt is None or receipt.route_id != COD_ROUTE:
        raise SchemaSourceError("COD original A5 refused the host-reviewed route")
    data = receipt.result.data
    if not isinstance(data, dict) or data.get("id") != source_id:
        raise SchemaSourceError("COD A5 native result lacks matching typed identity")
    if (
        type(data.get(COD_FORMULA)) is not str
        or not 1 <= len(data[COD_FORMULA].strip()) <= 200
        or data[COD_FORMULA] != source_formula
    ):
        raise SchemaSourceError("COD A5 native result formula differs from host search")
    return CODPaperA5E1(
        route_id=receipt.route_id, source_id=source_id, formula=data[COD_FORMULA],
        host_bound_tool_calls=receipt.host_bound_tool_calls,
    )


async def _cli(args: argparse.Namespace) -> None:
    if args.phase == "probe":
        result = await probe_cod_optimade_paper_a5()
    else:
        if not args.expected_source_fingerprint:
            raise ValueError(
                "--expected-source-fingerprint from a separately reviewed probe required"
            )
        result = await run_cod_optimade_paper_a5(
            expected_source_fingerprint=args.expected_source_fingerprint,
        )
    from dataclasses import asdict
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "run"))
    parser.add_argument("--expected-source-fingerprint")
    asyncio.run(_cli(parser.parse_args()))

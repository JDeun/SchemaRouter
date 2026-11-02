"""Keyless Crossref original A5 E1: local probe → pinned native GET.

The scripted model/agent are deterministic test scaffolding, not independent
E2. Only an explicitly host-selected DOI reaches the Crossref REST API.

Examples:
    python -m scripts.research_paper_crossref_native_e1 probe
    python -m scripts.research_paper_crossref_native_e1 run \
        --expected-source-fingerprint <digest> --host-doi 10.1038/nature12373
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
    inspect_crossref_paper_source,
    register_reviewed_crossref_paper_source,
)
from schemarouter.errors import SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_crossref_registration import (
    CrossrefPaperSourceProbe,
    validate_host_crossref_doi,
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

CROSSREF_DOI = "10.1038/nature12373"
CROSSREF_ROUTE = "crossref.get_work"
CROSSREF_LICENSE = "source-license-unverified-research-only"
CROSSREF_INTENT = "paper.lookup"
CROSSREF_CONCEPT = "paper.publisher"
PRINCIPAL = PrincipalContext(subject="crossref-paper-a5-research", roles=("reader",))


@dataclass(frozen=True, slots=True)
class CrossrefPaperA5E1:
    doi: str
    publisher: str
    route_id: str
    host_bound_tool_calls: int
    independent_e2: bool = False


class _ScriptedCrossrefAgent:
    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        del messages
        # A model cannot select provider request arguments, even if it emits them.
        forged = {"name": tools[0]["name"], "arguments": {"doi": "10.0000/agent-forged"}}
        return {"text": f"<tool_call>{json.dumps(forged)}</tool_call>",
                "context_overflow": False}


def _scripted_understanding(_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent_id": CROSSREF_INTENT,
        "concept_ids": [CROSSREF_CONCEPT],
        "named_tools": ["crossref"],
        "parameter_hints": {},
    }


async def probe_crossref_paper_a5() -> CrossrefPaperSourceProbe:
    """Local declaration only: does not contact or verify Crossref's server."""
    return inspect_crossref_paper_source()


async def run_crossref_paper_a5(
    *,
    expected_source_fingerprint: str,
    host_doi: str,
    http_client: httpx.AsyncClient | None = None,
    network_policy: NetworkPolicy | None = None,
) -> CrossrefPaperA5E1:
    """Execute one native singleton GET after P2/host-source review.

    The fingerprint must be externally approved from a prior probe; `run`
    never treats the contemporaneous local probe as owner approval.
    """
    validated_doi = validate_host_crossref_doi(host_doi)
    router = SchemaRouter(
        http_client=http_client,
        network_policy=network_policy or NetworkPolicy.public_only(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation=CROSSREF_ROUTE,
                              roles_any=("reader",)),
        )),
    )
    approved = register_reviewed_crossref_paper_source(
        router,
        expected_source_fingerprint=expected_source_fingerprint,
        expected_base_url="https://api.crossref.org/v1",
        license=CROSSREF_LICENSE,
        reviewed_by="crossref-native-a5-research-host",
    )
    concept = NativeDeclaredConcept(
        concept_id=CROSSREF_CONCEPT,
        aliases=("paper publisher", "논문 출판사", "論文出版社"),
        required_fields=(
            CapabilityFieldContract(
                semantic_id="paper.doi", json_schema={"type": "string"},
            ),
            CapabilityFieldContract(
                semantic_id=CROSSREF_CONCEPT, json_schema={"type": "string"},
            ),
        ),
        source_type="crossref", license=CROSSREF_LICENSE,
    )
    catalog = NativeConceptCatalog(concepts=(concept,))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id=CROSSREF_INTENT,
        required_concept_ids=(CROSSREF_CONCEPT,),
    ),))
    graph = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({CROSSREF_ROUTE}),
    )
    view = capture_authorized_agent_tool_surface(
        router, "Read the publisher and DOI of the host-selected Crossref work",
        principal=PRINCIPAL,
    )
    decision, receipt = await run_paper_scoped_native_direct_e1(
        _scripted_understanding, _ScriptedCrossrefAgent(),
        view=view,
        index=graph,
        catalog=catalog,
        intent_registry=intents,
        model_visible_intent_ids=(CROSSREF_INTENT,),
        model_visible_concept_ids=(CROSSREF_CONCEPT,),
        expected_route_id=CROSSREF_ROUTE,
        host_source_arguments={CROSSREF_ROUTE: {"doi": validated_doi}},
    )
    if decision != "offer" or receipt is None or receipt.route_id != CROSSREF_ROUTE:
        raise SchemaSourceError("Crossref original A5 refused host-reviewed typed route")
    data = receipt.result.data
    if (
        not isinstance(data, dict)
        or type(data.get("message.DOI")) is not str
        or data["message.DOI"].casefold() != validated_doi.casefold()
        or type(data.get("message.publisher")) is not str
        or not data["message.publisher"].strip()
    ):
        raise SchemaSourceError("Crossref A5 native receipt lacks verified DOI and publisher")
    if approved.key != "crossref":
        raise SchemaSourceError("Crossref registered source identity changed")
    return CrossrefPaperA5E1(
        doi=data["message.DOI"],
        publisher=data["message.publisher"],
        route_id=receipt.route_id,
        host_bound_tool_calls=receipt.host_bound_tool_calls,
    )


async def _cli(args: argparse.Namespace) -> None:
    if args.phase == "probe":
        result = await probe_crossref_paper_a5()
    else:
        if not args.expected_source_fingerprint:
            raise ValueError(
                "--expected-source-fingerprint from a prior reviewed probe is required"
            )
        result = await run_crossref_paper_a5(
            expected_source_fingerprint=args.expected_source_fingerprint,
            host_doi=args.host_doi,
        )
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("probe", "run"))
    parser.add_argument("--expected-source-fingerprint")
    parser.add_argument("--host-doi", default=CROSSREF_DOI)
    asyncio.run(_cli(parser.parse_args()))

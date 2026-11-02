"""Opt-in source-native A5 direct dispatch through real Open-Meteo HTTPS adapter.

One host-scripted agent selects the originally offered tool. The host binds
the approved city input; no real model inference, independent gold or E2.
Open-Meteo free API is documented for noncommercial E1 research only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

import httpx

from schemarouter import (
    CapabilityFieldContract,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PrincipalContext,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_open_meteo_live_two_hop_e1 import (
    _DOCUMENTED_SOURCE_LICENSE,
    build_live_router,
)
from scripts.research_paper_scoped_native_direct_e1 import (
    run_paper_scoped_native_direct_e1,
)

QUERY = "Locate Seoul coordinates in the reviewed Open-Meteo source"
HOST_INPUT = {
    "name": "Seoul", "language": "en", "country_code": "KR",
}
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="geo.coordinates",
    aliases=("latitude longitude coordinates",),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="open_meteo.wgs84.latitude",
            json_schema={"type": "number"},
        ),
        CapabilityFieldContract(
            semantic_id="open_meteo.wgs84.longitude",
            json_schema={"type": "number"},
        ),
    ),
    source_type="public_rest",
    license=_DOCUMENTED_SOURCE_LICENSE,
),))
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="geo.lookup", required_concept_ids=("geo.coordinates",),
),))


class HostScriptedGeocodeAgent:
    """A synthetic chooser used to verify wiring, NEVER model quality."""

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(messages) != 2 or len(tools) != 1:
            raise ValueError("source-approved single tool exposure required")
        # Deliberately wrong, unapproved agent input. The native invoker
        # must see only the independently host-approved Seoul parameters.
        forged = {
            "name": tools[0]["name"],
            "arguments": {
                "name": "Tokyo", "language": "ja", "country_code": "JP",
                "extra": "agent-forged",
            },
        }
        return {
            "text": f"<tool_call>{json.dumps(forged)}</tool_call>",
            "input_tokens": 1, "output_tokens": 1, "tool_tokens": 1,
            "latency_ms": 0.0, "context_overflow": False,
        }


async def run_native_open_meteo_direct_e1(client: httpx.AsyncClient) -> dict[str, Any]:
    """Exercise E1 genuine registered HTTPS invoker; return redacted counts."""
    router, geocode, forecast = build_live_router(
        client, documented_noncommercial_e1=True, transport_retry_budget=0,
    )
    try:
        view = capture_authorized_agent_tool_surface(
            router, QUERY,
            principal=PrincipalContext(subject="e1-geocode-research", roles=("reader",)),
        )
        index = NativeSchemaGraphIndex.build(
            NativeSchemaPostingIndex.build(router.registry),
            approved_host_roots=frozenset({"open_meteo_geocoding.search"}),
        )
        decision, receipt = await run_paper_scoped_native_direct_e1(
            lambda _payload: {
                "intent_id": "geo.lookup", "concept_ids": ["geo.coordinates"],
                "named_tools": ["open_meteo_geocoding"],
                "parameter_hints": {"name": "Tokyo"},
            },
            HostScriptedGeocodeAgent(),
            view=view, index=index, catalog=CATALOG, intent_registry=INTENTS,
            model_visible_intent_ids=("geo.lookup",),
            model_visible_concept_ids=("geo.coordinates",),
            host_source_arguments={"open_meteo_geocoding.search": dict(HOST_INPUT)},
        )
        if decision != "offer" or receipt is None:
            raise ValueError("original P2 direct source was not executed")
        response = receipt.result.data
        if (
            not isinstance(response, dict)
            or not set(("latitude", "longitude")).issubset(response)
            or geocode.calls != 1 or geocode.http_attempts != 1
            or forecast.calls != 0 or forecast.http_attempts != 0
            or receipt.host_bound_tool_calls != 1
            or receipt.provider_provenance_verified
            or receipt.independent_e2
        ):
            raise ValueError("Open-Meteo source-native E1 result not validated")
        # Do not export private tool results, coordinates, model strings or
        # original provider response. The host-only result stays in memory.
        return {
            "evidence_tier": "E1_HOST_SCRIPTED_NATIVE_DIRECT_NOT_E2",
            "native_invocations": 1,
            "source_http_attempts": geocode.http_attempts,
            "host_bound_tool_calls": receipt.host_bound_tool_calls,
            "provider_result_contract_matched": True,
            "model_selected_calls": 0,
            "independent_e2": False,
            "source_license_scope": "documented_noncommercial_only",
        }
    finally:
        await router.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="explicitly opt in to the keyless public Open-Meteo HTTPS read",
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("public network experiment is opt-in: pass --live")

    async def run() -> dict[str, Any]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20), follow_redirects=False,
        ) as client:
            return await run_native_open_meteo_direct_e1(client)

    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(run())
        print(json.dumps({"status": "success", **result}, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "failure", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    finally:
        logging.disable(previous_logging_disable)


if __name__ == "__main__":
    main()

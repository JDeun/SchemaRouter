"""E1 local-source control: 12+ bound original read-only routes, no provider.

This is a deterministic registry/executor and scoped-authorization fixture,
NOT independent E2, a remote provider, or a verified full-menu cost win.
The existing host tool disclosure cap of five is never bypassed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.errors import PolicyViolationError
from scripts.agent_utility_v7_dev_agent import MODEL_NAME, MODEL_REVISION
from scripts.research_authorized_agent_tool_surface import (
    _authorization_policy_receipt,
    capture_authorized_agent_tool_surface,
)
from scripts.research_codegraph_scoped_materializer import (
    SurgicalEpisode,
    capture_surgical_episode,
)
from scripts.research_codegraph_action_shape_e1 import classify_rejected_action_shape
from scripts.research_codegraph_surgical_agent_e1 import (
    SurgicalHostContext,
    run_surgical_model_episode,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    _parse_strict_model_json,
    parse_one_model_action,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

LANGUAGE_ALIASES = {
    "en": "case status",
    "ko": "문의 상태",
    "ja": "問い合わせ状態",
}
CONDITIONS = ("joined", "denied", "no_fit", "over_k")
ARMS = ("all_visible", "lexical_k5", "concept_graph_optin", "surgical_g5_e1")
ROUTES = ("contacts.read", "cases.read")
TURN_BUDGET = 5
SOURCE_LICENCE = "deterministic-local-owner-reviewed"
ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class LocalControlSource:
    router: SchemaRouter
    catalog: NativeConceptCatalog
    index: NativeSchemaGraphIndex
    principal: PrincipalContext
    language: str
    condition: str
    callback_log: list[str]
    registered_callbacks: tuple[str, ...]
    episode: SurgicalEpisode | None


def _field(name: str, *, semantic_id: str, identifier: bool = False) -> FieldSpec:
    return FieldSpec(
        name=name, semantic_id=semantic_id, identifier=identifier,
        json_schema={"type": "string"},
    )


def _registered_source_contracts(
    router: SchemaRouter, *, condition: str, inventory_routes: int = 10,
) -> None:
    if type(inventory_routes) is not int or inventory_routes not in (2, 10):
        raise ValueError("only the preregistered 4 or 12 route local source")
    aliases = " ".join(LANGUAGE_ALIASES.values())
    original_ids = ("contact_id", "region_id")
    produced = original_ids[:1] if condition == "no_fit" else original_ids
    router.add_tool(ToolSpec(
        name="contacts", source_type="local_reviewed", license=SOURCE_LICENCE,
        description=f"{aliases} root contact identifiers",
        endpoints=[EndpointSpec(
            name="read", description=f"{aliases} producer source",
            read_only=True,
            output_fields=[_field(name, semantic_id=f"crm.{name}", identifier=True)
                           for name in produced],
            output_schema={
                "type": "object",
                "properties": {name: {"type": "string"} for name in produced},
                "required": list(produced),
            },
        )],
    ))
    for index in range(6 if condition == "over_k" else 1):
        name = "cases" if index == 0 else f"cases_{index}"
        router.add_tool(ToolSpec(
            name=name, source_type="local_reviewed", license=SOURCE_LICENCE,
            description=f"{aliases} consumer verification",
            endpoints=[EndpointSpec(
                name="read", description=f"{aliases} source case result",
                read_only=True,
                parameters=[ParameterSpec(
                    name=param, semantic_id=f"crm.{param}", required=True,
                    json_schema={"type": "string"},
                ) for param in original_ids],
                input_schema={
                    "type": "object",
                    "properties": {param: {"type": "string"} for param in original_ids},
                    "required": list(original_ids),
                },
                output_fields=[_field("case_state", semantic_id="crm.status")],
            )],
        ))
    for index in range(inventory_routes):
        name = f"inventory_{index:02d}"
        router.add_tool(ToolSpec(
            name=name, source_type="local_reviewed", license=SOURCE_LICENCE,
            description=f"Inventory category {index} health lookup, unrelated to cases",
            endpoints=[EndpointSpec(
                name="read", description=f"Inventory sample {index}",
                read_only=True,
                output_fields=[_field(
                    "item_code", semantic_id=f"inventory_{index}.item_code",
                )],
            )],
        ))


def build_local_multiroute_source(
    *, language: str, condition: str = "joined", catalog_size: int = 12,
) -> LocalControlSource:
    """Bind the original 12-route control or an independent K5-safe 4-route source."""
    if type(catalog_size) is not int or catalog_size not in (4, 12):
        raise ValueError("only preregistered 4 or 12 route local source")
    if catalog_size == 4 and condition != "joined":
        raise ValueError("four-route comparison requires the joined task")
    if language not in LANGUAGE_ALIASES or condition not in CONDITIONS:
        raise ValueError("unregistered local source cohort")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    _registered_source_contracts(
        router, condition=condition, inventory_routes=catalog_size - 2,
    )
    callbacks: list[str] = []
    seen: list[str] = []

    def callback_factory(route_id: str):
        def execute(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
            del endpoint
            seen.append(route_id)
            if route_id == ROUTES[0]:
                return {"contact_id": "contact-4", "region_id": "region-9"}
            if route_id.startswith("cases"):
                return {"case_state": "ready" if arguments == {
                    "contact_id": "contact-4", "region_id": "region-9",
                } else "invalid"}
            return {"item_code": "ordinary-local-fixture"}

        return execute

    for tool in router.registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            router.executor.bind(
                tool.key, callback_factory(route_id),
                expected_fingerprint=tool.fingerprint,
            )
            callbacks.append(route_id)
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="case_state", aliases=tuple(LANGUAGE_ALIASES.values()),
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),),
        source_type="local_reviewed", license=SOURCE_LICENCE,
    ),))
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    principal = PrincipalContext(
        subject="reviewer" if condition != "denied" else "unapproved",
        roles=("reader",) if condition != "denied" else ("viewer",),
    )
    episode = None
    if condition == "joined":
        episode = capture_surgical_episode(
            router, LANGUAGE_ALIASES[language], principal=principal,
            catalog=catalog, index=index,
        )
    return LocalControlSource(
        router=router, catalog=catalog, index=index, principal=principal,
        language=language, condition=condition, callback_log=seen,
        registered_callbacks=tuple(callbacks), episode=episode,
    )


def _same_source_digest(source: LocalControlSource) -> str:
    snapshot = (
        source.router.registry.version,
        tuple((tool.key, tool.fingerprint) for tool in source.router.registry.tools()),
        _authorization_policy_receipt(source.router.authorization_policy),
    )
    return hashlib.sha256(repr(snapshot).encode("utf-8")).hexdigest()


def _strict_final(text: str, observed: Mapping[str, Any]) -> bool:
    try:
        answer = _parse_strict_model_json(text)
    except (TypeError, ValueError, OverflowError):
        return False
    return answer == {"case_state": observed.get("case_state")}


async def _baseline_local_arm(
    agent: Any, *, source: LocalControlSource, condition: str,
) -> dict[str, Any]:
    """Old native disclosure and invocation, with no >5-route workaround."""
    router = source.router
    query = LANGUAGE_ALIASES[source.language]
    view = capture_authorized_agent_tool_surface(
        router, query, principal=source.principal,
    )
    digest = _same_source_digest(source)
    if condition == "all_visible" and len(view.visible_route_ids) > 5:
        return {
            "condition": condition, "status": "BLOCKED_MENU_CAP",
            "source_receipt_digest": digest, "model_turns": 0,
            "actual_source_calls": 0, "schema_requests": 0,
            "full_task_complete": None, "model_input_tokens": None,
            "tool_schema_tokens": None, "model_output_tokens": None,
            "total_model_tokens": None,
        }
    if condition == "lexical_k5":
        selection = router.retrieve_authorized(query, principal=source.principal, k=5)
        offered = tuple(
            candidate.route_id for candidate in selection.candidates
            if candidate.route_id in view.visible_route_ids
        )
    elif condition == "concept_graph_optin":
        selection = retrieve_authorized_concept_graph(
            router, query, principal=source.principal,
            catalog=source.catalog, index=source.index, k=5,
        )
        offered = selection.route_ids
    else:
        offered = view.visible_route_ids
    if len(offered) > 5:
        raise ValueError("baseline exceeds authorized model menu")
    definitions = view.tool_definitions(list(offered), k=5)
    messages = [
        {"role": "system", "content": (
            "Use selected original read-only tools, first contacts then cases. "
            "Only trust the verified public preceding observation. "
            "Answer JSON with case_state after both real calls."
        )},
        {"role": "user", "content": query},
    ]
    calls: list[str] = []
    observations: dict[str, dict[str, Any]] = {}
    input_tokens = output_tokens = schema_tokens = 0
    all_receipts = True
    reason = "turn_limit"
    rejected_model_action_shape: str | None = None
    correct = False
    turns = 0
    for _ in range(TURN_BUDGET):
        view.assert_source_unchanged()
        turns += 1
        generated = agent.generate(messages, definitions)
        view.assert_source_unchanged()
        if (
            type(generated) is not dict
            or type(generated.get("text")) is not str
            or generated.get("context_overflow") is not False
        ):
            reason = "invalid_model_envelope"
            all_receipts = False
            break
        if all(type(generated.get(key)) is int and generated[key] >= 0
               for key in ("input_tokens", "tool_tokens", "output_tokens")):
            input_tokens += generated["input_tokens"]
            output_tokens += generated["output_tokens"]
            schema_tokens += generated["tool_tokens"]
        else:
            all_receipts = False
        try:
            kind, payload = parse_one_model_action(generated["text"])
        except (ValueError, TypeError, OverflowError):
            reason = "malformed_model_action"
            rejected_model_action_shape = classify_rejected_action_shape(
                generated["text"],
            )
            break
        if kind == "final":
            reason = "completed_final" if len(calls) == 2 else "premature_final"
            if len(calls) < 2:
                rejected_model_action_shape = classify_rejected_action_shape(
                    generated["text"],
                )
            if len(calls) == 2:
                correct = _strict_final(payload, observations[ROUTES[1]])
            break
        route_id, arguments = payload["route"], payload["arguments"]
        if (
            len(calls) >= 2 or route_id != ROUTES[len(calls)]
            or route_id not in offered
        ):
            reason = "unoffered_or_out_of_order_route"
            break
        expected = {} if not calls else {
            field: observations[ROUTES[0]][field]
            for field in ("contact_id", "region_id")
        }
        if arguments != expected:
            reason = "unbound_source_arguments"
            break
        try:
            observation = await execute_scoped_host_call(
                view, selected_route_ids=list(offered),
                route_id=route_id, arguments=arguments,
                host_required_output_fields=(
                    ("contact_id", "region_id") if not calls else ("case_state",)
                ),
            )
        except (PolicyViolationError, ValueError, RuntimeError):
            reason = "native_host_call_denied"
            break
        if observation.get("status") != "ok":
            reason = "non_ok_observation"
            break
        calls.append(route_id)
        observations[route_id] = observation
        messages.extend((
            {"role": "assistant", "content": generated["text"]},
            {"role": "tool", "content": json.dumps(observation, sort_keys=True)},
        ))
    return {
        "condition": condition, "status": reason,
        "rejected_model_action_shape": rejected_model_action_shape,
        "source_receipt_digest": digest,
        "model_turns": turns,
        "actual_source_calls": len(calls),
        "schema_requests": 0,
        "full_task_complete": correct,
        "model_input_tokens": input_tokens if all_receipts else None,
        "tool_schema_tokens": schema_tokens if all_receipts else None,
        "model_output_tokens": output_tokens if all_receipts else None,
        "total_model_tokens": input_tokens + output_tokens if all_receipts else None,
    }


async def run_local_multiroute_codegraph_e1(
    agent: Any, *, language: str, condition: str = "joined",
    catalog_size: int = 12,
) -> dict[str, Any]:
    """12-route scaling negative OR separate true four-route comparable local E1."""
    source = build_local_multiroute_source(
        language=language, condition=condition, catalog_size=catalog_size,
    )
    route_count = len(source.registered_callbacks)
    safe: dict[str, Any] = {
        "study": (
            "CODEGRAPH_SURGICAL_LOCAL_FOUR_ROUTE_E1"
            if catalog_size == 4 else "CODEGRAPH_SURGICAL_LOCAL_MULTIROUTE_E1"
        ),
        "evidence_tier": "E1_LOCAL_SOURCE_CONTROL",
        "model_id": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "arms": ARMS,
        "language": language,
        "source_route_count": route_count,
        "requested_k": 5,
        "max_model_turns": TURN_BUDGET,
        "source_receipt_digest": _same_source_digest(source),
        "original_provider_e1": False,
        "independent_e2_qualified": False,
        "release_qualified": False,
        "task_success_rate": None,
        "qualified_task_denominator": None,
    }
    if condition != "joined":
        selection = retrieve_authorized_concept_graph(
            source.router, LANGUAGE_ALIASES[language],
            principal=source.principal,
            catalog=source.catalog, index=source.index,
        )
        blocked = {
            "denied": "BLOCKED_AUTHORIZATION",
            "no_fit": "BLOCKED_NO_PROVEN_HIT",
            "over_k": "BLOCKED_OVER_K_UNRANKED",
        }
        if selection.status == "complete":
            raise ValueError("negative source contract unexpectedly qualified")
        return {
            **safe, "status": blocked[condition],
            "source_call_count": 0, "outcomes": (),
        }
    if not callable(getattr(agent, "generate", None)):
        return {
            **safe, "status": "BLOCKED_MODEL_RUNTIME",
            "source_call_count": 0, "outcomes": (),
        }
    outcomes: list[dict[str, Any]] = []
    total_calls = 0
    for arm in ARMS:
        current = build_local_multiroute_source(
            language=language, catalog_size=catalog_size,
        )
        digest = _same_source_digest(current)
        if digest != safe["source_receipt_digest"]:
            return {
                **safe, "status": "INCOMPARABLE_SOURCE_DRIFT",
                "source_call_count": total_calls, "outcomes": (),
            }
        if arm == "surgical_g5_e1":
            if current.episode is None:
                raise ValueError("positive case missing verified G5 selection")
            context = SurgicalHostContext(
                required_output_fields={
                    ROUTES[0]: ("contact_id", "region_id"),
                    ROUTES[1]: ("case_state",),
                },
                final_response_instruction="Answer JSON with only case_state.",
                validate_final=_strict_final,
            )
            row = await run_surgical_model_episode(
                agent, episode=current.episode,
                host_context=context, max_turns=TURN_BUDGET,
            )
            row = {
                **row, "condition": arm,
                "status": row["termination_reason"],
                "source_receipt_digest": digest,
                "full_task_complete": row["full_task_correct"],
            }
        else:
            row = await _baseline_local_arm(agent, source=current, condition=arm)
        if row["actual_source_calls"] != len(current.callback_log):
            raise ValueError("local original executor count mismatch")
        total_calls += len(current.callback_log)
        outcomes.append(row)
    if catalog_size == 4:
        # Each arm receives the same ORIGINAL registered four-route inventory;
        # FULL now fits the existing public K5 cap without special-case bypass.
        # This is ONE local synthetic task per language, not independent E2.
        if any(type(row["full_task_complete"]) is not bool for row in outcomes):
            return {
                **safe, "status": "INCOMPARABLE_LOCAL_ARM",
                "source_call_count": total_calls, "outcomes": outcomes,
            }
        return {
            **safe, "status": "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2",
            "task_success_rate": {
                row["condition"]: float(row["full_task_complete"])
                for row in outcomes
            },
            "qualified_task_denominator": {
                arm: 1 for arm in ARMS
            },
            "source_call_count": total_calls, "outcomes": outcomes,
        }
    return {
        **safe,
        "status": "INCOMPARABLE_FULL_MENU_CAP",
        "source_call_count": total_calls,
        "outcomes": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=["local-source"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--language", choices=LANGUAGE_ALIASES, default="en")
    parser.add_argument("--catalog-size", type=int, choices=(4, 12), default=12)
    args = parser.parse_args()
    source = build_local_multiroute_source(
        language=args.language, catalog_size=args.catalog_size,
    )
    # Source registration completes without model generation or fake scores.
    # A genuinely absent local runtime returns a null-denominator blocker.
    preflight = asyncio.run(run_local_multiroute_codegraph_e1(
        None, language=args.language, catalog_size=args.catalog_size,
    ))
    if preflight["status"] == "BLOCKED_MODEL_RUNTIME":
        previous = {key: os.environ.get(key) for key in (
            "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
        )}
        try:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            try:
                from scripts.agent_utility_v7_dev_agent import LocalQwenAgent

                agent = LocalQwenAgent()
            except (ImportError, OSError, RuntimeError, ValueError):
                result = preflight
            else:
                result = asyncio.run(run_local_multiroute_codegraph_e1(
                    agent, language=args.language, catalog_size=args.catalog_size,
                ))
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    else:
        result = preflight
    result["registered_original_read_only_routes"] = len(source.registered_callbacks)
    result["source_revision"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True, timeout=10,
    ).stdout.strip()
    result["hardware"] = platform.platform()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "study": result["study"], "status": result["status"],
        "qualified_task_denominator": result["qualified_task_denominator"],
        "registered_original_read_only_routes": len(source.registered_callbacks),
    }))


if __name__ == "__main__":
    main()

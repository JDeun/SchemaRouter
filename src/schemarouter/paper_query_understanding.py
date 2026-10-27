"""Bounded, host-owned Understand(q) callback for schema-only field routing.

Model output proposes reviewed IDs; only currently authorized source contracts
can produce a field plan. No tool call, data read, or answer synthesis occurs.
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import MAX_QUERY_BYTES, MAX_QUERY_CHARS, NativeConceptCatalog
from .errors import ModelAnalysisError, PolicyViolationError
from .host_field_contract import _policy_contents_digest
from .paper_typed_tool_plan import PaperTypedToolPlan
from .paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    _bounded_name,
)

if TYPE_CHECKING:
    from .field_routing_session import SchemaFieldRoutingSession


PaperFieldModel = Callable[
    [dict[str, Any]], dict[str, Any] | str | Awaitable[dict[str, Any] | str],
]


def _decode_bounded_response(raw: dict[str, Any] | str, limit: int) -> PaperUnderstanding:
    """Reject duplicate keys, nonfinite numbers, excess bytes and type coercion."""

    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate model field")
            result[key] = value
        return result

    def reject_nonfinite(_value: str) -> None:
        raise ValueError("nonfinite model value")

    try:
        if type(raw) is str:
            if len(raw.encode("utf-8")) > limit:
                raise ModelAnalysisError("paper model output exceeds byte budget")
            payload = json.loads(
                raw, object_pairs_hook=unique_pairs, parse_constant=reject_nonfinite,
            )
        elif type(raw) is dict:
            payload = raw
        else:
            raise ValueError("invalid model output")
        if type(payload) is not dict:
            raise ValueError("model result must be an object")
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        if len(encoded.encode("utf-8")) > limit:
            raise ModelAnalysisError("paper model output exceeds byte budget")
        return PaperUnderstanding.model_validate_json(encoded, strict=True)
    except ModelAnalysisError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ModelAnalysisError("invalid structured paper model response") from None


async def compile_model_query(
    session: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    model: PaperFieldModel,
    intent_registry: PaperIntentRegistry,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
    model_visible_tool_keys: tuple[str, ...] = (),
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
    max_hops: int = 2,
    max_model_input_bytes: int = 32768,
    max_model_output_bytes: int = 4096,
) -> PaperTypedToolPlan:
    """Propose source-scoped intent IDs using a single caller-supplied model.

    The caller deliberately chooses which IDs/tool *names* may be disclosed
    to its model. Live field and source checks independently constrain those
    names. Model-suggested parameter values never become host arguments.
    """
    if (
        type(query) is not str or not 2 <= len(query) <= MAX_QUERY_CHARS
        or len(query.encode("utf-8")) > MAX_QUERY_BYTES
        or query != query.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in query)
    ):
        raise ValueError("invalid bounded paper query")
    if not isinstance(principal, PrincipalContext):
        raise PolicyViolationError("paper query requires trusted principal")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("host-approved intent registry required")
    if not callable(model):
        raise ValueError("explicit model callback required")
    if type(k) is not int or k != 5 or type(max_hops) is not int or max_hops not in (1, 2):
        raise ValueError("paper query requires K5 and one or two graph hops")
    if (
        type(max_model_input_bytes) is not int
        or not 1 <= max_model_input_bytes <= 32768
        or type(max_model_output_bytes) is not int
        or not 1 <= max_model_output_bytes <= 4096
    ):
        raise ValueError("invalid paper model byte budget")

    # Review-only sessions have no approved concept authority. The public
    # session entrypoint already enforces this; the standalone compiler must
    # enforce it too before producing any model-visible disclosure.
    catalog = session._require_catalog()
    try:
        reviewed = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
        intents = PaperIntentRegistry.model_validate(
            intent_registry.model_dump(mode="python"), strict=True,
        )
        before = (catalog.model_dump_json(), intent_registry.model_dump_json(),
                  principal.model_dump_json(), deepcopy(host_source_arguments))
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise PolicyViolationError("paper query owner declarations invalid") from None

    approved_concepts = {c.concept_id: c for c in reviewed.concepts}
    approved_intents = {i.intent_id: i for i in intents.intents}
    if (
        type(model_visible_concept_ids) is not tuple
        or not 1 <= len(model_visible_concept_ids) <= 8
        or any(type(cid) is not str for cid in model_visible_concept_ids)
        or len(set(model_visible_concept_ids)) != len(model_visible_concept_ids)
        or not set(model_visible_concept_ids) <= approved_concepts.keys()
        or type(model_visible_intent_ids) is not tuple
        or not 1 <= len(model_visible_intent_ids) <= 16
        or any(type(iid) is not str for iid in model_visible_intent_ids)
        or len(set(model_visible_intent_ids)) != len(model_visible_intent_ids)
        or not set(model_visible_intent_ids) <= approved_intents.keys()
        or any(not set(approved_intents[iid].required_concept_ids)
               <= set(model_visible_concept_ids) for iid in model_visible_intent_ids)
        or type(model_visible_tool_keys) is not tuple
        or len(model_visible_tool_keys) > 5
        or any(not _bounded_name(name) for name in model_visible_tool_keys)
        or len(set(model_visible_tool_keys)) != len(model_visible_tool_keys)
    ):
        raise ValueError("invalid host-approved model disclosure")

    router = session._router
    witness = router._retrieval_authority_witness()
    session._index.field_index._assert_source(router)
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper query requires explicit source policy")
    policy_digest = _policy_contents_digest(policy)
    availability = router.planner.availability_predicate

    def verify() -> None:
        session._index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or router.planner.availability_predicate is not availability
            or catalog.model_dump_json() != before[0]
            or intent_registry.model_dump_json() != before[1]
            or principal.model_dump_json() != before[2]
            or host_source_arguments != before[3]
        ):
            raise PolicyViolationError("paper query source or owner authority changed")

    def abstain() -> PaperTypedToolPlan:
        verify()
        return PaperTypedToolPlan(
            status="no_proven_hit", snapshot_id=session.snapshot_id,
            registry_version=witness[1], requested_k=k,
        )

    # These are owner-reviewed concepts that still have a current, accessible,
    # field-complete proof. Never disclose unreachable concepts to the model.
    offered_concepts = []
    for concept_id in model_visible_concept_ids:
        concept = approved_concepts[concept_id]
        try:
            coverage = session.discover(concept.aliases[0], principal=principal, k=k)
        except ValueError:
            # A catalog alias is not an independent proof of current fields.
            continue
        except Exception:
            raise PolicyViolationError("paper query source eligibility check failed") from None
        verify()
        if coverage.status == "complete":
            offered_concepts.append(concept)
    offered_ids = {concept.concept_id for concept in offered_concepts}
    offered_intents = [
        approved_intents[iid] for iid in model_visible_intent_ids
        if set(approved_intents[iid].required_concept_ids) <= offered_ids
    ]
    if not offered_intents:
        return abstain()

    # Only host-approved, currently scoped, non-destructive tool identities
    # may reach the model. Schema bodies/hidden route IDs are not disclosed.
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper query lacks source authorization")
    offered_tools: list[str] = []
    for tool_key in model_visible_tool_keys:
        allowed = False
        try:
            tool = router.registry.get(tool_key)
            for endpoint in tool.endpoints:
                if (
                    endpoint.read_only is True and endpoint.destructive is not True
                    and permitted(tool, endpoint)
                    and (availability is None or availability(tool, endpoint))
                    and router._data_scope_endpoint_view(principal, tool, endpoint)
                    is not None
                ):
                    allowed = True
                    break
        except Exception:
            raise ValueError("invalid host-approved model disclosure") from None
        verify()
        if not allowed:
            raise ValueError("invalid host-approved model disclosure")
        offered_tools.append(tool_key)

    payload = {
        "task": "Identify one reviewed intent and necessary concepts for schema fields only",
        "query": query,
        "offered_intents": [
            {"intent_id": i.intent_id, "required_concept_ids": list(i.required_concept_ids)}
            for i in offered_intents
        ],
        "offered_concepts": [
            {"concept_id": c.concept_id, "aliases": list(c.aliases)}
            for c in offered_concepts
        ],
        "offered_tool_keys": offered_tools,
        "response_fields": ["intent_id", "concept_ids", "named_tools"],
        "rules": [
            "Use only offered IDs and offered tool keys; return one JSON object.",
            "Do not suggest parameter values or request a provider execution.",
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > max_model_input_bytes:
        raise ModelAnalysisError("paper model input exceeds byte budget")
    verify()
    try:
        response = model(json.loads(encoded))
        if inspect.isawaitable(response):
            response = await response
    except Exception:
        verify()
        raise ModelAnalysisError("paper model understanding failed") from None
    verify()
    understood = _decode_bounded_response(response, max_model_output_bytes)
    if (
        understood.intent_id not in {i.intent_id for i in offered_intents}
        or not set(understood.concept_ids) <= offered_ids
        or not set(understood.named_tools) <= set(offered_tools)
    ):
        raise ModelAnalysisError("model selected unoffered paper identities")
    try:
        plan = session.compile_understood(
            understood, principal=principal, intent_registry=intent_registry,
            host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
        )
    except (ValueError, TypeError):
        verify()
        raise ModelAnalysisError("model understanding could not be compiled") from None
    verify()
    return plan

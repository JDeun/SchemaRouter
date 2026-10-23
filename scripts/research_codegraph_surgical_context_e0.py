"""#1711 bounded E0: compare scoped full tool context vs graph references.

This measures only canonical UTF-8 JSON bytes. It neither invokes sources
nor estimates tokenizer cost, agent quality, independent E2 success or grants.
The compact payload is a *reference*, not an executable tool definition.
"""

from __future__ import annotations

import argparse
import hmac
import json
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_authorized_agent_tool_surface import (
    _authorization_policy_receipt,
    _principal_claims_canonical,
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    _catalog_content_digest,
)


def _json_bytes(value: dict[str, Any]) -> bytes:
    """Use one byte-stable UTF-8 encoding for both paired arms."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def compare_contexts(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
) -> dict[str, Any]:
    """Capture equal source-verified G5 evidence, varying only context format.

    This research-only function intentionally has no generalized disclosure API.
    Full source definitions are obtained through the already guarded,
    principal-scoped model surface; all path and field references must also
    appear in that exact checked view, or the comparison fails closed.
    """
    # Graph selection and tool-surface capture are distinct authorized reads.
    # Bind both to the same authority *content*, not merely a registry version.
    authority_witness = router._retrieval_authority_witness()
    policy_receipt = _authorization_policy_receipt(router.authorization_policy)
    principal_claims = _principal_claims_canonical(principal)
    try:
        NativeConceptCatalog.model_validate(catalog.model_dump(mode="python"), strict=True)
        catalog_receipt = _catalog_content_digest(catalog)
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise PolicyViolationError("cannot attest approved concept catalog") from exc

    def assert_scope_unchanged() -> None:
        router._check_retrieval_authority_witness(authority_witness)
        if not hmac.compare_digest(
            policy_receipt, _authorization_policy_receipt(router.authorization_policy),
        ) or _principal_claims_canonical(principal) != principal_claims:
            raise PolicyViolationError("graph/source authorization scope changed")
        try:
            NativeConceptCatalog.model_validate(catalog.model_dump(mode="python"), strict=True)
            current_catalog_receipt = _catalog_content_digest(catalog)
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("concept catalog changed during context capture") from exc
        if not hmac.compare_digest(catalog_receipt, current_catalog_receipt):
            raise PolicyViolationError("concept catalog changed during context capture")

    selection = retrieve_authorized_concept_graph(
        router, query, principal=principal, catalog=catalog, index=index, k=5,
    )
    assert_scope_unchanged()
    if (
        selection.independent_quality_evidence
        or selection.calibrated_no_fit
        or selection.executable_authority
    ):
        raise PolicyViolationError("unexpected graph quality or execution authority")
    output_names: dict[str, list[str]] = {}
    definitions: list[dict[str, Any]] = []
    if selection.status == "complete":
        view = capture_authorized_agent_tool_surface(
            router, query, principal=principal,
        )
        assert_scope_unchanged()
        view.assert_source_unchanged()
        if (
            view.independent_quality_evidence
            or view.executable_authority
            or selection.requested_k != 5
            or view.original_query != query
            or view.witness[1] != selection.registry_version
            or view.witness != authority_witness
            or view._authorization_policy_receipt != policy_receipt
            or view._principal_claims_snapshot != principal_claims
            or not set(selection.route_ids).issubset(view.visible_route_ids)
        ):
            raise PolicyViolationError("selected graph path not in scoped source view")
        # Internal source view is research-only and HMAC-protected. Never read
        # raw registered endpoint output_fields for these exposed names.
        scoped = {route.route_id: route for route in view._semantic_source_routes}
        for path in selection.route_sets:
            for route_id, tool_fp, endpoint_fp in path.route_fingerprints:
                route = scoped.get(route_id)
                if route is None or (
                    route.tool_fingerprint, route.endpoint_fingerprint
                ) != (tool_fp, endpoint_fp):
                    raise PolicyViolationError("graph/source route fingerprint mismatch")
        output_names = {
            route_id: sorted(view._visible_output_names[route_id])
            for route_id in selection.route_ids
        }
        # The actual join must still be possible using visible producer fields;
        # route fingerprint parity alone does not establish data-scope parity.
        for path in selection.route_sets:
            if len(path.route_ids) == 2 and any(
                source_field not in output_names[path.route_ids[0]]
                for _, source_field in path.parameter_bindings
            ):
                raise PolicyViolationError("graph binding field is no longer visible")
        definitions = view.tool_definitions(list(selection.route_ids), k=5)
        view.assert_source_unchanged()
        assert_scope_unchanged()

    common: dict[str, Any] = {
        "status": selection.status,
        "index_snapshot_id": selection.snapshot_id,
        "registry_version": selection.registry_version,
        "requested_k": selection.requested_k,
        "route_ids": list(selection.route_ids),
        "route_sets": [{
            "route_ids": list(path.route_ids),
            "route_fingerprints": [list(row) for row in path.route_fingerprints],
            "required_semantic_ids": list(path.required_semantic_ids),
            "parameter_bindings": [list(row) for row in path.parameter_bindings],
            "visible_output_fields": [
                {"route_id": route_id, "fields": output_names[route_id]}
                for route_id in path.route_ids
            ],
        } for path in selection.route_sets],
        "independent_quality_evidence": False,
        "calibrated_no_fit": False,
        "executable_authority": False,
        "tool_call_ready": False,
    }
    full = {
        **common,
        "context_format": "full_source_definitions",
        "tool_definitions": definitions,
    }
    surgical = {
        **common,
        "context_format": "graph_references_only",
        "requires_source_schema_materialization": True,
    }
    full_len = len(_json_bytes(full))
    surgical_len = len(_json_bytes(surgical))
    assert_scope_unchanged()
    return {
        "full_envelope": full,
        "surgical_envelope": surgical,
        "full_utf8_json_bytes": full_len,
        "surgical_utf8_json_bytes": surgical_len,
        "surgical_to_full_ratio": surgical_len / full_len,
        "selected_path_parity": full["route_sets"] == surgical["route_sets"],
        "token_cost": "NOT_MEASURED",
        "task_success": "NOT_MEASURED",
    }


def _synthetic_control(
    *, missing_identifier: bool = False, extra_consumers: int = 0,
) -> tuple[SchemaRouter, NativeConceptCatalog, NativeSchemaGraphIndex]:
    """Synthetic original source schemas only; no invoker/provider calls.

    The fixture is not an AST CodeGraph installation or a genuine provider.
    The same two complete required inputs and read-only typed output are
    frozen for each paired arm, principal and language alias.
    """
    aliases = ("case status", "문의 상태", "問い合わせ状態")
    text = " ".join(aliases)
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    original = ("contact_id", "region_id")
    producer_names = original[:1] if missing_identifier else original
    router.add_tool(ToolSpec(
        name="contacts", source_type="crm", license="synthetic-owner-review",
        description=f"{text} producer",
        endpoints=[EndpointSpec(
            name="read", description=f"{text} source identifiers", read_only=True,
            output_fields=[FieldSpec(
                name=field, semantic_id=f"crm.{field}", identifier=True,
                json_schema={"type": "string"},
            ) for field in producer_names],
            output_schema={
                "type": "object",
                "properties": {field: {"type": "string"} for field in producer_names},
                "required": list(producer_names),
            },
        )],
    ))
    for i in range(extra_consumers + 1):
        name = "cases" if i == 0 else f"cases_{i}"
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="synthetic-owner-review",
            description=f"{text} consumer",
            endpoints=[EndpointSpec(
                name="read", description=f"{text} case status", read_only=True,
                parameters=[ParameterSpec(
                    name=field, semantic_id=f"crm.{field}", required=True,
                    json_schema={"type": "string"},
                ) for field in original],
                input_schema={
                    "type": "object",
                    "properties": {field: {"type": "string"} for field in original},
                    "required": list(original),
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="case_status", aliases=aliases,
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="synthetic-owner-review",
    ),))
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    return router, catalog, index


def run_synthetic_controls() -> dict[str, Any]:
    """Preregistered paired statuses and bytes; no model, tokenizer or IO."""
    cases = (
        ("joined_en", "case status", False, 0, False),
        ("joined_ko", "문의 상태", False, 0, False),
        ("joined_ja", "問い合わせ状態", False, 0, False),
        ("no_fit", "case status", True, 0, False),
        ("denied", "case status", False, 0, True),
        ("over_k", "case status", False, 5, False),
    )
    rows: list[dict[str, Any]] = []
    for case_id, query, missing_identifier, extra_consumers, denied in cases:
        router, catalog, index = _synthetic_control(
            missing_identifier=missing_identifier,
            extra_consumers=extra_consumers,
        )
        principal = PrincipalContext(
            subject="synthetic-denied" if denied else "synthetic-reader",
            roles=("viewer",) if denied else ("reader",),
        )
        pair = compare_contexts(
            router, query, principal=principal, catalog=catalog, index=index,
        )
        rows.append({
            "case_id": case_id,
            "status": pair["full_envelope"]["status"],
            "snapshot_id": pair["full_envelope"]["index_snapshot_id"],
            "selected_route_ids": pair["full_envelope"]["route_ids"],
            "selected_path_parity": pair["selected_path_parity"],
            "full_utf8_json_bytes": pair["full_utf8_json_bytes"],
            "surgical_utf8_json_bytes": pair["surgical_utf8_json_bytes"],
            "surgical_to_full_ratio": pair["surgical_to_full_ratio"],
        })
    return {
        "issue": 1711,
        "evidence_tier": "E0_SYNTHETIC_NONEXECUTING",
        "fixed_k": 5,
        "encoding": "UTF-8 compact sorted-key JSON, ensure_ascii=False",
        "independent_quality_evidence": False,
        "calibrated_no_fit": False,
        "executable_authority": False,
        "token_cost": "NOT_MEASURED",
        "task_success": "NOT_MEASURED",
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output stable JSON report")
    args = parser.parse_args()
    result = run_synthetic_controls()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        for case in result["cases"]:
            print(
                f"{case['case_id']}: {case['status']} "
                f"full={case['full_utf8_json_bytes']} "
                f"reference={case['surgical_utf8_json_bytes']} "
                f"ratio={case['surgical_to_full_ratio']:.3f}"
            )
        print("Tokens, cost, task success: NOT_MEASURED")


if __name__ == "__main__":
    main()

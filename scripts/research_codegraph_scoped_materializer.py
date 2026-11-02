"""Research-only, revalidated disclosure of selected original G5 schemas.

The model sees a nonexecuting reference, never a source grant. Every schema
request rechecks the host's original policy, principal, registry and source.
Actual calls remain exclusively in ``execute_scoped_host_call``.
"""

from __future__ import annotations

import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from typing import Any, NoReturn

from schemarouter import NativeConceptCatalog, PrincipalContext, SchemaRouter
from schemarouter.concept_graph_retrieval import (
    NativeConceptGraphSelection,
    retrieve_authorized_concept_graph,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    _authorization_policy_receipt,
    _principal_claims_canonical,
    capture_authorized_agent_tool_surface,
)

_EPISODE_HMAC_KEY = secrets.token_bytes(32)
STRICT_G5_K = 5


def _deny() -> NoReturn:
    # One error surface for unknown, absent, restricted and stale route IDs.
    raise PolicyViolationError("scoped schema request denied")


@dataclass(frozen=True, slots=True)
class SurgicalEpisode:
    """Host-private selection state; NOT a callable authorization token."""

    router: SchemaRouter = field(repr=False, compare=False)
    original_query: str
    principal: PrincipalContext = field(repr=False, compare=False)
    catalog: NativeConceptCatalog = field(repr=False, compare=False)
    index: NativeSchemaGraphIndex = field(repr=False, compare=False)
    selection: NativeConceptGraphSelection
    witness: tuple[Any, ...] = field(repr=False)
    policy_receipt: str = field(repr=False)
    principal_claims: str = field(repr=False)
    catalog_json: str = field(repr=False)
    _receipt: str = field(default="", repr=False, compare=False)

    @property
    def public_reference(self) -> dict[str, Any]:
        """Safe path evidence, with no original executable tool schemas."""
        _assert_episode_unchanged(self)
        view = _capture_checked_view(self)
        return {
            "status": "complete",
            "context_format": "graph_references_only",
            "index_snapshot_id": self.selection.snapshot_id,
            "registry_version": self.selection.registry_version,
            "requested_k": STRICT_G5_K,
            "route_ids": list(self.selection.route_ids),
            "route_sets": [
                {
                    "route_ids": list(path.route_ids),
                    "route_fingerprints": [list(value) for value in path.route_fingerprints],
                    "required_semantic_ids": list(path.required_semantic_ids),
                    "parameter_bindings": [list(value) for value in path.parameter_bindings],
                    "visible_output_fields": [
                        {"route_id": route_id,
                         "fields": sorted(view._visible_output_names[route_id])}
                        for route_id in path.route_ids
                    ],
                }
                for path in self.selection.route_sets
            ],
            "requires_source_schema_materialization": True,
            "tool_call_ready": False,
            "independent_quality_evidence": False,
            "calibrated_no_fit": False,
            "executable_authority": False,
        }


def _episode_receipt(episode: SurgicalEpisode) -> str:
    """Detect in-process modification of host-private selected path identity."""
    try:
        payload = {
            "router_id": id(episode.router),
            "principal_id": id(episode.principal),
            "catalog_id": id(episode.catalog),
            "index_id": id(episode.index),
            "query": episode.original_query,
            "selection": asdict(episode.selection),
            "witness": repr(episode.witness),
            "policy_receipt": episode.policy_receipt,
            "principal_claims": episode.principal_claims,
            "catalog_json": episode.catalog_json,
        }
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, AttributeError, OverflowError, RecursionError):
        _deny()
    return hmac.digest(_EPISODE_HMAC_KEY, canonical, "sha256").hex()


def _assert_episode_unchanged(episode: SurgicalEpisode) -> None:
    if type(episode) is not SurgicalEpisode or (
        type(episode._receipt) is not str or
        not hmac.compare_digest(episode._receipt, _episode_receipt(episode))
    ):
        _deny()
    episode.router._check_retrieval_authority_witness(episode.witness)
    if not hmac.compare_digest(
        episode.policy_receipt,
        _authorization_policy_receipt(episode.router.authorization_policy),
    ) or episode.principal_claims != _principal_claims_canonical(episode.principal):
        _deny()
    if episode.catalog_json != episode.catalog.model_dump_json():
        _deny()
    episode.index.field_index._assert_source(episode.router)


def _verify_view_against_selection(
    episode: SurgicalEpisode,
    view: AuthorizedAgentToolSurface,
) -> None:
    selection = episode.selection
    if (
        selection.status != "complete"
        or selection.requested_k != STRICT_G5_K
        or not 1 <= len(selection.route_ids) <= STRICT_G5_K
        or len(set(selection.route_ids)) != len(selection.route_ids)
        or selection.independent_quality_evidence
        or selection.calibrated_no_fit
        or selection.executable_authority
        or view.independent_quality_evidence
        or view.executable_authority
        or view.original_query != episode.original_query
        or view.witness != episode.witness
        or view._authorization_policy_receipt != episode.policy_receipt
        or view._principal_claims_snapshot != episode.principal_claims
        or not set(selection.route_ids).issubset(view.visible_route_ids)
    ):
        _deny()
    scoped = {route.route_id: route for route in view._semantic_source_routes}
    for path in selection.route_sets:
        if not set(path.route_ids).issubset(selection.route_ids):
            _deny()
        for route_id, tool_fp, endpoint_fp in path.route_fingerprints:
            route = scoped.get(route_id)
            if route is None or (
                route.tool_fingerprint, route.endpoint_fingerprint
            ) != (tool_fp, endpoint_fp):
                _deny()
        if len(path.route_ids) == 2 and any(
            source_field not in view._visible_output_names[path.route_ids[0]]
            for _, source_field in path.parameter_bindings
        ):
            _deny()
    view.assert_source_unchanged()


def _capture_checked_view(episode: SurgicalEpisode) -> AuthorizedAgentToolSurface:
    _assert_episode_unchanged(episode)
    renewed = retrieve_authorized_concept_graph(
        episode.router, episode.original_query, principal=episode.principal,
        catalog=episode.catalog, index=episode.index, k=STRICT_G5_K,
    )
    if renewed != episode.selection:
        _deny()
    view = capture_authorized_agent_tool_surface(
        episode.router, episode.original_query, principal=episode.principal,
    )
    _assert_episode_unchanged(episode)
    _verify_view_against_selection(episode, view)
    return view


def capture_surgical_episode(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    k: int = STRICT_G5_K,
) -> SurgicalEpisode:
    """Pin the complete original G5 path, principal and source continuity."""
    if type(k) is not int or k != STRICT_G5_K:
        raise ValueError("surgical materialization requires strict K5")
    witness = router._retrieval_authority_witness()
    policy_receipt = _authorization_policy_receipt(router.authorization_policy)
    principal_claims = _principal_claims_canonical(principal)
    catalog_json = catalog.model_dump_json()
    selection = retrieve_authorized_concept_graph(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if selection.status != "complete":
        _deny()
    episode = SurgicalEpisode(
        router=router, original_query=query, principal=principal, catalog=catalog,
        index=index, selection=selection, witness=witness,
        policy_receipt=policy_receipt, principal_claims=principal_claims,
        catalog_json=catalog_json,
    )
    object.__setattr__(episode, "_receipt", _episode_receipt(episode))
    _capture_checked_view(episode)
    return episode


def materialize_scoped_original_schemas(
    episode: SurgicalEpisode, selected_route_ids: list[str],
) -> tuple[AuthorizedAgentToolSurface, list[dict[str, Any]]]:
    """Return a fresh checked host view and the exact requested schemas.

    The caller may pass the view only to the **existing** scoped invoker;
    neither this result nor the model's schema request grants permission.
    """
    _assert_episode_unchanged(episode)
    if (
        type(selected_route_ids) is not list
        or not 1 <= len(selected_route_ids) <= STRICT_G5_K
        or any(type(route) is not str for route in selected_route_ids)
        or len(set(selected_route_ids)) != len(selected_route_ids)
        or not set(selected_route_ids).issubset(episode.selection.route_ids)
    ):
        _deny()
    view = _capture_checked_view(episode)
    definitions = view.tool_definitions(selected_route_ids, k=STRICT_G5_K)
    _verify_view_against_selection(episode, view)
    _assert_episode_unchanged(episode)
    return view, definitions


def request_scoped_source_schema(
    episode: SurgicalEpisode, selected_route_ids: list[str],
) -> list[dict[str, Any]]:
    """Nonexecuting model-facing entry point: selected original schemas only."""
    _, definitions = materialize_scoped_original_schemas(episode, selected_route_ids)
    return definitions

"""Opt-in native declared-concept selector for the EXISTING EVAL-FIXED5-OPTIN loop.

This is a source-pinned, principal-scoped *candidate selector* only. It
cannot see task gold, agent state, fixture data or a host invoker, and
cannot confer execution privileges or independently calibrated no-fit.
"""
from __future__ import annotations

import hmac
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256

from schemarouter import PolicyViolationError
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.concept_retrieval import (
    NativeConceptCatalog,
    resolve_native_concepts,
    retrieve_authorized_concepts,
)
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import (
    IndexedNativeFieldCandidate,
    NativeSchemaPostingIndex,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    compile_paper_understood_direct_plan,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_authorized_fixed5_decision_bridge import _visible_fingerprints

STRICT_K = 5


def _catalog_content_digest(catalog: NativeConceptCatalog) -> str:
    """Stable serialized owner contract; integrity detection, not signature."""
    raw = json.dumps(
        catalog.model_dump(mode="json"),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass
class AuthorizedConceptFixed5Selector:
    """Callback(query, scoped_route_ids), compatible with existing agent E0.

    The host supplies a previously approved concept catalog. Gold labels
    MUST NEVER be put into this catalog or used to choose matching aliases.
    """

    view: AuthorizedAgentToolSurface
    catalog: NativeConceptCatalog
    last_status: str | None = field(default=None, init=False)
    independent_quality_evidence: bool = field(default=False, init=False)
    calibrated_no_fit: bool = field(default=False, init=False)
    executable_authority: bool = field(default=False, init=False)
    _pinned: dict[str, tuple[str, str]] = field(init=False, repr=False)
    _catalog_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, NativeConceptCatalog):
            raise ValueError("trusted native concept catalog required")
        self.view.assert_source_unchanged()
        # Force validation before first model exposure, not only at first call.
        NativeConceptCatalog.model_validate(
            self.catalog.model_dump(mode="python"), strict=True,
        )
        self._catalog_digest = _catalog_content_digest(self.catalog)
        self._pinned = _visible_fingerprints(self.view)

    def _assert_catalog_unchanged(self) -> None:
        """Revalidate the approved ontology after untrusted ranking callbacks."""
        try:
            NativeConceptCatalog.model_validate(
                self.catalog.model_dump(mode="python"), strict=True,
            )
            digest = _catalog_content_digest(self.catalog)
        except (ValueError, TypeError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("concept catalog mutated after approval") from exc
        if not hmac.compare_digest(digest, self._catalog_digest):
            raise PolicyViolationError("concept catalog mutated after approval")

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        try:
            NativeConceptCatalog.model_validate(
                self.catalog.model_dump(mode="python"), strict=True,
            )
            current_digest = _catalog_content_digest(self.catalog)
        except (ValueError, TypeError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("concept catalog mutated after approval") from exc
        if not hmac.compare_digest(current_digest, self._catalog_digest):
            raise PolicyViolationError("concept catalog mutated after approval")
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise PolicyViolationError("concept selector query/view mismatch")
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("concept selector source revision drift")

        try:
            # Declaration validation, ambiguity and type conflicts fail closed.
            # Only the EXACT unknown-concept case is an E0 abstention.
            resolve_native_concepts(query, catalog=self.catalog)
        except ValueError as exc:
            if str(exc) != "no declared concept in query":
                raise
            self.view.assert_source_unchanged()
            self.last_status = "no_declared_concept_not_calibrated_no_fit"
            return []

        result = retrieve_authorized_concepts(
            self.view.router,
            query,
            principal=self.view._principal,
            catalog=self.catalog,
            k=STRICT_K,
        )
        self.view.assert_source_unchanged()
        current = _visible_fingerprints(self.view)
        if current != self._pinned:
            raise PolicyViolationError("concept selector source revision drift")

        candidates = result.candidates
        names = [candidate.route_id for candidate in candidates]
        if (
            result.requested_k != STRICT_K
            or result.registry_version != self.view.witness[1]
            or type(names) is not list
            or len(names) > STRICT_K
            or len(set(names)) != len(names)
            or not set(names).issubset(source_ids)
            or any(
                (
                    candidate.tool_fingerprint,
                    candidate.endpoint_fingerprint,
                ) != self._pinned[candidate.route_id]
                for candidate in candidates
            )
        ):
            raise PolicyViolationError("concept selector candidate scope mismatch")
        self.last_status = (
            "unverified_declared_concept_candidates" if names
            else "declared_concept_unmet_not_calibrated_no_fit"
        )
        return names


@dataclass
class AuthorizedConceptGraphFixed5Selector(AuthorizedConceptFixed5Selector):
    """Opt-in canonical G5 composer for the *existing* agent callback.

    Does not receive task gold, the host invoker or source observations. The
    output only chooses which already captured, principal-scoped tool schemas
    the existing EVAL-FIXED5-OPTIN loop may disclose to its model.
    """

    index: NativeSchemaGraphIndex

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.index, NativeSchemaGraphIndex):
            raise ValueError("native source-pinned graph index required")
        self.index.field_index._assert_source(self.view.router)
        if self.index.field_index.registry_version != self.view.witness[1]:
            raise PolicyViolationError("graph selector source revision mismatch")

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        try:
            NativeConceptCatalog.model_validate(
                self.catalog.model_dump(mode="python"), strict=True,
            )
            current_digest = _catalog_content_digest(self.catalog)
        except (ValueError, TypeError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("concept catalog mutated after approval") from exc
        if not hmac.compare_digest(current_digest, self._catalog_digest):
            raise PolicyViolationError("concept catalog mutated after approval")
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise PolicyViolationError("graph selector query/view mismatch")
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("graph selector source revision drift")

        try:
            resolve_native_concepts(query, catalog=self.catalog)
        except ValueError as exc:
            if str(exc) != "no declared concept in query":
                raise
            self.view.assert_source_unchanged()
            self.last_status = "no_declared_concept_not_calibrated_no_fit"
            return []

        selected = retrieve_authorized_concept_graph(
            self.view.router, query, principal=self.view._principal,
            catalog=self.catalog, index=self.index, k=STRICT_K,
        )
        self.view.assert_source_unchanged()
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("graph selector source revision drift")
        routes = list(selected.route_ids)
        if (
            selected.requested_k != STRICT_K
            or selected.registry_version != self.view.witness[1]
            or selected.snapshot_id != self.index.field_index.snapshot_id
            or len(routes) > STRICT_K
            or len(set(routes)) != len(routes)
            or not set(routes).issubset(source_ids)
            or selected.independent_quality_evidence
            or selected.calibrated_no_fit
            or selected.executable_authority
            or any(
                (tool_fp, endpoint_fp) != self._pinned[route_id]
                for route_set in selected.route_sets
                for route_id, tool_fp, endpoint_fp in route_set.route_fingerprints
            )
        ):
            raise PolicyViolationError("graph selector candidate scope mismatch")
        if selected.status != "complete":
            if routes or selected.route_sets:
                raise PolicyViolationError("graph selector returned unsafe abstention")
            self.last_status = selected.status
            return []
        if not routes or not selected.route_sets:
            raise PolicyViolationError("graph selector incomplete route set")
        try:
            # Enforces actual serialized model-definition byte cap before the
            # external agent sees even one of the selected route schemas.
            self.view.tool_definitions(routes, k=STRICT_K)
        except ValueError as exc:
            if "exceed" not in str(exc) or "byte cap" not in str(exc):
                raise
            self.view.assert_source_unchanged()
            self.last_status = "budget_unsatisfied"
            return []
        self.view.assert_source_unchanged()
        self.last_status = "complete"
        return routes


@dataclass
class AuthorizedIndexedFieldFixed5Selector(AuthorizedConceptFixed5Selector):
    """Research-only direct FieldGroup index → original fixed5 agent callback.

    A complete source-native output field group is not proof that the host can
    provide mandatory request arguments. Bound-input routes are excluded here;
    the existing G5 selector handles proved producer→consumer joins instead.
    The ranker, when provided, chooses only among detached qualified offsets.
    """

    index: NativeSchemaPostingIndex
    research_ranker: Callable[
        [str, tuple[IndexedNativeFieldCandidate, ...], int], tuple[int, ...],
    ] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.index) is not NativeSchemaPostingIndex:
            raise ValueError("source-pinned native posting index required")
        if self.research_ranker is not None and not callable(self.research_ranker):
            raise ValueError("bounded research ranker must be callable")
        self.index._assert_source(self.view.router)
        if self.index.registry_version != self.view.witness[1]:
            raise PolicyViolationError("indexed selector source revision mismatch")

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise PolicyViolationError("indexed selector query/view mismatch")
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("indexed selector source revision drift")

        try:
            # Only exact source-owner declared concept mentions qualify.
            resolve_native_concepts(query, catalog=self.catalog)
        except ValueError as exc:
            if str(exc) != "no declared concept in query":
                raise
            self.view.assert_source_unchanged()
            self._assert_catalog_unchanged()
            self.last_status = "no_declared_concept_not_calibrated_no_fit"
            return []

        result = self.index.lookup_concepts(
            self.view.router, query, catalog=self.catalog,
            principal=self.view._principal, k=STRICT_K,
            input_free_only=True, _research_ranker=self.research_ranker,
        )
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("indexed selector source revision drift")
        routes = [candidate.route_id for candidate in result.candidates]
        if (
            result.requested_k != STRICT_K
            or result.registry_version != self.view.witness[1]
            or result.index_snapshot_id != self.index.snapshot_id
            or len(routes) > STRICT_K
            or len(set(routes)) != len(routes)
            or not set(routes).issubset(source_ids)
            or any(
                (candidate.tool_fingerprint, candidate.endpoint_fingerprint)
                != self._pinned[candidate.route_id]
                for candidate in result.candidates
            )
        ):
            raise PolicyViolationError("indexed selector candidate scope mismatch")
        if result.status not in {"complete", "ranked_unverified"}:
            if routes or result.status not in {
                "no_proven_hit", "over_k_unranked", "ranker_abstained_unverified",
            }:
                raise PolicyViolationError("indexed selector returned unsafe abstention")
            self.last_status = result.status
            return []
        if not routes or result.experimental_ranked != (result.status == "ranked_unverified"):
            raise PolicyViolationError("indexed selector incomplete source evidence")
        try:
            self.view.tool_definitions(routes, k=STRICT_K)
        except ValueError as exc:
            if "exceed" not in str(exc) or "byte cap" not in str(exc):
                raise
            self.view.assert_source_unchanged()
            self._assert_catalog_unchanged()
            self.last_status = "budget_unsatisfied"
            return []
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        self.last_status = result.status
        return routes


def _paper_declaration_digest(
    value: PaperIntentRegistry | PaperUnderstanding,
) -> str:
    raw = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass
class AuthorizedPaperUnderstoodDirectFixed5Selector(AuthorizedConceptFixed5Selector):
    """Structured paper Understand → source-verified existing agent tool menu.

    Model hints are not tool arguments. The current principal-scoped source
    surface, not this callback or the model, owns final route visibility.
    """

    index: NativeSchemaGraphIndex
    intent_registry: PaperIntentRegistry
    understanding: PaperUnderstanding
    _intent_digest: str = field(init=False, repr=False)
    _understanding_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.index, NativeSchemaGraphIndex):
            raise ValueError("original native graph index required")
        if not isinstance(self.intent_registry, PaperIntentRegistry):
            raise ValueError("host-approved paper intent registry required")
        if not isinstance(self.understanding, PaperUnderstanding):
            raise ValueError("bounded structured understanding required")
        self._assert_paper_declarations_valid()
        self._intent_digest = _paper_declaration_digest(self.intent_registry)
        self._understanding_digest = _paper_declaration_digest(self.understanding)
        self.index.field_index._assert_source(self.view.router)
        if self.index.field_index.registry_version != self.view.witness[1]:
            raise PolicyViolationError("paper selector source revision mismatch")

    def _assert_paper_declarations_valid(self) -> None:
        try:
            PaperIntentRegistry.model_validate(
                self.intent_registry.model_dump(mode="python"), strict=True,
            )
            PaperUnderstanding.model_validate(
                self.understanding.model_dump(mode="python"), strict=True,
            )
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("paper selector declaration invalid") from exc

    def _assert_paper_declarations_unchanged(self) -> None:
        self._assert_paper_declarations_valid()
        try:
            intent_digest = _paper_declaration_digest(self.intent_registry)
            understanding_digest = _paper_declaration_digest(self.understanding)
        except (TypeError, ValueError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("paper selector declaration invalid") from exc
        if (
            not hmac.compare_digest(intent_digest, self._intent_digest)
            or not hmac.compare_digest(
                understanding_digest, self._understanding_digest,
            )
        ):
            raise PolicyViolationError("paper selector declaration changed")

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        self._assert_paper_declarations_unchanged()
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise PolicyViolationError("paper selector query/view mismatch")
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("paper selector source revision drift")

        plan = compile_paper_understood_direct_plan(
            self.view.router, self.understanding,
            principal=self.view._principal,
            catalog=self.catalog,
            intent_registry=self.intent_registry,
            index=self.index, k=STRICT_K,
        )
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        self._assert_paper_declarations_unchanged()
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("paper selector source revision drift")

        if (
            plan.requested_k != STRICT_K
            or plan.snapshot_id != self.index.field_index.snapshot_id
            or plan.registry_version != self.view.witness[1]
            or plan.executable_authority
            or plan.bindings
        ):
            raise PolicyViolationError("paper selector invalid original proof")
        if plan.status in {
            "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
        }:
            if plan.calls:
                raise PolicyViolationError("paper selector abstention exposed tools")
            self.last_status = plan.status
            return []
        if plan.status not in {"ready", "requires_arguments"} or not plan.calls:
            raise PolicyViolationError("paper selector unverified direct evidence")

        routes = [receipt.route_id for receipt in plan.calls]
        if (
            len(routes) > STRICT_K
            or len(set(routes)) != len(routes)
            or not set(routes).issubset(source_ids)
            or any(
                (
                    receipt.call.tool_fingerprint,
                    receipt.call.schema_fingerprint,
                ) != self._pinned[receipt.route_id]
                for receipt in plan.calls
            )
        ):
            raise PolicyViolationError("paper selector candidate scope mismatch")
        try:
            self.view.tool_definitions(routes, k=STRICT_K)
        except ValueError as exc:
            if "exceed" not in str(exc) or "byte cap" not in str(exc):
                raise
            self.view.assert_source_unchanged()
            self._assert_catalog_unchanged()
            self._assert_paper_declarations_unchanged()
            self.last_status = "budget_unsatisfied"
            return []
        self.view.assert_source_unchanged()
        self._assert_catalog_unchanged()
        self._assert_paper_declarations_unchanged()
        self.last_status = plan.status
        return routes

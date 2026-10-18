"""Opt-in native declared-concept selector for the EXISTING EVAL-FIXED5-OPTIN loop.

This is a source-pinned, principal-scoped *candidate selector* only. It
cannot see task gold, agent state, fixture data or a host invoker, and
cannot confer execution privileges or independently calibrated no-fit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import (
    NativeConceptCatalog,
    retrieve_authorized_concepts,
    resolve_native_concepts,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_authorized_fixed5_decision_bridge import _visible_fingerprints

STRICT_K = 5


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

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, NativeConceptCatalog):
            raise ValueError("trusted native concept catalog required")
        self.view.assert_source_unchanged()
        # Force validation before first model exposure, not only at first call.
        NativeConceptCatalog.model_validate(
            self.catalog.model_dump(mode="python"), strict=True,
        )
        self._pinned = _visible_fingerprints(self.view)

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
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

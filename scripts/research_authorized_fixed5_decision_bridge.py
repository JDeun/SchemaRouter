"""Opt-in authorized fixed-K5 decision bridge for the existing agent evaluator.

This is a research-only callback, not a product default, no-fit classifier,
execution permission, or independent multilingual task-utility result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from schemarouter import PolicyViolationError
from schemarouter.decisions import DecisionBackend
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
)
from scripts.research_bounded_authorized_semantic_diagnostic import (
    DiagnosticSemanticShortlist,
    propose_bounded_semantic_shortlist,
)

STRICT_K = 5
_ALLOWED_STATUSES = frozenset({
    "empty_visible_catalog_not_no_fit",
    "backend_abstained_not_calibrated_no_fit",
    "unverified_full_k_model_ranking",
    "unverified_partial_k_model_ranking",
})


def _visible_fingerprints(
    view: AuthorizedAgentToolSurface,
) -> dict[str, tuple[str, str]]:
    """Check exact native source fingerprints, never descriptions or gold."""
    source: dict[str, tuple[str, str]] = {}
    for tool in view.router.registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            if route in source:
                raise PolicyViolationError("duplicate native source route")
            if route in view.visible_route_ids:
                source[route] = (tool.fingerprint, endpoint.fingerprint)
    if set(source) != set(view.visible_route_ids):
        raise PolicyViolationError("scoped native source fingerprints incomplete")
    return source


@dataclass
class AuthorizedFixed5DecisionSelector:
    """Callable(query, visible_ids) for EVAL-FIXED5-OPTIN only.

    The backend only receives currently authorized native metadata through
    the existing bounded source-scoped comparator. It NEVER sees fixture
    gold, evaluation labels, provider callables, or executor state.
    """

    view: AuthorizedAgentToolSurface
    backend: DecisionBackend = field(repr=False)
    max_model_input_bytes: int = 131072
    last_status: str | None = field(default=None, init=False)
    last_model_input_bytes: int | None = field(default=None, init=False)
    calibrated_no_fit: bool = field(default=False, init=False)
    executable_authority: bool = field(default=False, init=False)
    independent_quality_evidence: bool = field(default=False, init=False)
    _pinned_fingerprints: dict[str, tuple[str, str]] = field(
        init=False, repr=False,
    )

    def __post_init__(self) -> None:
        if (
            type(self.max_model_input_bytes) is not int
            or not 1 <= self.max_model_input_bytes <= 131072
        ):
            raise ValueError("invalid fixed5 comparator input budget")
        self.view.assert_source_unchanged()
        self._pinned_fingerprints = _visible_fingerprints(self.view)

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(source_ids) != len(set(source_ids))
        ):
            raise PolicyViolationError("fixed5 source/view query mismatch")
        if _visible_fingerprints(self.view) != self._pinned_fingerprints:
            raise PolicyViolationError("fixed5 native source fingerprint drift")

        result: DiagnosticSemanticShortlist = propose_bounded_semantic_shortlist(
            self.view.router,
            query,
            principal=self.view._principal,
            backend=self.backend,
            k=STRICT_K,
            max_model_input_bytes=self.max_model_input_bytes,
        )
        self.view.assert_source_unchanged()
        if _visible_fingerprints(self.view) != self._pinned_fingerprints:
            raise PolicyViolationError("fixed5 native source fingerprint drift")
        if (
            result.status not in _ALLOWED_STATUSES
            or result.executable_authority
            or result.independent_quality_evidence
            or result.calibrated_no_fit
            or type(result.registered_candidate_count) is not int
            or result.registered_candidate_count != len(source_ids)
            or result.registry_version != self.view.witness[1]
            or len(result.route_ids) > STRICT_K
            or len(result.route_ids) != len(set(result.route_ids))
            or any(type(route) is not str for route in result.route_ids)
            or not set(result.route_ids).issubset(source_ids)
            or len(result.source_tool_fingerprints) != len(result.route_ids)
            or len(result.source_endpoint_fingerprints) != len(result.route_ids)
            or any(
                (tool_fp, endpoint_fp) != self._pinned_fingerprints[route]
                for route, tool_fp, endpoint_fp in zip(
                    result.route_ids,
                    result.source_tool_fingerprints,
                    result.source_endpoint_fingerprints,
                    strict=True,
                )
            )
        ):
            raise PolicyViolationError("fixed5 diagnostic violated source contract")
        # An abstention / empty catalog is not proof that the user task is
        # unsupported. Never refill from gold or widen K in response.
        self.last_status = result.status
        self.last_model_input_bytes = result.model_input_bytes
        return list(result.route_ids)

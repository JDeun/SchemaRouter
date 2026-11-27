"""Historical query-only field discovery and compilation, checkout only.

These wrappers retain the pre-retirement session behavior for the existing
source/coverage regressions. Configured Algorithm 1 uses Understand instead.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schemarouter.authorization import PrincipalContext
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from scripts.research_legacy_paper_field_retrieval import PaperFieldCoverage, retrieve_paper_field_coverage
from scripts.research_legacy_paper_typed_plan import compile_paper_typed_tool_plan

if TYPE_CHECKING:
    from schemarouter.field_routing_session import SchemaFieldRoutingSession


def research_discover_fields(
    self: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    k: int = 5,
) -> PaperFieldCoverage:
    """Return field-complete route alternatives or abstain; no data I/O."""
    catalog = self._require_catalog()
    return retrieve_paper_field_coverage(
        self._router, query, principal=principal,
        catalog=catalog, index=self._index, k=k,
    )

def research_compile_fields(
    self: SchemaFieldRoutingSession,
    query: str,
    *,
    principal: PrincipalContext,
    alternative_index: int = 0,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    k: int = 5,
) -> PaperTypedToolPlan:
    """Describe typed call shapes, bindings and field metadata, not execution.

    Even a `ready` receipt is not an executable authorization grant.
    """
    catalog = self._require_catalog()
    return compile_paper_typed_tool_plan(
        self._router, query, principal=principal,
        catalog=catalog, index=self._index,
        alternative_index=alternative_index,
        host_source_arguments=host_source_arguments, k=k,
    )

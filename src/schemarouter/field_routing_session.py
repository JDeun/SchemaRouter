"""Prepared schema-only field routing over host-owned provider contracts.

One reusable public entry point for the original-paper P1/P2 proof path.
Neither discovery nor compilation invokes providers or retrieves data rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .native_graph_index import NativeSchemaGraphIndex
from .native_semantic_index import NativeSchemaPostingIndex
from .paper_field_retrieval import PaperFieldCoverage, retrieve_paper_field_coverage
from .paper_query_understanding import PaperFieldModel, compile_model_query
from .paper_typed_tool_plan import PaperTypedToolPlan, compile_paper_typed_tool_plan
from .paper_understood_direct_plan import PaperIntentRegistry, PaperUnderstanding
from .paper_understood_graph_plan import compile_paper_understood_graph_plan

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class SchemaFieldRoutingSession:
    """Reuse an attested index to locate necessary schema fields, not records.

    The index is tied to one exact router registry revision. Reprepare after
    schema changes; no automatic source refresh or background provider query.
    Authorization and scoped visibility are checked live on *every* query.
    """

    # No authorization-neutral posting IDs, route fingerprints or owner
    # declarations may leak through repr/logging of this public handle.
    _router: SchemaRouter = field(repr=False)
    _catalog: NativeConceptCatalog = field(repr=False)
    _index: NativeSchemaGraphIndex = field(repr=False)

    @classmethod
    def prepare(
        cls,
        router: SchemaRouter,
        *,
        catalog: NativeConceptCatalog,
        approved_host_roots: frozenset[str] = frozenset(),
    ) -> SchemaFieldRoutingSession:
        """Index registered schemas once using host-reviewed field semantics."""
        if not isinstance(catalog, NativeConceptCatalog):
            raise ValueError("owner-reviewed concept catalog required")
        if (
            type(approved_host_roots) is not frozenset
            or len(approved_host_roots) > 64
            or any(type(route) is not str for route in approved_host_roots)
        ):
            raise ValueError("explicit bounded host-approved route set required")
        if router.authorization_policy is None:
            raise PolicyViolationError(
                "field routing requires explicit source authorization policy"
            )

        # Revalidate and detach the owner's declaration so later caller-side
        # Pydantic mutation cannot silently change this prepared contract.
        reviewed = NativeConceptCatalog.model_validate(
            catalog.model_dump(mode="python"), strict=True,
        )
        field_index = NativeSchemaPostingIndex.build(router.registry)
        index = NativeSchemaGraphIndex.build(
            field_index, approved_host_roots=approved_host_roots,
        )
        field_index._assert_source(router)
        return cls(_router=router, _catalog=reviewed, _index=index)

    @property
    def snapshot_id(self) -> str:
        """Original schema index fingerprint used by every result."""
        return self._index.field_index.snapshot_id

    @property
    def indexed_route_count(self) -> int:
        """Registered endpoint count scanned only during preparation."""
        return self._index.field_index.indexed_route_count

    def discover(
        self,
        query: str,
        *,
        principal: PrincipalContext,
        k: int = 5,
    ) -> PaperFieldCoverage:
        """Return field-complete route alternatives or abstain; no data I/O."""
        return retrieve_paper_field_coverage(
            self._router, query, principal=principal,
            catalog=self._catalog, index=self._index, k=k,
            experimental_indexed_direct=True,
        )

    def compile(
        self,
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
        return compile_paper_typed_tool_plan(
            self._router, query, principal=principal,
            catalog=self._catalog, index=self._index,
            alternative_index=alternative_index,
            host_source_arguments=host_source_arguments, k=k,
            experimental_indexed_direct=True,
        )

    def compile_understood(
        self,
        understanding: PaperUnderstanding,
        *,
        principal: PrincipalContext,
        intent_registry: PaperIntentRegistry,
        host_source_arguments: dict[str, dict[str, Any]] | None = None,
        k: int = 5,
        max_hops: int = 2,
    ) -> PaperTypedToolPlan:
        """Compile untrusted structured Understand(q) hints to a source-proven plan.

        Only the host-reviewed intent/concept catalog defines field meanings.
        Model parameter hints are never treated as host-supplied arguments.
        No model or provider is invoked, even for a `ready` receipt.
        """
        return compile_paper_understood_graph_plan(
            self._router, understanding, principal=principal,
            catalog=self._catalog, intent_registry=intent_registry,
            index=self._index, host_source_arguments=host_source_arguments,
            k=k, max_hops=max_hops,
        )

    async def acompile_query(
        self,
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
        """Use a caller-owned model to suggest IDs, then prove source fields.

        No provider data is fetched. The model cannot authorize a route,
        expand source scope, or bind its proposed argument values.
        """
        return await compile_model_query(
            self, query, principal=principal, model=model,
            intent_registry=intent_registry,
            model_visible_intent_ids=model_visible_intent_ids,
            model_visible_concept_ids=model_visible_concept_ids,
            model_visible_tool_keys=model_visible_tool_keys,
            host_source_arguments=host_source_arguments, k=k, max_hops=max_hops,
            max_model_input_bytes=max_model_input_bytes,
            max_model_output_bytes=max_model_output_bytes,
        )

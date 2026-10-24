"""Read-only Algorithm 1 P1/P2 source receipts in the EXISTING #1477 agent E0 loop.

The host owns the principal-scoped native source, catalog and graph index.
The callback receives NO evaluator gold, model prompt, invoker or task state.
The emitted route IDs are *candidate disclosure*, never an execution grant.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass

from schemarouter import PolicyViolationError, compile_paper_field_toolcalls
from schemarouter.concept_retrieval import resolve_native_concepts
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    STRICT_K,
    AuthorizedConceptGraphFixed5Selector,
    _catalog_content_digest,
)
from scripts.research_authorized_fixed5_decision_bridge import _visible_fingerprints


@dataclass
class AuthorizedPaperFieldFixed5Selector(AuthorizedConceptGraphFixed5Selector):
    """Opt-in exact one-alternative P2 route IDs for an existing E0 callback.

    Multiple proven alternatives are deliberately *not* ranked or flattened.
    Existing model-visible scoped tool definitions are not yet projected down
    to the P2 minimal field list; no schema-token saving is claimed.
    """

    experimental_indexed_direct: bool = False

    def __post_init__(self) -> None:
        if type(self.experimental_indexed_direct) is not bool:
            raise ValueError("paper indexed direct mode must be boolean")
        super().__post_init__()

    def __call__(self, query: str, source_ids: tuple[str, ...]) -> list[str]:
        self.view.assert_source_unchanged()
        try:
            self.catalog.model_validate(
                self.catalog.model_dump(mode="python"), strict=True,
            )
            current_digest = _catalog_content_digest(self.catalog)
        except (ValueError, TypeError, OverflowError, AttributeError) as exc:
            raise PolicyViolationError("paper owner catalog mutated") from exc
        if not hmac.compare_digest(current_digest, self._catalog_digest):
            raise PolicyViolationError("paper owner catalog mutated")
        if (
            type(query) is not str
            or query != self.view.original_query
            or type(source_ids) is not tuple
            or source_ids != self.view.visible_route_ids
            or len(set(source_ids)) != len(source_ids)
        ):
            raise PolicyViolationError("paper query/principal view mismatch")
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("paper source revision drift")

        try:
            resolve_native_concepts(query, catalog=self.catalog)
        except ValueError as exc:
            if str(exc) != "no declared concept in query":
                raise
            self.view.assert_source_unchanged()
            self.last_status = "no_declared_concept_not_calibrated_no_fit"
            return []

        plan = compile_paper_field_toolcalls(
            self.view.router, query,
            principal=self.view._principal, catalog=self.catalog,
            index=self.index, k=STRICT_K,
            experimental_indexed_direct=self.experimental_indexed_direct,
        )
        self.view.assert_source_unchanged()
        if _visible_fingerprints(self.view) != self._pinned:
            raise PolicyViolationError("paper source revision drift")
        if (
            plan.requested_k != STRICT_K
            or plan.registry_version != self.view.witness[1]
            or plan.snapshot_id != self.index.field_index.snapshot_id
            or plan.experimental_indexed_direct != self.experimental_indexed_direct
            or plan.executable_authority
            or plan.independent_quality_evidence
        ):
            raise PolicyViolationError("paper plan scope or source mismatch")

        if plan.status != "complete":
            if plan.alternatives:
                raise PolicyViolationError("paper noncomplete plan exposed calls")
            self.last_status = plan.status
            return []
        if len(plan.alternatives) != 1:
            # Without an independently measured ranking policy, selecting
            # the first complete alternative would be hidden Top-K tuning.
            self.last_status = "multiple_unranked_alternatives"
            return []

        alternative = plan.alternatives[0]
        names = [f"{call.tool}.{call.endpoint}" for call in alternative.calls]
        if (
            not 1 <= len(names) <= STRICT_K
            or len(set(names)) != len(names)
            or not set(names).issubset(source_ids)
        ):
            raise PolicyViolationError("paper field candidate K5 mismatch")
        for route_id, call in zip(names, alternative.calls, strict=True):
            pinned = self._pinned.get(route_id)
            if (
                pinned is None
                or pinned != (call.tool_fingerprint, call.schema_fingerprint)
                or type(call.fields) is not list
                or not call.fields
                or len(set(call.fields)) != len(call.fields)
                or not set(call.fields).issubset(
                    self.view._visible_output_names.get(route_id, frozenset())
                )
                or call.arguments
            ):
                raise PolicyViolationError("paper field projection/source mismatch")

        try:
            self.view.tool_definitions(names, k=STRICT_K)
        except ValueError as exc:
            if "exceed" not in str(exc) or "byte cap" not in str(exc):
                raise
            self.view.assert_source_unchanged()
            self.last_status = "budget_unsatisfied"
            return []
        self.view.assert_source_unchanged()
        self.last_status = "complete"
        return names

    def projected_tool_definitions(
        self, query: str, source_ids: tuple[str, ...],
    ) -> list[dict[str, object]]:
        """Opt-in minimal model disclosure, never an execution grant.

        Recomputes the proof after selector validation rather than trusting
        cached, potentially stale field names. Input schemas are preserved.
        """
        import copy
        import json

        names = self(query, source_ids)
        if not names:
            return []
        plan = compile_paper_field_toolcalls(
            self.view.router, query,
            principal=self.view._principal, catalog=self.catalog,
            index=self.index, k=STRICT_K,
            experimental_indexed_direct=self.experimental_indexed_direct,
        )
        self.view.assert_source_unchanged()
        if plan.status != "complete" or len(plan.alternatives) != 1:
            raise PolicyViolationError("paper projection proof changed")
        calls = plan.alternatives[0].calls
        if [f"{call.tool}.{call.endpoint}" for call in calls] != names:
            raise PolicyViolationError("paper projection routes changed")
        original = self.view.tool_definitions(names, k=STRICT_K)
        projected: list[dict[str, object]] = []
        for route_id, call, definition in zip(names, calls, original, strict=True):
            if (
                not call.fields
                or len(set(call.fields)) != len(call.fields)
                or not set(call.fields).issubset(
                    self.view._visible_output_names[route_id]
                )
            ):
                raise PolicyViolationError("paper projection fields changed")
            item = copy.deepcopy(definition)
            # Never retain a full-schema description that may mention
            # unrelated fields, even if those fields are authorized.
            item["description"] = (
                f"Registered source route: {route_id}. "
                f"Selected output fields: {'; '.join(call.fields)}. "
                "Selection is not execution authorization."
            )
            projected.append(item)
        encoded = json.dumps(
            projected, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        from scripts.research_authorized_agent_tool_surface import (
            MAX_MODEL_TOOL_JSON_BYTES,
        )
        if len(encoded) > MAX_MODEL_TOOL_JSON_BYTES:
            raise ValueError("projected model tool definitions exceed research byte cap")
        self.view.assert_source_unchanged()
        return projected

"""Opt-in, source-scoped DecisionBackend adapter for direct native FieldGroup K5.

Source verification is performed by NativeSchemaPostingIndex.lookup *before*
this callback is invoked. This file only encodes the already-authorized
candidate receipt for an existing model-neutral DecisionBackend; it has no
registry, policy, source-invocation or task-gold access. E0, not trained.
"""
from __future__ import annotations

from dataclasses import dataclass

from schemarouter.decisions import (
    DecisionBackend,
    DecisionOption,
    DecisionRequest,
    choose_sync,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import (
    MAX_RESEARCH_RANKABLE_POSTINGS,
    STRICT_K,
    IndexedNativeFieldCandidate,
)

MAX_MODEL_INPUT_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class ResearchAuthorizedPostingDecisionRanker:
    """Explicit research-only callback for indexed *direct* field matches."""

    backend: DecisionBackend
    max_model_input_bytes: int = MAX_MODEL_INPUT_BYTES
    omit_identical_field_descriptions: bool = True

    def __post_init__(self) -> None:
        if (
            type(self.max_model_input_bytes) is not int
            or not 1 <= self.max_model_input_bytes <= MAX_MODEL_INPUT_BYTES
            or type(self.omit_identical_field_descriptions) is not bool
        ):
            raise ValueError("invalid direct posting decision input bounds")

    def __call__(
        self,
        query: str,
        paths: tuple[IndexedNativeFieldCandidate, ...],
        k: int,
    ) -> tuple[int, ...]:
        if (
            type(query) is not str
            or len(query.encode("utf-8")) > 512
            or type(k) is not int
            or k != STRICT_K
            or type(paths) is not tuple
            or not STRICT_K < len(paths) <= MAX_RESEARCH_RANKABLE_POSTINGS
            or any(type(path) is not IndexedNativeFieldCandidate for path in paths)
            or len({path.route_id for path in paths}) != len(paths)
        ):
            raise PolicyViolationError("direct ranker needs bounded source-verified paths")
        # The source receipts expose only currently permitted route names and
        # required, principal-visible output field names. Never send tool
        # descriptions, provider URLs, credentials, source records or task gold.
        descriptions = tuple(
            ",".join(path.required_output_fields) for path in paths
        )
        omit = (
            self.omit_identical_field_descriptions
            and len(set(descriptions)) == 1
        )
        options = [
            DecisionOption(
                id=f"route_{i:02d}",
                label=path.route_id,
                description="" if omit else f"fields={descriptions[i]}",
            )
            for i, path in enumerate(paths)
        ]
        request = DecisionRequest(
            query=query,
            options=options,
            max_selections=STRICT_K,
            context={
                "type": "SOURCE_VERIFIED_DIRECT_FIELDS_RESEARCH_E0",
                "independent_quality_evidence": False,
                "executable_authority": False,
                "calibrated_no_fit": False,
            },
        )
        if len(request.model_dump_json().encode("utf-8")) > self.max_model_input_bytes:
            raise PolicyViolationError("direct ranker model input byte cap")
        # choose_sync validates IDs, selection counts, duplicate choices and
        # asynchronous backends. The parent index verifies original evidence
        # again after this callback, even if the backend changes live policy.
        decision = choose_sync(self.backend, request)
        if decision.abstained:
            return ()
        if len(decision.selections) != STRICT_K:
            raise PolicyViolationError(
                "direct ranker returned partial fixed-K5 ranking"
            )
        offered = {option.id: i for i, option in enumerate(options)}
        return tuple(offered[item.option_id] for item in decision.selections)

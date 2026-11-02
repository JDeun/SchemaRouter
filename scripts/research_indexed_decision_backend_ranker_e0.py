"""Research-only DecisionBackend adapter for direct semantic posting K5.

The native posting lookup MUST qualify all original routes using current
principal authorization, data scope, availability and typed field coverage.
This module receives only those verified candidates; it cannot inspect the
registry, read tool arguments, execute endpoints, or use held-out task gold.
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
class ResearchIndexedFieldDecisionRanker:
    """Explicit E0 ranking callback for NativeSchemaPostingIndex.lookup."""

    backend: DecisionBackend
    max_model_input_bytes: int = MAX_MODEL_INPUT_BYTES
    omit_identical_descriptions: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.max_model_input_bytes) is not int
            or not 1 <= self.max_model_input_bytes <= MAX_MODEL_INPUT_BYTES
            or type(self.omit_identical_descriptions) is not bool
        ):
            raise ValueError("invalid bounded indexed research ranker configuration")

    def __call__(
        self,
        query: str,
        candidates: tuple[IndexedNativeFieldCandidate, ...],
        k: int,
    ) -> tuple[int, ...]:
        if (
            type(query) is not str
            or len(query.encode("utf-8")) > 512
            or type(k) is not int or k != STRICT_K
            or type(candidates) is not tuple
            or not STRICT_K < len(candidates) <= MAX_RESEARCH_RANKABLE_POSTINGS
            or any(type(c) is not IndexedNativeFieldCandidate for c in candidates)
            or len({c.route_id for c in candidates}) != len(candidates)
        ):
            raise PolicyViolationError("indexed model requires bounded scoped candidates")

        # Fingerprints are authorization receipts for the HOST only; the
        # backend sees original visible route and field NAMES, nothing else.
        descriptions = tuple(
            ", ".join(candidate.required_output_fields)
            for candidate in candidates
        )
        omit = (
            self.omit_identical_descriptions
            and len(set(descriptions)) == 1
        )
        options = [
            DecisionOption(
                id=f"route_{i:02d}",
                label=candidate.route_id,
                description="" if omit else descriptions[i],
            )
            for i, candidate in enumerate(candidates)
        ]
        request = DecisionRequest(
            query=query,
            options=options,
            max_selections=STRICT_K,
            context={
                "type": "INDEXED_AUTHORIZED_FIELDS_RESEARCH_E0",
                "independent_quality_evidence": False,
                "executable_authority": False,
                "calibrated_no_fit": False,
            },
        )
        if len(request.model_dump_json().encode("utf-8")) > self.max_model_input_bytes:
            raise PolicyViolationError("indexed research model input byte cap")
        # choose_sync verifies the original offered option set even when a
        # backend mutates its copy of the prompt or forges selected IDs.
        result = choose_sync(self.backend, request)
        if result.abstained:
            return ()
        if len(result.selections) != STRICT_K:
            raise PolicyViolationError("indexed research model returned partial K5")
        allowed = {option.id: i for i, option in enumerate(options)}
        return tuple(allowed[item.option_id] for item in result.selections)

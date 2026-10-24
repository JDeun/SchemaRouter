"""E0-only DecisionBackend adapter for authorized native field-index overflow.

Caller must use NativeSchemaPostingIndex.lookup(..., _research_ranker=...).
That lookup constructs/rechecks the scoped evidence. This adapter consumes
only its bounded, already-authorized candidate list and cannot grant access.
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
class ResearchAuthorizedIndexedDecisionRanker:
    """Injectable no-default research adapter; NEVER a product ranker."""

    backend: DecisionBackend
    max_model_input_bytes: int = MAX_MODEL_INPUT_BYTES
    omit_identical_field_descriptions: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.max_model_input_bytes) is not int
            or not 1 <= self.max_model_input_bytes <= MAX_MODEL_INPUT_BYTES
            or type(self.omit_identical_field_descriptions) is not bool
        ):
            raise ValueError("invalid indexed research decision options")

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
            or any(type(item) is not IndexedNativeFieldCandidate for item in candidates)
        ):
            raise PolicyViolationError("indexed ranker requires bounded source evidence")
        # Strictly only source-visible route IDs and required visible field names:
        # never advertise registry tool descriptors, hidden data, credentials,
        # fingerprint internals, task gold or execution/permission promises.
        descriptions = tuple(
            "required output=" + ",".join(item.required_output_fields)
            for item in candidates
        )
        suppress = (
            self.omit_identical_field_descriptions
            and len(set(descriptions)) == 1
        )
        options = [
            DecisionOption(
                id=f"route_{i:02d}",
                label=item.route_id,
                description="" if suppress else descriptions[i],
            )
            for i, item in enumerate(candidates)
        ]
        request = DecisionRequest(
            query=query,
            options=options,
            max_selections=STRICT_K,
            context={
                "type": "NATIVE_INDEXED_REQUIRED_FIELD_RESEARCH_E0",
                "executable_authority": False,
                "independent_quality_evidence": False,
                "calibrated_no_fit": False,
            },
        )
        if len(request.model_dump_json().encode("utf-8")) > self.max_model_input_bytes:
            raise PolicyViolationError("indexed ranker model input byte cap")
        try:
            selected = choose_sync(self.backend, request)
        except Exception:
            # External model/provider errors may embed authorization secrets.
            raise PolicyViolationError("indexed research decision failed") from None
        if selected.abstained:
            return ()
        if len(selected.selections) != STRICT_K:
            raise PolicyViolationError("indexed ranker returned partial fixed-K5")
        verified_ids = {option.id: i for i, option in enumerate(options)}
        return tuple(verified_ids[choice.option_id] for choice in selected.selections)

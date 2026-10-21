"""Research-only bounded DecisionBackend adapter for G5 typed graph overflow.

A G5 lookup must already have filtered every original native endpoint using
current principal authorization, hidden-field scoping and availability. This
adapter cannot access a registry, execute a tool, fill from task gold, or turn
model abstention into validated no-fit. It maps only authorized source-proven
typed path evidence into opaque decision IDs and checks the exact fixed K5.
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
from schemarouter.native_graph_index import (
    MAX_RESEARCH_RANKABLE_PATHS,
    STRICT_K,
    NativeIndexedGraphCandidate,
)

MAX_MODEL_INPUT_BYTES = 16_384


def _scoped_path_description(path: NativeIndexedGraphCandidate) -> str:
    bindings = ",".join(
        f"{param}<-{source_field}"
        for param, source_field in path.parameter_bindings
    )
    fields = ",".join(path.consumer_output_fields)
    return (
        f"source={path.producer_route_id}; "
        f"output={fields}; input={bindings}"
    )


@dataclass(frozen=True, slots=True)
class ResearchAuthorizedG5DecisionRanker:
    """E0 adapter passed explicitly as a G5 `_research_ranker` callback."""

    backend: DecisionBackend
    max_model_input_bytes: int = MAX_MODEL_INPUT_BYTES
    omit_identical_descriptions: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.omit_identical_descriptions) is not bool
            or type(self.max_model_input_bytes) is not int
            or not 1 <= self.max_model_input_bytes <= MAX_MODEL_INPUT_BYTES
        ):
            raise ValueError("invalid G5 research decision input byte limit")

    def __call__(
        self,
        query: str,
        paths: tuple[NativeIndexedGraphCandidate, ...],
        k: int,
    ) -> tuple[int, ...]:
        if (
            type(query) is not str
            or len(query.encode("utf-8")) > 512
            or type(k) is not int or k != STRICT_K
            or type(paths) is not tuple
            or not STRICT_K < len(paths) <= MAX_RESEARCH_RANKABLE_PATHS
            or any(type(item) is not NativeIndexedGraphCandidate for item in paths)
        ):
            raise PolicyViolationError("G5 ranker requires bounded scoped typed paths")
        # The callback intentionally cannot discover or authorize any routes:
        # labels and fields are those of the already scoped candidate proofs.
        descriptions = tuple(_scoped_path_description(path) for path in paths)
        # Research-only unsupervised source-feature ablation: if every
        # already-authorized option has EXACTLY the same visible description,
        # it cannot distinguish candidate routes. Drop that redundant text
        # while preserving source-owned unique route ID labels and all G5
        # permission/typed-binding/source checks. Never use task gold.
        omit = (
            self.omit_identical_descriptions
            and len(set(descriptions)) == 1
        )
        options = [
            DecisionOption(
                id=f"path_{i:02d}",
                label=path.consumer_route_id,
                description="" if omit else descriptions[i],
            )
            for i, path in enumerate(paths)
        ]
        request = DecisionRequest(
            query=query, options=options, max_selections=STRICT_K,
            context={
                "type": "G5_AUTHORIZED_TYPED_PATHS_RESEARCH_E0",
                "independent_quality_evidence": False,
                "executable_authority": False,
                "calibrated_no_fit": False,
            },
        )
        if len(request.model_dump_json().encode("utf-8")) > self.max_model_input_bytes:
            raise PolicyViolationError("G5 research ranker model input byte cap")
        # Host-owned choose_sync rejects unoffered, duplicate, over-K, malformed,
        # asynchronous, or model-forged selection envelopes.
        result = choose_sync(self.backend, request)
        if result.abstained:
            return ()
        if len(result.selections) != STRICT_K:
            raise PolicyViolationError(
                "G5 research model returned partial fixed-K5 ranking"
            )
        offered = {option.id: i for i, option in enumerate(options)}
        return tuple(offered[item.option_id] for item in result.selections)

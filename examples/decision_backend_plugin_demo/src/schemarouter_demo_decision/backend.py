from __future__ import annotations

from schemarouter import (
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
)


class DemoBoundedDecisionBackend:
    """Deterministic example that can only return IDs offered in the request."""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        query = " ".join(request.query.casefold().split())

        matches = []
        for option in request.options:
            labels = {
                option.id.casefold(),
                " ".join(option.label.casefold().split()),
            }
            labels.discard("")
            if any(label in query for label in labels):
                matches.append(option)

        if not matches:
            return DecisionResult(
                abstained=True,
                metadata={"reason": "no_exact_option_match"},
            )

        selected = matches[: request.max_selections]
        return DecisionResult(
            selections=[
                DecisionSelection(option_id=option.id, score=1.0)
                for option in selected
            ],
            metadata={"strategy": "exact_bounded_match"},
        )

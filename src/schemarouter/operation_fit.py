"""Optional declared-operation execution guard for post-planning no-match (#1291).

The host, *not* the embedding model, supplies both a structured requested
operation and a route-to-operation manifest for this authorized registry.
No text translation, classification, new authorization, or tool calls occur.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .errors import PolicyViolationError
from .models import ExecutionPlan, StrictModel

OperationKind = Literal[
    "search", "lookup", "list", "history", "convert", "directions",
    "create", "update", "delete",
]


class DeclaredOperationFitPolicy(StrictModel):
    """Host-authored exact operation contract, separate from semantic ranking.

    Each *executable* primary or fallback route needs a matching declared
    operation. A catalog description is not trusted to authorize an action.
    Missing route mappings fail closed. This cannot classify user intent.
    """

    requested_operation: OperationKind
    route_operations: dict[str, OperationKind] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_routes(self) -> DeclaredOperationFitPolicy:
        if any(
            not route.strip() or route != route.strip() or "." not in route
            for route in self.route_operations
        ):
            raise ValueError("operation route IDs must be nonempty dotted identities")
        return self


def validated_declared_operation_policy(
    policy: DeclaredOperationFitPolicy,
) -> DeclaredOperationFitPolicy:
    """Rebuild a detached snapshot, rejecting model_copy(update=...) forgery."""
    if not isinstance(policy, DeclaredOperationFitPolicy):
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid operation-fit policy"
        )
    try:
        return DeclaredOperationFitPolicy.model_validate(
            policy.model_dump(mode="python", warnings=False), strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid operation-fit policy"
        ) from exc


def validate_declared_operation_fit(
    plan: ExecutionPlan,
    *,
    policy: DeclaredOperationFitPolicy,
) -> None:
    """Deny an unrepresented or mismatched final call or fallback.

    Call only after existing registry/shortlist/schema authorization. The
    runtime's permission checks remain mandatory. A successful return
    establishes *manifest equality*, not actual task satisfaction.
    """
    verified = validated_declared_operation_policy(policy)

    def require(route_tool: str, route_endpoint: str) -> None:
        route_id = f"{route_tool}.{route_endpoint}"
        declared = verified.route_operations.get(route_id)
        if declared is None:
            raise PolicyViolationError(
                "selective retrieval execution denied: undeclared operation route"
            )
        if declared != verified.requested_operation:
            raise PolicyViolationError(
                "selective retrieval execution denied: operation mismatch"
            )

    for call in plan.calls:
        require(call.tool, call.endpoint)
    for fallback in plan.fallback_routes:
        for call in fallback.alternatives:
            require(call.tool, call.endpoint)

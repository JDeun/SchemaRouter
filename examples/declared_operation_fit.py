"""Post-planning exact operation gate example; no models or tools are invoked.

This does not classify intent. The trusted host must supply an operation tag
and an approved route-operation manifest from its own registry, not LLM output.
"""
from schemarouter import (
    DeclaredOperationFitPolicy,
    ExecutionPlan,
    ToolCall,
    validate_declared_operation_fit,
)


def main() -> None:
    # This example verifies the contract, not actual router authorization.
    plan = ExecutionPlan(
        query="재고 수량 조회",
        registry_version=1,
        calls=[ToolCall(tool="inventory", endpoint="lookup", schema_fingerprint="fixture")],
    )
    host_manifest = {"inventory.lookup": "lookup", "inventory.update": "update"}
    policy = DeclaredOperationFitPolicy(
        requested_operation="lookup",
        route_operations=host_manifest,
    )
    validate_declared_operation_fit(plan, policy=policy)
    print("Operation tag matches the planned route (authorization still required).")

    # An unsupported mutation is refused even when a lexical/embedding
    # ranker returned an inventory lookup candidate.
    from schemarouter import PolicyViolationError

    denied = policy.model_copy(update={"requested_operation": "delete"})
    try:
        validate_declared_operation_fit(plan, policy=denied)
    except PolicyViolationError:
        print("Delete request refused: the selected operation is only lookup.")
    else:
        raise AssertionError("a mismatched operation must never be accepted")


if __name__ == "__main__":
    main()

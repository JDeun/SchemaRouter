from __future__ import annotations

from benchmarks.agent_utility_v1_catalog import TASKS, build_registry
from benchmarks.agent_utility_v1_executor import DeterministicTaskExecutor


def test_search_retrieve_dependency_requires_returned_paper_id() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(
        registry,
        "multi-paper-search-retrieve",
    )

    first = executor.execute(
        "papers.search",
        {"query": "perovskite stability"},
    )
    assert first.advanced_task is True
    assert first.observation["paper_id"] == "P-SEARCH-1"
    assert executor.complete is False

    wrong = executor.execute(
        "papers.retrieve",
        {"paper_id": "P-OTHER"},
    )
    assert wrong.schema_valid is True
    assert wrong.semantic_valid is False
    assert wrong.advanced_task is False
    assert executor.complete is False

    correct = executor.execute(
        "papers.retrieve",
        {"paper_id": "P-SEARCH-1"},
    )
    assert correct.advanced_task is True
    assert executor.complete is True


def test_material_export_dependency_requires_artifact_output() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(
        registry,
        "multi-retrieve-export",
    )

    retrieved = executor.execute(
        "materials.retrieve",
        {"material_id": "MAT-7"},
    )
    assert retrieved.advanced_task is True
    assert retrieved.observation["artifact_id"] == "ART-MAT-7"

    exported = executor.execute(
        "exports.export",
        {"artifact_id": "ART-MAT-7"},
    )
    assert exported.advanced_task is True
    assert executor.complete is True


def test_credit_share_dependency_requires_numeric_amount_and_artifact() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "multi-create-share")

    wrong_type = executor.execute(
        "credits.create",
        {"amount": "100"},
    )
    assert wrong_type.schema_valid is False
    assert executor.complete is False

    created = executor.execute(
        "credits.create",
        {"amount": 100},
    )
    assert created.advanced_task is True
    assert created.observation["artifact_id"] == "ART-CREDIT-1"

    shared = executor.execute(
        "messaging.share",
        {
            "artifact_id": "ART-CREDIT-1",
            "recipient": "analyst@example.org",
        },
    )
    assert shared.advanced_task is True
    assert executor.complete is True


def test_wrong_destructive_call_is_blocked() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "single-paper-search")

    attempt = executor.execute(
        "inventory.delete",
        {"item_id": "INV-3"},
    )
    assert attempt.policy_blocked is True
    assert attempt.advanced_task is False
    assert executor.complete is False


def test_expected_destructive_call_can_execute() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "single-inventory-delete")

    attempt = executor.execute(
        "inventory.delete",
        {"item_id": "INV-3"},
    )
    assert attempt.policy_blocked is False
    assert attempt.advanced_task is True
    assert executor.complete is True


def test_extraneous_non_destructive_call_does_not_advance_task() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "single-export")

    attempt = executor.execute("inventory.list", {})
    assert attempt.error is None
    assert attempt.expected_at_step is False
    assert attempt.advanced_task is False
    assert executor.complete is False


def test_hidden_destructive_tool_attempt_is_countable() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "single-paper-search")

    attempt = executor.execute(
        "inventory.delete",
        {"item_id": "INV-3"},
        available=False,
    )
    assert attempt.route_id == "inventory.delete"
    assert attempt.policy_blocked is True
    assert attempt.error == "unavailable_tool"
    assert attempt.advanced_task is False


def test_multi_create_send_dependency_uses_frozen_task_id() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "multi-create-send")

    wrong = executor.execute(
        "inventory.create",
        {"item_name": "wrong-name"},
    )
    assert wrong.schema_valid is True
    assert wrong.semantic_valid is False
    assert wrong.advanced_task is False

    created = executor.execute(
        "inventory.create",
        {"item_name": "anode-binder"},
    )
    assert created.advanced_task is True
    assert created.observation["item_id"] == "INV-NEW-1"

    sent = executor.execute(
        "messaging.send",
        {
            "recipient": "analyst@example.org",
            "message": "Created anode-binder as INV-NEW-1",
        },
    )
    assert sent.advanced_task is True
    assert executor.complete is True


def test_user_supplied_arguments_are_explicit_in_frozen_queries() -> None:
    queries = {task.task_id: task.query for task in TASKS}

    assert "Experiment complete." in queries["single-message-send"]
    assert "analyst@example.org" in queries["single-message-send"]
    assert "100 credits" in queries["multi-create-share"]
    assert "analyst@example.org" in queries["multi-create-share"]


def test_single_message_send_requires_explicit_frozen_content() -> None:
    registry = build_registry(20)
    executor = DeterministicTaskExecutor(registry, "single-message-send")

    wrong = executor.execute(
        "messaging.send",
        {
            "recipient": "analyst@example.org",
            "message": "Something else",
        },
    )
    assert wrong.schema_valid is True
    assert wrong.semantic_valid is False
    assert wrong.advanced_task is False

    correct = executor.execute(
        "messaging.send",
        {
            "recipient": "analyst@example.org",
            "message": "Experiment complete.",
        },
    )
    assert correct.advanced_task is True
    assert executor.complete is True

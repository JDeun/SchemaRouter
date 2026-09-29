"""Deterministic local executor for the canonical frozen #420/#423 benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmarks.agent_utility_b2_catalog import TASKS, AgentUtilityTask
from schemarouter import EndpointSpec, InMemoryRegistry


@dataclass(frozen=True)
class ExecutionAttempt:
    route_id: str
    arguments: dict[str, Any]
    schema_valid: bool
    semantic_valid: bool
    policy_blocked: bool
    expected_at_step: bool
    advanced_task: bool
    error: str | None
    observation: dict[str, Any]


def _task_map() -> dict[str, AgentUtilityTask]:
    return {task.task_id: task for task in TASKS}


def _json_type_valid(value: Any, declared: str | None) -> bool:
    if declared is None:
        return True
    if declared == "string":
        return isinstance(value, str) and bool(value.strip())
    if declared == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "array":
        return isinstance(value, list)
    if declared == "object":
        return isinstance(value, dict)
    return True


def _endpoint_for(
    registry: InMemoryRegistry,
    route_id: str,
) -> EndpointSpec | None:
    if "." not in route_id:
        return None
    tool_key, endpoint_name = route_id.split(".", 1)
    try:
        tool = registry.get(tool_key)
    except KeyError:
        return None
    try:
        return tool.endpoint(endpoint_name)
    except KeyError:
        return None


def _schema_valid(
    endpoint: EndpointSpec,
    arguments: dict[str, Any],
) -> tuple[bool, str | None]:
    declared = {parameter.name: parameter for parameter in endpoint.parameters}
    extra = sorted(set(arguments).difference(declared))
    if extra:
        return False, "unexpected_arguments:" + ",".join(extra)

    for parameter in endpoint.parameters:
        if parameter.required and parameter.name not in arguments:
            return False, f"missing_required_argument:{parameter.name}"
        if parameter.name not in arguments:
            continue
        schema_type = parameter.json_schema.get("type")
        if isinstance(schema_type, list):
            allowed = [
                item for item in schema_type if isinstance(item, str)
            ]
            if not any(
                _json_type_valid(arguments[parameter.name], item)
                for item in allowed
            ):
                return False, f"invalid_type:{parameter.name}"
        elif isinstance(schema_type, str) and not _json_type_valid(
            arguments[parameter.name],
            schema_type,
        ):
            return False, f"invalid_type:{parameter.name}"

    return True, None


def _eq_string(arguments: dict[str, Any], key: str, value: str) -> bool:
    actual = arguments.get(key)
    return isinstance(actual, str) and actual.strip() == value


def _has_text(arguments: dict[str, Any], key: str) -> bool:
    value = arguments.get(key)
    return isinstance(value, str) and bool(value.strip())


class DeterministicTaskExecutor:
    """Execute mock tool calls without exposing hidden route labels to the agent."""

    def __init__(
        self,
        registry: InMemoryRegistry,
        task_id: str,
    ) -> None:
        tasks = _task_map()
        if task_id not in tasks:
            raise KeyError(task_id)
        self.registry = registry
        self.task = tasks[task_id]
        self.progress = 0
        self.attempts: list[ExecutionAttempt] = []
        self.state: dict[str, Any] = {}

    @property
    def complete(self) -> bool:
        return self.progress >= len(self.task.required_routes)

    @property
    def next_expected_route(self) -> str | None:
        if self.complete:
            return None
        return self.task.required_routes[self.progress]

    def _semantic_valid(
        self,
        route_id: str,
        arguments: dict[str, Any],
    ) -> bool:
        task_id = self.task.task_id

        exact_string_rules: dict[tuple[str, str], tuple[str, str]] = {
            ("single-paper-retrieve", "papers.retrieve"): ("paper_id", "P-104"),
            ("single-paper-summary", "papers.summarize"): ("paper_id", "P-104"),
            ("single-material-retrieve", "materials.retrieve"): (
                "material_id",
                "MAT-7",
            ),
            ("single-material-current", "materials.current"): (
                "material_id",
                "MAT-7",
            ),
            ("single-material-history", "materials.history"): (
                "material_id",
                "MAT-7",
            ),
            ("single-material-forecast", "materials.forecast"): (
                "material_id",
                "MAT-7",
            ),
            ("single-inventory-create", "inventory.create"): (
                "item_name",
                "cathode-powder",
            ),
            ("single-inventory-update", "inventory.update"): ("item_id", "INV-3"),
            ("single-inventory-delete", "inventory.delete"): ("item_id", "INV-3"),
            ("single-credit-refund", "credits.refund"): ("credit_id", "CR-8"),
            ("single-runtime-restart", "runtime.restart"): (
                "runtime_id",
                "RT-2",
            ),
            ("single-export", "exports.export"): ("artifact_id", "ART-2"),
            ("multi-paper-retrieve-summary", "papers.retrieve"): (
                "paper_id",
                "P-205",
            ),
            ("multi-paper-retrieve-summary", "papers.summarize"): (
                "paper_id",
                "P-205",
            ),
            ("multi-create-send", "inventory.create"): (
                "item_name",
                "anode-binder",
            ),
            ("multi-retrieve-export", "materials.retrieve"): (
                "material_id",
                "MAT-7",
            ),
        }

        rule = exact_string_rules.get((task_id, route_id))
        if rule is not None:
            return _eq_string(arguments, rule[0], rule[1])

        if route_id in {"papers.search", "materials.search"}:
            return _has_text(arguments, "query")

        if task_id == "single-message-send" and route_id == "messaging.send":
            return (
                _eq_string(arguments, "recipient", "analyst@example.org")
                and _eq_string(arguments, "message", "Experiment complete.")
            )

        if task_id == "single-share" and route_id == "messaging.share":
            return (
                _eq_string(arguments, "artifact_id", "ART-2")
                and _eq_string(
                    arguments,
                    "recipient",
                    "analyst@example.org",
                )
            )

        if task_id == "multi-paper-search-retrieve":
            if route_id == "papers.retrieve":
                return _eq_string(
                    arguments,
                    "paper_id",
                    str(self.state.get("selected_paper_id", "")),
                )

        if task_id == "multi-material-search-current":
            if route_id == "materials.current":
                return _eq_string(
                    arguments,
                    "material_id",
                    str(self.state.get("selected_material_id", "")),
                )

        if task_id == "multi-create-share":
            if route_id == "credits.create":
                amount = arguments.get("amount")
                return (
                    isinstance(amount, (int, float))
                    and not isinstance(amount, bool)
                    and float(amount) == 100.0
                )
            if route_id == "messaging.share":
                return (
                    _eq_string(
                        arguments,
                        "artifact_id",
                        str(self.state.get("created_artifact_id", "")),
                    )
                    and _eq_string(
                        arguments,
                        "recipient",
                        "analyst@example.org",
                    )
                )

        if task_id == "multi-create-send":
            if route_id == "messaging.send":
                message = arguments.get("message")
                return (
                    _eq_string(
                        arguments,
                        "recipient",
                        "analyst@example.org",
                    )
                    and isinstance(message, str)
                    and "INV-NEW-1" in message
                )

        if task_id == "multi-retrieve-export":
            if route_id == "exports.export":
                return _eq_string(
                    arguments,
                    "artifact_id",
                    str(self.state.get("material_artifact_id", "")),
                )

        return True

    def _observation(
        self,
        route_id: str,
        *,
        expected: bool,
    ) -> dict[str, Any]:
        if not expected:
            return {
                "status": "executed",
                "message": "Tool call completed but the user task is not complete.",
            }

        if route_id == "papers.search":
            self.state["selected_paper_id"] = "P-SEARCH-1"
            return {
                "status": "ok",
                "paper_id": "P-SEARCH-1",
                "title": "Selected paper",
            }
        if route_id == "papers.retrieve":
            if self.task.task_id == "multi-paper-search-retrieve":
                paper_id = str(self.state.get("selected_paper_id", ""))
            elif self.task.task_id == "multi-paper-retrieve-summary":
                paper_id = "P-205"
            else:
                paper_id = "P-104"
            return {
                "status": "ok",
                "paper_id": paper_id,
                "paper_text": "Deterministic paper content.",
            }
        if route_id == "papers.summarize":
            return {
                "status": "ok",
                "summary": "Deterministic paper summary.",
            }

        if route_id == "materials.search":
            self.state["selected_material_id"] = "MAT-SEARCH-1"
            return {
                "status": "ok",
                "material_id": "MAT-SEARCH-1",
                "formula": "LiNi0.8Mn0.1Co0.1O2",
            }
        if route_id == "materials.retrieve":
            artifact_id = (
                "ART-MAT-7"
                if self.task.task_id == "multi-retrieve-export"
                else "ART-MATERIAL"
            )
            self.state["material_artifact_id"] = artifact_id
            return {
                "status": "ok",
                "material_id": "MAT-7",
                "formula": "LiFePO4",
                "artifact_id": artifact_id,
            }
        if route_id == "materials.current":
            return {
                "status": "ok",
                "youngs_modulus": 125.0,
                "unit": "GPa",
            }
        if route_id == "materials.history":
            return {
                "status": "ok",
                "youngs_modulus": [121.0, 123.0, 125.0],
                "unit": "GPa",
            }
        if route_id == "materials.forecast":
            return {
                "status": "ok",
                "youngs_modulus": [126.0, 127.0],
                "unit": "GPa",
            }

        if route_id == "inventory.list":
            return {
                "status": "ok",
                "items": ["INV-1", "INV-2", "INV-3"],
            }
        if route_id == "inventory.create":
            self.state["created_item_id"] = "INV-NEW-1"
            return {
                "status": "ok",
                "item_id": "INV-NEW-1",
            }
        if route_id == "inventory.update":
            return {"status": "ok", "item_id": "INV-3"}
        if route_id == "inventory.delete":
            return {"status": "ok", "deleted_item_id": "INV-3"}

        if route_id == "messaging.send":
            return {"status": "ok", "message_id": "MSG-1"}
        if route_id == "messaging.share":
            return {"status": "ok", "share_id": "SHARE-1"}

        if route_id == "credits.create":
            self.state["created_artifact_id"] = "ART-CREDIT-1"
            return {
                "status": "ok",
                "credit_id": "CR-NEW-1",
                "artifact_id": "ART-CREDIT-1",
            }
        if route_id == "credits.cancel":
            return {"status": "ok", "cancelled": True}
        if route_id == "credits.refund":
            return {"status": "ok", "refunded": True}

        if route_id == "runtime.restart":
            return {"status": "ok", "runtime_id": "RT-2", "state": "running"}
        if route_id == "runtime.execute":
            return {"status": "ok", "execution_id": "EXEC-1"}

        if route_id == "exports.export":
            return {"status": "ok", "file_uri": "file:///tmp/artifact.json"}

        return {"status": "ok"}

    def execute(
        self,
        route_id: str,
        arguments: dict[str, Any],
        *,
        available: bool = True,
        execution_allowed: bool = True,
    ) -> ExecutionAttempt:
        endpoint = _endpoint_for(self.registry, route_id)
        if endpoint is None:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=False,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=False,
                advanced_task=False,
                error="unknown_tool",
                observation={
                    "status": "error",
                    "error": "unknown_tool",
                },
            )
            self.attempts.append(attempt)
            return attempt

        schema_valid, schema_error = _schema_valid(endpoint, arguments)
        expected = route_id == self.next_expected_route

        if not available:
            blocked = bool(endpoint.destructive)
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=schema_valid,
                semantic_valid=False,
                policy_blocked=blocked,
                expected_at_step=expected,
                advanced_task=False,
                error="unavailable_tool",
                observation={
                    "status": "blocked" if blocked else "error",
                    "error": "unavailable_tool",
                },
            )
            self.attempts.append(attempt)
            return attempt

        if bool(endpoint.destructive) and not expected:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=schema_valid,
                semantic_valid=False,
                policy_blocked=True,
                expected_at_step=False,
                advanced_task=False,
                error="destructive_policy_block",
                observation={
                    "status": "blocked",
                    "error": "destructive_policy_block",
                },
            )
            self.attempts.append(attempt)
            return attempt

        if not schema_valid:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=False,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=expected,
                advanced_task=False,
                error=schema_error,
                observation={
                    "status": "error",
                    "error": schema_error,
                },
            )
            self.attempts.append(attempt)
            return attempt

        if not execution_allowed:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=True,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=expected,
                advanced_task=False,
                error="parallel_tool_call_requires_observation",
                observation={
                    "status": "error",
                    "error": "parallel_tool_call_requires_observation",
                },
            )
            self.attempts.append(attempt)
            return attempt

        semantic_valid = self._semantic_valid(route_id, arguments)
        if expected and not semantic_valid:
            attempt = ExecutionAttempt(
                route_id=route_id,
                arguments=arguments,
                schema_valid=True,
                semantic_valid=False,
                policy_blocked=False,
                expected_at_step=True,
                advanced_task=False,
                error="invalid_task_arguments",
                observation={
                    "status": "error",
                    "error": "invalid_task_arguments",
                },
            )
            self.attempts.append(attempt)
            return attempt

        observation = self._observation(route_id, expected=expected)
        if expected:
            self.progress += 1

        attempt = ExecutionAttempt(
            route_id=route_id,
            arguments=arguments,
            schema_valid=True,
            semantic_valid=semantic_valid,
            policy_blocked=False,
            expected_at_step=expected,
            advanced_task=expected,
            error=None,
            observation=observation,
        )
        self.attempts.append(attempt)
        return attempt

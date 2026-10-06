from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jsonschema import exceptions, validators

from .errors import SchemaValidationError
from .models import EndpointSpec, _schema_at_projection_path


@dataclass(frozen=True, slots=True)
class RuntimeValidationBudget:
    """Hard limits for synchronous runtime JSON Schema validation work."""

    max_value_nodes: int = 50_000
    max_value_depth: int = 64
    max_container_items: int = 10_000
    max_string_chars: int = 1_000_000
    max_schema_nodes: int = 10_000
    max_schema_depth: int = 64
    max_combinator_product: int = 256
    max_regex_patterns: int = 64
    max_regex_pattern_chars: int = 256
    max_regex_input_chars: int = 4_096
    max_regex_variable_quantifiers: int = 2
    max_regex_repeat: int = 256
    max_unique_items: int = 512

    def __post_init__(self) -> None:
        limits = (
            self.max_value_nodes,
            self.max_value_depth,
            self.max_container_items,
            self.max_string_chars,
            self.max_schema_nodes,
            self.max_schema_depth,
            self.max_combinator_product,
            self.max_regex_patterns,
            self.max_regex_pattern_chars,
            self.max_regex_input_chars,
            self.max_regex_variable_quantifiers,
            self.max_regex_repeat,
            self.max_unique_items,
        )
        if any(limit <= 0 for limit in limits):
            raise ValueError("runtime validation limits must be positive")


_DEFAULT_RUNTIME_VALIDATION_BUDGET = RuntimeValidationBudget()


class _RuntimeValidationBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _RuntimeSchemaFeatures:
    has_pattern_properties: bool = False


def _budget_error(reason: str) -> _RuntimeValidationBudgetExceeded:
    return _RuntimeValidationBudgetExceeded(reason)


def _parse_brace_quantifier(pattern: str, start: int) -> tuple[int, bool, int | None] | None:
    end = pattern.find("}", start + 1)
    if end < 0:
        return None
    body = pattern[start + 1 : end]
    match = re.fullmatch(r"(\d+)(?:,(\d*)?)?", body)
    if match is None:
        return None
    lower = int(match.group(1))
    upper_text = match.group(2)
    if "," not in body:
        return end, False, lower
    if upper_text in (None, ""):
        return end, True, None
    upper = int(upper_text)
    return end, lower != upper, upper


def _validate_runtime_regex(pattern: str, budget: RuntimeValidationBudget) -> None:
    if len(pattern) > budget.max_regex_pattern_chars:
        raise _budget_error("regex pattern length limit exceeded")

    escaped = False
    in_class = False
    variable_quantifiers = 0
    group_stack: list[dict[str, bool]] = []
    last_group_ambiguous = False
    index = 0

    while index < len(pattern):
        char = pattern[index]

        if escaped:
            if char in "123456789":
                raise _budget_error("regex backreferences are not permitted")
            escaped = False
            last_group_ambiguous = False
            index += 1
            continue

        if char == "\\":
            escaped = True
            last_group_ambiguous = False
            index += 1
            continue

        if in_class:
            if char == "]":
                in_class = False
            index += 1
            continue

        if char == "[":
            in_class = True
            last_group_ambiguous = False
            index += 1
            continue

        if char == "(":
            if pattern.startswith("(?", index) and not pattern.startswith("(?:", index):
                raise _budget_error(
                    "regex lookarounds, inline flags, and named groups are not permitted"
                )
            group_stack.append({"variable": False, "alternation": False})
            last_group_ambiguous = False
            index += 3 if pattern.startswith("(?:", index) else 1
            continue

        if char == ")":
            if not group_stack:
                last_group_ambiguous = False
                index += 1
                continue
            closed = group_stack.pop()
            last_group_ambiguous = closed["variable"] or closed["alternation"]
            if group_stack:
                group_stack[-1]["variable"] |= closed["variable"]
                group_stack[-1]["alternation"] |= closed["alternation"]
            index += 1
            continue

        if char == "|":
            if group_stack:
                group_stack[-1]["alternation"] = True
            last_group_ambiguous = False
            index += 1
            continue

        is_variable = False
        upper_bound: int | None = None
        if char in "*+":
            is_variable = True
        elif char == "?":
            # A lazy suffix (for example +?) does not add another choice dimension.
            previous = pattern[index - 1] if index else ""
            is_variable = previous not in "*+}"
        elif char == "{":
            parsed = _parse_brace_quantifier(pattern, index)
            if parsed is not None:
                end, is_variable, upper_bound = parsed
                index = end

        if upper_bound is not None and upper_bound > budget.max_regex_repeat:
            raise _budget_error("regex bounded-repeat limit exceeded")

        if is_variable:
            if last_group_ambiguous:
                raise _budget_error("ambiguous quantified regex groups are not permitted")
            variable_quantifiers += 1
            if variable_quantifiers > budget.max_regex_variable_quantifiers:
                raise _budget_error("regex variable-quantifier limit exceeded")
            if group_stack:
                group_stack[-1]["variable"] = True

        if char not in "*+?{":
            last_group_ambiguous = False
        index += 1


def _inspect_runtime_schema(
    schema: dict[str, Any],
    budget: RuntimeValidationBudget,
) -> _RuntimeSchemaFeatures:
    stack: list[tuple[bool, Any, int, int]] = [(False, schema, 0, 1)]
    active_containers: set[int] = set()
    nodes = 0
    regex_patterns = 0
    has_pattern_properties = False

    while stack:
        leaving, current, depth, combinator_product = stack.pop()
        if leaving:
            active_containers.discard(id(current))
            continue

        nodes += 1
        if nodes > budget.max_schema_nodes:
            raise _budget_error("schema node limit exceeded")
        if depth > budget.max_schema_depth:
            raise _budget_error("schema depth limit exceeded")

        if isinstance(current, dict):
            identity = id(current)
            if identity in active_containers:
                raise _budget_error("cyclic schema containers are not permitted")
            active_containers.add(identity)
            stack.append((True, current, depth, combinator_product))

            pattern = current.get("pattern")
            if isinstance(pattern, str):
                regex_patterns += 1
                _validate_runtime_regex(pattern, budget)

            pattern_properties = current.get("patternProperties")
            if isinstance(pattern_properties, dict):
                has_pattern_properties = True
                for candidate in pattern_properties:
                    if isinstance(candidate, str):
                        regex_patterns += 1
                        _validate_runtime_regex(candidate, budget)

            if regex_patterns > budget.max_regex_patterns:
                raise _budget_error("regex pattern count limit exceeded")

            children: list[tuple[Any, int]] = []
            for key, child in current.items():
                child_product = combinator_product
                if key in {"anyOf", "oneOf", "allOf"} and isinstance(child, list):
                    child_product *= max(1, len(child))
                    if child_product > budget.max_combinator_product:
                        raise _budget_error("schema combinator work limit exceeded")
                children.append((child, child_product))
            for child, child_product in reversed(children):
                stack.append((False, child, depth + 1, child_product))
            continue

        if isinstance(current, list):
            identity = id(current)
            if identity in active_containers:
                raise _budget_error("cyclic schema containers are not permitted")
            active_containers.add(identity)
            stack.append((True, current, depth, combinator_product))
            for child in reversed(current):
                stack.append((False, child, depth + 1, combinator_product))

    return _RuntimeSchemaFeatures(
        has_pattern_properties=has_pattern_properties,
    )


def _inspect_runtime_value(
    value: Any,
    *,
    budget: RuntimeValidationBudget,
    features: _RuntimeSchemaFeatures,
) -> None:
    stack: list[tuple[bool, Any, int]] = [(False, value, 0)]
    active_containers: set[int] = set()
    nodes = 0

    while stack:
        leaving, current, depth = stack.pop()
        if leaving:
            active_containers.discard(id(current))
            continue

        nodes += 1
        if nodes > budget.max_value_nodes:
            raise _budget_error("value node limit exceeded")
        if depth > budget.max_value_depth:
            raise _budget_error("value depth limit exceeded")

        if isinstance(current, str):
            if len(current) > budget.max_string_chars:
                raise _budget_error("string length limit exceeded")
            continue

        if isinstance(current, dict):
            identity = id(current)
            if identity in active_containers:
                raise _budget_error("cyclic runtime values are not permitted")
            active_containers.add(identity)
            stack.append((True, current, depth))
            if len(current) > budget.max_container_items:
                raise _budget_error("object member limit exceeded")
            if features.has_pattern_properties:
                for key in current:
                    if isinstance(key, str) and len(key) > budget.max_regex_input_chars:
                        raise _budget_error("patternProperties key length limit exceeded")
            for child in reversed(tuple(current.values())):
                stack.append((False, child, depth + 1))
            continue

        if isinstance(current, list):
            identity = id(current)
            if identity in active_containers:
                raise _budget_error("cyclic runtime values are not permitted")
            active_containers.add(identity)
            stack.append((True, current, depth))
            if len(current) > budget.max_container_items:
                raise _budget_error("array item limit exceeded")
            for child in reversed(current):
                stack.append((False, child, depth + 1))


def _safe_schema_name(value: Any) -> str:
    text = str(value)
    return text if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", text) else "<field>"


def _safe_path(error: exceptions.ValidationError) -> str:
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(str(part))
            continue
        parts.append(_safe_schema_name(part))
    return ".".join(parts)


def _safe_validation_detail(error: exceptions.ValidationError) -> str:
    """Preserve stable schema diagnostics without echoing runtime/provider values."""

    if error.validator == "type":
        expected = error.validator_value
        if isinstance(expected, str) and re.fullmatch(r"[A-Za-z]+", expected):
            return f"value is not of type {expected!r}"
        if isinstance(expected, list):
            safe_types = [
                item
                for item in expected
                if isinstance(item, str) and re.fullmatch(r"[A-Za-z]+", item)
            ]
            if safe_types and len(safe_types) == len(expected):
                return "value is not of type " + ", ".join(repr(item) for item in safe_types)

    if error.validator == "required":
        required = error.validator_value
        instance = error.instance
        if isinstance(required, list) and isinstance(instance, dict):
            for name in required:
                if isinstance(name, str) and name not in instance:
                    return f"{_safe_schema_name(name)!r} is a required property"

    keyword = str(error.validator) if error.validator is not None else "validation"
    return f"value does not satisfy JSON Schema keyword {keyword!r}"


def _runtime_validator_class(
    validator_cls: Any,
    budget: RuntimeValidationBudget,
) -> Any:
    base_unique_items = validator_cls.VALIDATORS.get("uniqueItems")

    def bounded_pattern(validator, pattern, instance, schema):
        if not validator.is_type(instance, "string"):
            return
        if len(instance) > budget.max_regex_input_chars:
            raise _budget_error("regex input length limit exceeded")
        if not re.search(pattern, instance):
            yield exceptions.ValidationError(
                f"{instance!r} does not match {pattern!r}"
            )

    def bounded_pattern_properties(validator, patterns, instance, schema):
        if not validator.is_type(instance, "object"):
            return
        for key, value in instance.items():
            if not isinstance(key, str):
                continue
            if len(key) > budget.max_regex_input_chars:
                raise _budget_error("patternProperties key length limit exceeded")
            for pattern, subschema in patterns.items():
                if re.search(pattern, key):
                    yield from validator.descend(
                        value,
                        subschema,
                        path=key,
                        schema_path=pattern,
                    )

    def bounded_unique_items(validator, unique, instance, schema):
        if base_unique_items is None:
            return
        if (
            unique is True
            and validator.is_type(instance, "array")
            and len(instance) > budget.max_unique_items
        ):
            raise _budget_error("uniqueItems array limit exceeded")
        yield from base_unique_items(validator, unique, instance, schema)

    return validators.extend(
        validator_cls,
        {
            "pattern": bounded_pattern,
            "patternProperties": bounded_pattern_properties,
            "uniqueItems": bounded_unique_items,
        },
    )


def _synthesized_input_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    properties = {
        parameter.name: parameter.json_schema or {}
        for parameter in endpoint.parameters
    }
    required = [
        parameter.name
        for parameter in endpoint.parameters
        if parameter.required
    ]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _synthesized_output_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    properties = {
        field.name: field.json_schema or {}
        for field in endpoint.output_fields
    }
    required = [
        name
        for name in endpoint.metadata.get("output_required", [])
        if name in properties
    ]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def effective_input_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    return endpoint.input_schema or _synthesized_input_schema(endpoint)


def effective_output_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    if endpoint.output_schema:
        return endpoint.output_schema
    if endpoint.output_fields:
        return _synthesized_output_schema(endpoint)
    return {}


def field_value_schema(endpoint: EndpointSpec, field_name: str) -> dict[str, Any]:
    """Resolve the declared raw value schema for one output field conservatively."""

    field = next(
        (candidate for candidate in endpoint.output_fields if candidate.name == field_name),
        None,
    )
    if field is None:
        return {}
    if field.json_schema:
        return deepcopy(field.json_schema)

    schema = _schema_at_projection_path(
        effective_output_schema(endpoint),
        field.projection_path,
    )
    return deepcopy(schema)


def canonical_field_value_schema(
    endpoint: EndpointSpec,
    field_name: str,
) -> dict[str, Any]:
    """Return the projected result type shape after explicit unit normalization.

    Raw provider constraints remain validated before normalization. This helper only widens
    integer types to JSON number where affine conversion can produce non-integer values.
    """

    schema = field_value_schema(endpoint, field_name)
    field = next(
        (candidate for candidate in endpoint.output_fields if candidate.name == field_name),
        None,
    )
    if field is None or field.unit_normalization is None:
        return schema

    normalized = deepcopy(schema)

    def widen_integer(current: dict[str, Any]) -> None:
        declared = current.get("type")
        if declared == "integer":
            current["type"] = "number"
        elif isinstance(declared, list):
            current["type"] = list(
                dict.fromkeys(
                    "number" if value == "integer" else value
                    for value in declared
                )
            )
        items = current.get("items")
        if isinstance(items, dict):
            widen_integer(items)

    widen_integer(normalized)
    return normalized


def json_schema_types(schema: dict[str, Any]) -> frozenset[str]:
    declared = schema.get("type")
    if isinstance(declared, str):
        return frozenset({declared})
    if isinstance(declared, list):
        return frozenset(
            value
            for value in declared
            if isinstance(value, str)
        )
    return frozenset()


def json_types_compatible(
    required: frozenset[str],
    candidate: frozenset[str],
) -> bool:
    """Conservative value-type compatibility for fallback fields."""

    if not required:
        return True
    if not candidate:
        return False

    def accepted(candidate_type: str) -> bool:
        if candidate_type in required:
            return True
        # Every integer is a JSON number, but an arbitrary number is not necessarily an integer.
        return candidate_type == "integer" and "number" in required

    return all(accepted(candidate_type) for candidate_type in candidate)


def json_schemas_compatible(
    required: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    """Conservatively compare field value-shape compatibility."""

    required_types = json_schema_types(required)
    candidate_types = json_schema_types(candidate)
    if not json_types_compatible(required_types, candidate_types):
        return False
    if not required_types:
        return True

    if "array" in required_types:
        if "array" not in candidate_types:
            # A union can still be compatible through another shared type.
            shared_non_array = (required_types & candidate_types) - {"array"}
            numeric = {"number", "integer"}
            return bool(shared_non_array) or bool(
                required_types & numeric and candidate_types & numeric
            )
        required_items = required.get("items")
        candidate_items = candidate.get("items")
        if isinstance(required_items, dict):
            if not isinstance(candidate_items, dict):
                return False
            if not json_schemas_compatible(required_items, candidate_items):
                return False

    return True


def projected_output_schema(
    endpoint: EndpointSpec,
    selected_fields: list[str],
) -> dict[str, Any]:
    """Return a conservative schema for an explicitly server-projected response.

    Object paths and explicit wildcard array-item paths are narrowed recursively while preserving
    collection structure. Root collection endpoints keep their historical record-relative fields.
    """

    schema = deepcopy(effective_output_schema(endpoint))
    if endpoint.server_projection is None or not selected_fields or not schema:
        return schema

    field_map = {field.name: field for field in endpoint.output_fields}
    selected = [
        field_map[name]
        for name in selected_fields
        if name in field_map
    ]
    if not selected:
        return schema

    selection_tree: dict[str, Any] = {}
    for field in selected:
        current = selection_tree
        path = field.projection_path
        if not path:
            return schema
        for index, part in enumerate(path):
            if index == len(path) - 1:
                existing = current.get(part)
                if isinstance(existing, dict) and existing:
                    return schema
                current[part] = None
                continue

            existing = current.get(part)
            if existing is None and part in current:
                return schema
            if existing is None:
                child: dict[str, Any] = {}
                current[part] = child
                current = child
            elif isinstance(existing, dict):
                current = existing
            else:
                return schema

    def narrow_schema(
        current_schema: dict[str, Any],
        tree: dict[str, Any],
    ) -> dict[str, Any] | None:
        if "*" in tree:
            if set(tree) != {"*"}:
                return None
            if "array" not in json_schema_types(current_schema):
                return None
            items = current_schema.get("items")
            if not isinstance(items, dict):
                return None
            subtree = tree["*"]
            narrowed = deepcopy(current_schema)
            if subtree is None:
                return narrowed
            if not isinstance(subtree, dict) or not subtree:
                return None
            narrowed_items = narrow_schema(items, subtree)
            if narrowed_items is None:
                return None
            narrowed["items"] = narrowed_items
            return narrowed

        if "object" not in json_schema_types(current_schema):
            return None
        properties = current_schema.get("properties")
        if not isinstance(properties, dict):
            return None
        if any(name not in properties for name in tree):
            return None

        narrowed_properties: dict[str, Any] = {}
        for name, subtree in tree.items():
            property_schema = properties[name]
            if not isinstance(property_schema, dict):
                return None
            if subtree is None:
                narrowed_properties[name] = deepcopy(property_schema)
                continue
            if not isinstance(subtree, dict) or not subtree:
                return None
            narrowed_child = narrow_schema(property_schema, subtree)
            if narrowed_child is None:
                return None
            narrowed_properties[name] = narrowed_child

        narrowed = deepcopy(current_schema)
        narrowed["properties"] = narrowed_properties

        required = current_schema.get("required")
        if isinstance(required, list):
            narrowed_required = [
                name
                for name in required
                if name in tree
            ]
            if narrowed_required:
                narrowed["required"] = narrowed_required
            else:
                narrowed.pop("required", None)
        return narrowed

    narrowed = narrow_schema(schema, selection_tree)
    if narrowed is not None:
        return narrowed

    if "array" in json_schema_types(schema) and isinstance(schema.get("items"), dict):
        narrowed_items = narrow_schema(schema["items"], selection_tree)
        if narrowed_items is not None:
            schema["items"] = narrowed_items
            return schema

    return schema

def validate_json_schema_value(
    value: Any,
    schema: dict[str, Any],
    *,
    context: str,
    budget: RuntimeValidationBudget | None = None,
) -> None:
    if not schema:
        return

    effective_budget = budget or _DEFAULT_RUNTIME_VALIDATION_BUDGET

    try:
        features = _inspect_runtime_schema(schema, effective_budget)
        _inspect_runtime_value(
            value,
            budget=effective_budget,
            features=features,
        )
        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        runtime_validator_cls = _runtime_validator_class(validator_cls, effective_budget)
        validator = runtime_validator_cls(schema)
        first = next(validator.iter_errors(value), None)
    except _RuntimeValidationBudgetExceeded as exc:
        raise SchemaValidationError(
            f"{context}: JSON Schema validation work budget exceeded ({exc})"
        ) from exc
    except exceptions.SchemaError as exc:
        raise SchemaValidationError(
            f"{context}: declared JSON Schema is invalid"
        ) from exc
    except Exception as exc:  # unresolved refs and validator/runtime failures fail closed
        raise SchemaValidationError(
            f"{context}: JSON Schema could not be evaluated safely"
        ) from exc

    if first is None:
        return

    path = _safe_path(first)
    location = f" at {path}" if path else ""
    raise SchemaValidationError(
        f"{context}{location}: {_safe_validation_detail(first)}"
    )

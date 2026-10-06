from __future__ import annotations

import pytest
from jsonschema import exceptions

import schemarouter.validation as validation_module
from schemarouter.errors import SchemaValidationError
from schemarouter.validation import RuntimeValidationBudget, validate_json_schema_value


def test_runtime_validation_accepts_ordinary_patterns_and_values() -> None:
    validate_json_schema_value(
        "foo",
        {"type": "string", "pattern": r"^(?:foo|bar)$"},
        context="result",
    )
    validate_json_schema_value(
        "2026-10-06",
        {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        context="result",
    )


def test_runtime_validation_bounds_value_depth() -> None:
    value: object = "leaf"
    for _ in range(5):
        value = [value]

    with pytest.raises(SchemaValidationError, match="value depth limit exceeded"):
        validate_json_schema_value(
            value,
            {"type": "array"},
            context="result",
            budget=RuntimeValidationBudget(max_value_depth=3),
        )


def test_runtime_validation_bounds_total_value_nodes() -> None:
    with pytest.raises(SchemaValidationError, match="value node limit exceeded"):
        validate_json_schema_value(
            [1, 2, 3, 4],
            {"type": "array"},
            context="result",
            budget=RuntimeValidationBudget(max_value_nodes=4),
        )


def test_runtime_validation_rejects_cyclic_python_values() -> None:
    value: list[object] = []
    value.append(value)

    with pytest.raises(SchemaValidationError, match="cyclic runtime values"):
        validate_json_schema_value(
            value,
            {"type": "array"},
            context="arguments",
        )


def test_runtime_validation_allows_shared_acyclic_containers() -> None:
    shared = {"value": 1}
    validate_json_schema_value(
        {"left": shared, "right": shared},
        {"type": "object"},
        context="result",
    )


def test_runtime_validation_rejects_cyclic_schema_containers() -> None:
    schema: dict = {"type": "object"}
    schema["properties"] = {"self": schema}

    with pytest.raises(SchemaValidationError, match="cyclic schema containers"):
        validate_json_schema_value(
            {},
            schema,
            context="result",
        )


def test_runtime_validation_bounds_nested_combinator_work() -> None:
    schema = {
        "anyOf": [
            {"type": "string"},
            {
                "anyOf": [
                    {"type": "number"},
                    {"type": "integer"},
                ]
            },
        ]
    }

    with pytest.raises(SchemaValidationError, match="schema combinator work limit exceeded"):
        validate_json_schema_value(
            "value",
            schema,
            context="result",
            budget=RuntimeValidationBudget(max_combinator_product=3),
        )


def test_runtime_validation_rejects_ambiguous_quantified_regex_groups() -> None:
    with pytest.raises(
        SchemaValidationError,
        match="ambiguous quantified regex groups are not permitted",
    ):
        validate_json_schema_value(
            "a" * 128 + "!",
            {"type": "string", "pattern": r"^(a+)+$"},
            context="result",
        )


@pytest.mark.parametrize(
    "pattern",
    [
        r"^(a)\1$",
        r"^(?=a)a$",
        r"^a+b+c+$",
    ],
)
def test_runtime_validation_rejects_high_risk_regex_features(pattern: str) -> None:
    with pytest.raises(SchemaValidationError, match="validation work budget exceeded"):
        validate_json_schema_value(
            "abc",
            {"type": "string", "pattern": pattern},
            context="result",
        )


def test_runtime_validation_limits_pattern_input_only_when_pattern_applies() -> None:
    budget = RuntimeValidationBudget(max_regex_input_chars=8)

    with pytest.raises(SchemaValidationError, match="regex input length limit exceeded"):
        validate_json_schema_value(
            "a" * 9,
            {"type": "string", "pattern": r"^a+$"},
            context="result",
            budget=budget,
        )

    validate_json_schema_value(
        "a" * 9,
        {"type": "string"},
        context="result",
        budget=budget,
    )


def test_runtime_validation_limits_unique_items_only_on_unique_arrays() -> None:
    budget = RuntimeValidationBudget(max_unique_items=2)

    with pytest.raises(SchemaValidationError, match="uniqueItems array limit exceeded"):
        validate_json_schema_value(
            [1, 2, 3],
            {"type": "array", "uniqueItems": True},
            context="result",
            budget=budget,
        )

    validate_json_schema_value(
        [1, 2, 3],
        {"type": "array"},
        context="result",
        budget=budget,
    )


def test_runtime_validation_error_does_not_echo_sensitive_value() -> None:
    secret = "api-key-super-secret"

    with pytest.raises(SchemaValidationError) as captured:
        validate_json_schema_value(
            secret,
            {"type": "integer"},
            context="result",
        )

    message = str(captured.value)
    assert secret not in message
    assert "not of type 'integer'" in message


def test_runtime_validation_consumes_only_first_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FirstErrorOnlyValidator:
        def __init__(self, schema) -> None:
            del schema

        def iter_errors(self, value):
            del value
            yield exceptions.ValidationError(
                "do not expose this value",
                validator="type",
                validator_value="object",
                path=["payload"],
            )
            raise AssertionError("validation traversed beyond the first diagnostic")

    monkeypatch.setattr(
        validation_module,
        "_runtime_validator_class",
        lambda validator_cls, budget: FirstErrorOnlyValidator,
    )

    with pytest.raises(SchemaValidationError, match="not of type 'object'") as captured:
        validate_json_schema_value(
            {"payload": "secret"},
            {"type": "object"},
            context="result",
        )

    assert "do not expose this value" not in str(captured.value)


def test_runtime_validation_invalid_schema_failure_is_data_safe() -> None:
    with pytest.raises(
        SchemaValidationError,
        match=r"^result: declared JSON Schema is invalid$",
    ):
        validate_json_schema_value(
            "value",
            {"type": "string", "pattern": "["},
            context="result",
        )


def test_runtime_validation_budget_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        RuntimeValidationBudget(max_value_nodes=0)


def test_runtime_validation_bounds_schema_nodes_and_depth() -> None:
    with pytest.raises(SchemaValidationError, match="schema node limit exceeded"):
        validate_json_schema_value(
            "x",
            {"type": "string"},
            context="result",
            budget=RuntimeValidationBudget(max_schema_nodes=1),
        )

    with pytest.raises(SchemaValidationError, match="schema depth limit exceeded"):
        validate_json_schema_value(
            "x",
            {"allOf": [{"type": "string"}]},
            context="result",
            budget=RuntimeValidationBudget(max_schema_depth=1),
        )


def test_runtime_validation_bounds_container_and_string_sizes() -> None:
    with pytest.raises(SchemaValidationError, match="array item limit exceeded"):
        validate_json_schema_value(
            [1, 2, 3],
            {"type": "array"},
            context="result",
            budget=RuntimeValidationBudget(max_container_items=2),
        )

    with pytest.raises(SchemaValidationError, match="object member limit exceeded"):
        validate_json_schema_value(
            {"a": 1, "b": 2, "c": 3},
            {"type": "object"},
            context="result",
            budget=RuntimeValidationBudget(max_container_items=2),
        )

    with pytest.raises(SchemaValidationError, match="string length limit exceeded"):
        validate_json_schema_value(
            "abcd",
            {"type": "string"},
            context="result",
            budget=RuntimeValidationBudget(max_string_chars=3),
        )


def test_runtime_validation_bounds_regex_schema_complexity() -> None:
    with pytest.raises(SchemaValidationError, match="regex pattern length limit exceeded"):
        validate_json_schema_value(
            "a",
            {"type": "string", "pattern": "^a+$"},
            context="result",
            budget=RuntimeValidationBudget(max_regex_pattern_chars=3),
        )

    with pytest.raises(SchemaValidationError, match="regex bounded-repeat limit exceeded"):
        validate_json_schema_value(
            "aaaa",
            {"type": "string", "pattern": r"^a{4}$"},
            context="result",
            budget=RuntimeValidationBudget(max_regex_repeat=3),
        )

    with pytest.raises(SchemaValidationError, match="regex pattern count limit exceeded"):
        validate_json_schema_value(
            "a",
            {
                "allOf": [
                    {"type": "string", "pattern": "^a$"},
                    {"type": "string", "pattern": "^a$"},
                ]
            },
            context="result",
            budget=RuntimeValidationBudget(max_regex_patterns=1),
        )


def test_runtime_validation_allows_common_bounded_schema_patterns() -> None:
    for value, pattern in (
        ("alpha-123", r"^[A-Za-z0-9_-]{1,64}$"),
        ("2026-10-06", r"^\d{4}-\d{2}-\d{2}$"),
        ("foo", r"^(foo|bar)$"),
    ):
        validate_json_schema_value(
            value,
            {"type": "string", "pattern": pattern},
            context="result",
        )


def test_runtime_validation_bounds_pattern_properties_key_work() -> None:
    with pytest.raises(
        SchemaValidationError,
        match="patternProperties key length limit exceeded",
    ):
        validate_json_schema_value(
            {"long-key": 1},
            {
                "type": "object",
                "patternProperties": {
                    "^long-key$": {"type": "integer"},
                },
            },
            context="result",
            budget=RuntimeValidationBudget(max_regex_input_chars=4),
        )


def test_runtime_validation_sanitizes_unsafe_error_paths() -> None:
    sensitive_key = "customer secret field"
    with pytest.raises(SchemaValidationError) as captured:
        validate_json_schema_value(
            {sensitive_key: "not-an-integer"},
            {
                "type": "object",
                "properties": {
                    sensitive_key: {"type": "integer"},
                },
            },
            context="result",
        )

    message = str(captured.value)
    assert sensitive_key not in message
    assert "at <field>" in message
    assert "not of type 'integer'" in message


def test_runtime_validation_preserves_safe_array_error_path() -> None:
    with pytest.raises(SchemaValidationError) as captured:
        validate_json_schema_value(
            ["not-an-integer"],
            {"type": "array", "items": {"type": "integer"}},
            context="result",
        )

    assert "at 0" in str(captured.value)


def test_runtime_validation_unresolved_reference_fails_closed() -> None:
    with pytest.raises(
        SchemaValidationError,
        match=r"^result: JSON Schema could not be evaluated safely$",
    ):
        validate_json_schema_value(
            "value",
            {"$ref": "#/$defs/missing"},
            context="result",
        )

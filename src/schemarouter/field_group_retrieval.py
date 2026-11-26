"""Opt-in native typed FieldGroup retrieval over the authorized capability catalog.

A trusted host declares query aliases and complete required output semantics.
This is not natural-language semantic inference, an agent, or execution.
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache

from jsonschema import Draft202012Validator, SchemaError
from pydantic import model_validator

from .canonical_json import canonical_json_text
from .capability_contracts import (
    _SCHEMA_ANNOTATIONS,
    CapabilityFieldContract,
    compare_capability_fields,
)
from .models import EndpointSpec, FieldSpec, StrictModel
from .validation import (
    RuntimeValidationBudget,
    _has_declared_json_shape,
    _inspect_runtime_schema,
    _RuntimeValidationBudgetExceeded,
)

FIXED_FIELD_GROUP_K = 5


def _alias_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().casefold()


@lru_cache(maxsize=256)
def _validated_scalar_contract(encoded_schema: str) -> bool:
    """Cache syntax/work-budget checks by schema content, never source authority."""
    try:
        schema = json.loads(encoded_schema)
        _inspect_runtime_schema(schema, RuntimeValidationBudget())
        Draft202012Validator.check_schema(schema)
    except (SchemaError, _RuntimeValidationBudgetExceeded,
            TypeError, ValueError, OverflowError, RecursionError):
        return False
    return True


def _scalar_contract(schema: dict) -> bool:
    if (
        type(schema) is not dict
        or type(schema.get("type")) is not str
        or schema["type"] not in {"string", "integer", "number", "boolean"}
    ):
        return False
    if set(schema) == {"type"}:
        return True
    if "enum" in schema and not schema["enum"]:
        return False
    allowed = _SCHEMA_ANNOTATIONS | {"type", "enum", "const"}
    if schema["type"] in {"integer", "number"}:
        allowed |= {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}
    elif schema["type"] == "string":
        allowed |= {"minLength", "maxLength", "pattern"}
    if not schema.keys() <= allowed:
        return False
    try:
        encoded = canonical_json_text(schema)
        if len(encoded.encode("utf-8")) > 16_384:
            return False
    except (TypeError, ValueError, OverflowError, RecursionError):
        return False
    return _validated_scalar_contract(encoded)


@lru_cache(maxsize=256)
def _validated_response_contract(encoded_schema: str) -> bool:
    """Bounded JSON output contracts; references must be local and acyclic.

    This never grants an identifier/host-input contract. Keep the narrower
    scalar predicate for graph dependency producers and trusted host inputs.
    """
    return _has_declared_json_shape(json.loads(encoded_schema))


def _response_contract(schema: dict) -> bool:
    """A declared JSON response shape, not an empty/unknown schema."""
    if _scalar_contract(schema):
        return True
    if type(schema) is not dict or not (
        schema.keys() & {"type", "$ref", "anyOf", "oneOf", "allOf"}
    ):
        return False
    try:
        encoded = canonical_json_text(schema)
        return len(encoded.encode("utf-8")) <= 16_384 and _validated_response_contract(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return False


def _root_envelope_empty(endpoint: EndpointSpec) -> bool:
    """Proof of an input-free native endpoint, shared by FieldGroup and G5."""
    if endpoint.parameters or endpoint.auth_requirements:
        return False
    return not endpoint.input_schema or endpoint.input_schema in (
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": [],
         "additionalProperties": False},
    )


class NativeDeclaredFieldGroup(StrictModel):
    """Source-owner approved concept→conjunctive typed output requirements.

    These aliases are *not* discovered or translated by the router. The host
    decides the exact text forms and attests the trusted semantic contracts.
    """

    aliases: tuple[str, ...]
    required_fields: tuple[CapabilityFieldContract, ...]
    source_type: str | None = None
    license: str | None = None

    @model_validator(mode="after")
    def validate_bounded_group(self) -> NativeDeclaredFieldGroup:
        if (
            not 1 <= len(self.aliases) <= 16
            or any(
                type(value) is not str
                or not 1 <= len(value) <= 256
                or value != value.strip()
                or not _alias_key(value)
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
                for value in self.aliases
            )
            or len({_alias_key(value) for value in self.aliases}) != len(self.aliases)
            or not 1 <= len(self.required_fields) <= 8
            or len({field.semantic_id for field in self.required_fields})
            != len(self.required_fields)
            or any(
                not _response_contract(field.json_schema)
                or any(not key or not val for key, val in field.qualifiers.items())
                for field in self.required_fields
            )
            or any(
                value is not None
                and (
                    type(value) is not str
                    or not 1 <= len(value) <= 160
                    or value != value.strip()
                )
                for value in (self.source_type, self.license)
            )
        ):
            raise ValueError("invalid bounded native FieldGroup declaration")
        return self


def _compatible_field(required: CapabilityFieldContract, field: FieldSpec) -> bool:
    if (
        field.semantic_id is None
        or not _response_contract(field.json_schema)
    ):
        return False
    produced = CapabilityFieldContract.from_field(field)
    if produced is None:
        return False
    # No inferred conversions or equivalences. Missing required dimensions
    # remain UNKNOWN in the canonical typed comparator, never a positive hit.
    if required.unit is not None and produced.unit != required.unit:
        return False
    return compare_capability_fields(required, produced).status in {"exact", "compatible"}


def _complete_fields(
    fields: list[FieldSpec], required_fields: tuple[CapabilityFieldContract, ...],
) -> bool:
    return all(
        any(_compatible_field(required, field) for field in fields)
        for required in required_fields
    )

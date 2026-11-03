"""Schema-independent query needs; source-owned declarations alone resolve them."""
from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, model_validator

from .concept_retrieval import NativeConceptCatalog
from .models import StrictModel
from .paper_understood_direct_plan import PaperUnderstanding, _bounded_name
from .planner import _normalize


class PaperQueryNeed(StrictModel):
    """One untrusted raw information need, including every explicit constraint."""

    model_config = ConfigDict(strict=True)

    concept: str = Field(
        max_length=160,
        description="Short English name of one positive data concept, including its semantic role.",
    )
    unit: str | None = Field(
        default=None, max_length=160,
        description="Canonical unit symbol requested by the user; null when no unit was requested.",
    )
    source_type: str | None = Field(
        default=None, max_length=160,
        description="Explicit source-type constraint for this need; never permission.",
    )
    qualifiers: dict[str, str] = Field(
        default_factory=dict, max_length=8,
        description="All explicit role, path or temporal constraints as string keys and values.",
    )

    @model_validator(mode="before")
    @classmethod
    def canonical_conditions(cls, value: Any) -> Any:
        if type(value) is not dict or type(value.get("qualifiers", {})) is not dict:
            return value
        qualifiers = dict(value.get("qualifiers", {}))
        if len(qualifiers) > 8:
            raise ValueError("too many raw query qualifiers")
        normalized = dict(value)
        # Preserve equivalent model encodings without weakening any requested condition.
        for key in ("unit", "source_type"):
            if key not in qualifiers:
                continue
            requested = qualifiers.pop(key)
            if not _bounded_name(requested):
                raise ValueError("invalid reserved query condition")
            if normalized.get(key) is not None and normalized[key] != requested:
                raise ValueError("conflicting reserved query conditions")
            normalized[key] = requested
        normalized["qualifiers"] = qualifiers
        return normalized

    @model_validator(mode="after")
    def validate_need(self) -> PaperQueryNeed:
        if (
            not _bounded_name(self.concept)
            or self.unit is not None and not _bounded_name(self.unit)
            or self.source_type is not None and not _bounded_name(self.source_type)
            or any(not _bounded_name(key) or not _bounded_name(value)
                   for key, value in self.qualifiers.items())
        ):
            raise ValueError("invalid bounded raw query need")
        return self


class PaperQueryUnderstanding(StrictModel):
    """Untrusted Understand(q) output containing no source or concept authority."""

    model_config = ConfigDict(strict=True)

    intent_id: str | None = Field(
        description="One fixed task-intent vocabulary entry; null for unsupported or OOD intent.",
    )
    needs: tuple[PaperQueryNeed, ...] = Field(
        default=(), max_length=8,
        description="All positive raw needs, including unsupported ones; at most eight.",
    )
    needs_truncated: bool = Field(
        default=False,
        description="True if requested needs remain outside this list; never omit them silently.",
    )
    excluded_concepts: tuple[str, ...] = Field(
        default=(), max_length=8,
        description="Raw concepts explicitly negated by the user; never positive requirements.",
    )
    named_tools: tuple[str, ...] = Field(
        default=(), max_length=5,
        description="Only tool names explicitly stated by the user; never inferred route IDs.",
    )
    parameter_hints: dict[str, Any] = Field(
        default_factory=dict, max_length=8,
        description="Explicit argument values as bounded scalar hints; never host arguments.",
    )
    source_type: str | None = Field(
        default=None, max_length=160,
        description="Explicit source-type constraint for the entire query; never permission.",
    )

    @model_validator(mode="after")
    def validate_understanding(self) -> PaperQueryUnderstanding:
        # Reuse the existing scalar/value bounds and shared identity validation;
        # this does not resolve any hint into a source-owned concept or route.
        PaperUnderstanding(
            intent_id=self.intent_id, source_type=self.source_type,
            named_tools=self.named_tools, parameter_hints=self.parameter_hints,
        )
        if (
            len(set(self.excluded_concepts)) != len(self.excluded_concepts)
            or any(not _bounded_name(value) for value in self.excluded_concepts)
            or len(self.model_dump_json().encode("utf-8")) > 4096
        ):
            raise ValueError("invalid bounded raw query understanding")
        return self


def _resolve_query_need(
    need: PaperQueryNeed,
    catalog: NativeConceptCatalog,
    global_source_type: str | None = None,
) -> tuple[str | None, bool]:
    """Match a whole atom to one existing owner concept, never create authority.

    The boolean reports normalized alias/ID ambiguity. Query conditions may
    narrow an owner contract, but cannot disambiguate a colliding identity or
    combine conditions from different fields. Units have no inferred aliases.
    """
    approved_need = PaperQueryNeed.model_validate(need.model_dump(mode="python"), strict=True)
    approved_catalog = NativeConceptCatalog.model_validate(
        catalog.model_dump(mode="python"), strict=True,
    )
    normalized = _normalize(approved_need.concept)
    if not normalized:
        return None, False
    matches = [concept for concept in approved_catalog.concepts if any(
        _normalize(alias) == normalized for alias in (concept.concept_id, *concept.aliases)
    )]
    if len(matches) != 1:
        return None, len(matches) > 1
    concept = matches[0]
    if any(source is not None and source != concept.source_type
           for source in (global_source_type, approved_need.source_type)):
        return None, False
    if (approved_need.unit is not None or approved_need.qualifiers) and not any(
        (approved_need.unit is None or field.unit == approved_need.unit)
        and all(field.qualifiers.get(key) == value
                for key, value in approved_need.qualifiers.items())
        for field in concept.required_fields
    ):
        return None, False
    return concept.concept_id, False

"""Historical flat lexical request envelope, excluded from the installed wheel."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from schemarouter.models import EvidenceRequirements, FallbackScope, RetrievalMode, StrictModel


class PlanRequest(StrictModel):
    query: str
    concepts: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    arguments: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    field_evidence: dict[str, EvidenceRequirements] = Field(default_factory=dict)
    max_calls: int = Field(default=1, ge=1, le=32)
    retrieval_mode: RetrievalMode = "coverage"
    fallback_scope: FallbackScope = "disabled"
    max_fallbacks: int = Field(default=2, ge=0, le=8)

    @model_validator(mode="after")
    def validate_field_evidence(self) -> PlanRequest:
        normalized: dict[str, str] = {}
        for semantic_id, requirement in self.field_evidence.items():
            if not semantic_id.strip():
                raise ValueError("field_evidence semantic IDs must be non-empty")
            if semantic_id != semantic_id.strip():
                raise ValueError(
                    "field_evidence semantic IDs must not have surrounding whitespace"
                )
            key = "".join(
                char.lower()
                for char in semantic_id
                if char.isalnum()
            )
            if not key:
                raise ValueError(
                    "field_evidence semantic IDs must contain letters or numbers"
                )
            previous = normalized.get(key)
            if previous is not None and previous != semantic_id:
                raise ValueError(
                    "field_evidence contains ambiguous normalized semantic IDs: "
                    f"{previous!r}, {semantic_id!r}"
                )
            normalized[key] = semantic_id
            if (
                self.evidence.source_type is not None
                and requirement.source_type is not None
                and self.evidence.source_type != requirement.source_type
            ):
                raise ValueError(
                    "field_evidence source_type conflicts with global evidence "
                    f"for {semantic_id!r}"
                )
        return self

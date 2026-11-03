"""Optional concept constraints never replace current original-source proof."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemarouter import CapabilityFieldContract, NativeConceptCatalog, NativeDeclaredConcept
from schemarouter.concept_retrieval import _merged_concept_constraints, resolve_native_concepts


def _concept(name, *, source=None, license=None, aliases=None):
    return NativeDeclaredConcept(
        concept_id=f"case.{name}", aliases=aliases or (f"case {name}",),
        required_fields=(CapabilityFieldContract(
            semantic_id=f"case.{name}", json_schema={"type": "string"},
        ),), source_type=source, license=license,
    )


def test_neutral_concept_does_not_fabricate_source_or_license_constraints():
    concept = _concept("status")
    assert concept.source_type is None and concept.license is None
    assert _merged_concept_constraints((concept,)) == (None, None)
    result = resolve_native_concepts(
        "case status", catalog=NativeConceptCatalog(concepts=(concept,)),
    )
    assert result.field_group.source_type is None and result.field_group.license is None


def test_compatible_neutral_and_explicit_constraints_intersect_independently():
    concepts = (_concept("status"), _concept("priority", source="crm"),
                _concept("owner", license="reviewed"))
    assert _merged_concept_constraints(concepts) == ("crm", "reviewed")
    resolved = resolve_native_concepts(
        "case status case priority case owner", catalog=NativeConceptCatalog(concepts=concepts),
    )
    assert (resolved.field_group.source_type, resolved.field_group.license) == ("crm", "reviewed")


@pytest.mark.parametrize("constraints", (
    ({"source": "first"}, {"source": "second"}),
    ({"license": "first"}, {"license": "second"}),
))
def test_conflicting_nonnull_constraints_do_not_merge(constraints):
    concepts = tuple(_concept(name, **values) for name, values in zip(
        ("status", "priority"), constraints, strict=True,
    ))
    assert _merged_concept_constraints(concepts) is None
    with pytest.raises(ValueError, match="incompatible source policy"):
        resolve_native_concepts("case status case priority", catalog=NativeConceptCatalog(
            concepts=concepts,
        ))


def test_unspecified_and_explicit_source_are_not_disjoint_alias_authority():
    with pytest.raises(ValidationError, match="ambiguous owner-declared"):
        NativeConceptCatalog(concepts=(
            _concept("status", aliases=("shared name",)),
            _concept("priority", source="crm", aliases=("shared name",)),
        ))

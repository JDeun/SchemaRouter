# Declared concept E1: compose typed FieldGroup from query mentions

Issue [#1551](https://github.com/JDeun/SchemaRouter/issues/1551). Requires
[#1550](https://github.com/JDeun/SchemaRouter/pull/1550) native authorized
FieldGroup pre-K retrieval, builds on [#1548](https://github.com/JDeun/SchemaRouter/pull/1548)
trusted semantic graph adjacency, and supports original-paper
[#1530](https://github.com/JDeun/SchemaRouter/issues/1530).

## Exactly what is implemented

A **host-approved** `NativeConceptCatalog` records 1–32 concepts, each
with a canonical concept ID, at most 16 declared synonyms and a typed
`CapabilityFieldContract` group, and **required exact source/license**
requirements for every concept. These labels are locally host-reviewed
contract predicates, not legal licensing clearance. Bounded, source-owner-declared EN/KO/JA phrases are matched
inside a bounded user query using the native lexical engine's narrow Unicode
normalization and ASCII token boundaries. Different concept aliases in
one query are combined into a **conjunction** of at most eight distinct
fully typed requirements.

The resolver rejects duplicate aliases/IDs, overlapping mentions of
different declared concepts, unknown/no match, contradictory field
types/units/qualifiers, heterogeneous source/license requests, over-budget
and post-approval mutated concept declarations. A matched concept is a
candidate requirement only, **never** permission, actual parameter value,
provider fact, or source field existence.

`retrieve_authorized_concepts()` delegates directly to the native
`retrieve_authorized_field_group()`, which uses the original
`SchemaPlanner.retrieve_with_scoped_schema` and current principal-/field-
scoped schema projection. The planner prefilters each candidate for
**conjunctive required fields** before K5. No second ranker, graph executor,
automatic schema augmentation, cross-endpoint field union or default
`retrieve_authorized` change.

## Security, evidence, and limits

- EN/KO/JA fixed authored example sentences and Korean decomposed Unicode
  qualify deterministic mention matching, **not** open-vocabulary
  multilingual language understanding.
- English substring distractors, ambiguous aliases, mismatched semantic
  contracts, 120 partial providers, denied/hidden fields, no-fit unknown
  phrases and no-execution are covered by offline unit tests.
- A natural sentence containing a negated mention (e.g. "I do not want
  priority") **cannot be reliably interpreted by this E1**. The resolver
  makes no claim to understand negation, modality, scoping, entailment or
  unknown synonyms. Host declarations must be trusted and callers should
  use a separately reviewed intent interpreter for unrestricted queries.
- Compatible scalar `{"type":...}` schema only. JSON Schema patterns,
  enums, nested constraints, arbitrary unit conversion and unreviewed source
  assertions are not proven. Natural queries longer than 160 Unicode
  characters or 512 UTF-8 bytes abstain in this narrow E1.
- The synthetic tests are **not** independently authored retrieval
  results, model improvements, provider remote transfer, CPU latency
  benchmarks or end-task agent success. Before any default promotion compare
  on independent publisher-authored #1346, OOD/unsupported, EN/KO/JA #1339,
  and paired external-agent #1477 at the same fixed K5 and principal.
- Preserve frozen #432 negative study; v0.18 #1356 HARD HOLD.

## Usage
```python
from schemarouter import (
    CapabilityFieldContract,
    NativeDeclaredConcept,
    NativeConceptCatalog,
    retrieve_authorized_concepts,
)

catalog = NativeConceptCatalog(concepts=(
    NativeDeclaredConcept(
        concept_id="support.status",
        aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="support.status", json_schema={"type": "string"},
        ),),
        source_type="support", license="reviewed",
    ),
))
retrieval = retrieve_authorized_concepts(
    router,
    "Please show case status",
    principal=trusted_principal,
    catalog=catalog,
)
```

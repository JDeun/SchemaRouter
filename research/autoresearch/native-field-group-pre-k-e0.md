# Native FieldGroup pre-Top-K E0 (opt-in)

Issue [#1549](https://github.com/JDeun/SchemaRouter/issues/1549); original
paper parity [#1530](https://github.com/JDeun/SchemaRouter/issues/1530);
synthetic predecessor E1 [#1536](https://github.com/JDeun/SchemaRouter/pull/1536);
native graph G3 [#1548](https://github.com/JDeun/SchemaRouter/pull/1548).

## Precise product-facing scope

`NativeDeclaredFieldGroup` is a bounded, locally **trusted** mapping from
exact EN/KO/JA query aliases to 1–8 *complete typed* required output
`CapabilityFieldContract`s. This is query→declared-concept→FieldGroup
**qualification**, not free-form language understanding or semantic ID
learning.

`retrieve_authorized_field_group(router, query, principal=..., group=...)`
reuses the existing KeywordAnalyzer, `SchemaPlanner.retrieve_with_scoped_schema`
and the currently principal-scoped catalog. The added typed schema
predicate checks that a single endpoint provides **all** demanded visible
fields *before* Top-K selection. It refuses type/unit/qualifier mismatches,
unsupported JSON Schema constraints, missing semantic metadata, unknown
source/licenses (when exact host labels are required), denied/hidden
fields and non-read-only or destructive endpoints. It never unions two
partial endpoints into an invented complete provider. Original source
fingerprints and the authority/availability witness stay enforced.

Use:
```python
from schemarouter import (
    CapabilityFieldContract,
    NativeDeclaredFieldGroup,
    retrieve_authorized_field_group,
)

group = NativeDeclaredFieldGroup(
    aliases=("case status", "문의 상태", "問い合わせ状態"),
    required_fields=(CapabilityFieldContract(
        semantic_id="support.status",
        json_schema={"type": "string"},
    ),),
)
result = retrieve_authorized_field_group(
    router, "case status", principal=trusted_principal, group=group,
)
```

## What this does not establish

- Only explicit host-declared aliases and scalar `{"type": "..."}` schemas;
  E0 **does not translate or infer** unseen natural-language intents.
- Fixed K5 for comparable research gates. This is *not* default
  `SchemaRouter.retrieve_authorized`, a new ranking model, a graph DB,
  an agent executor or independent provider transfer evidence.
- Single-endpoint *complete* FieldGroups only. Native G3 separately
  handles narrow pinned one/two-edge chains. There is no automatic
  multi-provider field union or execution plan.
- Source/license values are metadata and exact host-requested matching
  hints, **not legal clearance**.
- No independent improvement can be claimed until publisher-authored
  #1346, multilingual #1339 and paired external agent #1477 evaluate
  true required-route recall, full required-field recall, over-K/no-fit,
  tokenizer cost, CPU p50/p95/p99 and task completion.
- Preserve original #432 negatives and v0.18 release #1356 HOLD.

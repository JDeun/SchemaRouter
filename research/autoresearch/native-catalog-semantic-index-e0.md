# Full registered-native-catalog semantic posting index E0

Issue [#1560](https://github.com/JDeun/SchemaRouter/issues/1560),
source graph [#1530](https://github.com/JDeun/SchemaRouter/issues/1530).
**Incomplete product milestone**, opt-in only.

## Source of truth and exact supported scope

Build `NativeSchemaPostingIndex` once for the CURRENT `ToolRegistry`
identity + version. It reads **all** registered native tool endpoints and
stores an immutable scalar semantic-ID→registered-route posting index,
exact route locators, full tool/endpoint fingerprints and deterministic
snapshot receipt. All registered routes are counted, including metadata-
only tools with zero semantic postings. It does not create another
ToolRegistry or copy unverified permission claims into searchable context.

At query time, an owner-approved `NativeDeclaredFieldGroup` or
`NativeConceptCatalog` maps exact known aliases into a **conjunction** of
typed requirements. The posting intersection is an *exact conservative
superset*: every surviving endpoint is independently reloaded from the
registered native schema and checked using the original typed
`_complete_fields` comparison, current policy principal, field data scope,
availability, source/license, original fingerprints and schema version
witness. The return type holds only source-pinned route IDs and relevant
field names, **no arguments and no execution authority**.

It does **not** scan every registered tool per lookup. It can still scan
the postings for common semantic IDs, and the index itself takes a full
source scan to build; p50/p95/p99 and >=5k route costs remain unmeasured.
The snapshot is rejected after registry mutation or replacement; the
caller must rebuild instead of reusing stale source annotations.
Availability/policy changes are observed live per query; policy content
is compared before/after lookup. The external host remains responsible
for approval, credentials, provider contact and execution.

Strict K=5. E0 returns all typed/principal-eligible routes if <=K,
an empty `no_proven_hit` status if none, or **no candidates** plus
`over_k_unranked` if >K. Sorting for reproducible output is not claimed
as a quality ranker; the product still needs independently evaluated
ranking to return useful top five among many full matches. No inferred
translation, unit conversion, hidden fields, or new source-specific
capability labels. Missing source/field metadata cannot qualify.

## Important remaining gaps

1. **Graph adjacency** and verified typed one/two-hop discovery is
   currently a separate bounded G3/G4 research layer. This E0 index only
   indexes complete single-endpoint **output field** semantics and therefore
   must NOT be described as full schema-graph retrieval or Algorithm 1.
   The next stage should combine this posting index with the existing
   `capability_graph.py` source→consumer typed graph, not duplicate it.
2. Current alias lists are human-approved, not learned multilingual
   concept detection, and ranking beyond K has no independent quality
   evidence. Index snapshot is an in-process structural hash rather than
   external cryptographic provenance.
3. Source owner review, license label and authorization rules must
   remain separately trusted. This E0 is not commercial production SLO,
   independent cohort #1346, paired external-agent #1477, frozen #432
   or v0.18 #1356 release qualification.

## Deterministic testing

Offline tests exercise EN/KO/JA declared concepts, >400 irrelevant
semantic distractors, policy-hidden required output, denied/unsafe
endpoints, wrong type/unit/source/label, registry source churn and
K-overflow. A separate **5,127 registered-route synthetic smoke test**
verifies complete-field lookup correctness at that catalog size, with
no measured latency, RSS, independent data distribution or adversarial
provider workload. Verify the default `retrieve_authorized()` output remains
unchanged and registered tools are never executed.

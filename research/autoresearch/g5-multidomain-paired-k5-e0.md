# Multi-domain native G5 vs lexical same K5 — preregistered E0

Recorded 2026-10-24 before NEW multi-domain inference/measurements.
Issue #1560, stacked above Draft #1742. The successful #1742 twelve-cell
result reused ONE synthetic CRM source fork across EN/KO/JA and 500/5000
catalog sizes: schema-aware lexical K5 also recovered all 3, but exposed
3264–3536 vs G5 2050 UTF-8 source-contract bytes. Those original results
are frozen, not repurposed as externally independent tasks.

## Changed factor: distinguish actual source/field domain

Keep existing native graph index, strict parser-free E0, read-only source,
current principal/policy/data scope, authorization and K5 exactly.
Reuse the same source-scoped **schema-aware** lexical scorer and make its
declared FieldGroup an explicit host argument, rather than hardcoding CRM.
Build one synthetic shared catalog with **three distinct registered
source-type domains**, each with a different root identifier contract,
two individually required output fields, an attested license, decoys,
different EN/KO/JA query aliases. Intended registered fields:
- CRM: original `crm.fork_customer_id`→`crm.fork_status` +
  `crm.fork_owner`, original native fixture.
- LAB: `lab.sample_id` integer→`lab.assay_state` +
  `lab.purity_band`, native lab producer/read and consumers.
- INVENTORY: `inventory.lot_id` string→`inventory.temperature_band`
  + `inventory.storage_zone`, native inventory producer/read
  and consumers.

For each of 500/5000 base-route sizes and normal/mixed original source
policy, use EN/KO/JA aliases in each of 3 domains, total 2 × 2 × 3 × 3
= **36 correlated developer-authored task/cell results**. The actual
route total will be base registered routes PLUS additional local-domain
native routes/decoys and must be reported explicitly; do not call it an
exact 500 or 5000 registered-route benchmark.

Host auth scope: both arms receive same host-declared FieldGroup
(source_type/license/semantic_id and required output type), same current
original visible source and strict K=5. No access to gold route IDs in
either selector. Lexical ranks exactly the scoped tool metadata, field
semantic aliases and input/output names but not graph adjacency/binding
edges. G5 uses `NativeSchemaGraphIndex.lookup_shared_root_forks`.
Independent source-oracle scanner enumerates current scoped original
read-only routes, verifies a root with exact one required identifier and
two consumer endpoints each having a required input of that same
semantic/type and exact required output field, and rejects wrong type,
cross-license/provider and unavailable routes. This scanner MUST NOT
call the G5 index or the lexical ranker.

Quality: ALL required original root+two consumers, zero unauthorized
routes, authentic scoped original field and type evidence, abstention
on source revocation. Report both-hit / G5-only / lexical-only / neither
for all 36 cells and per-domain. Cost comparison only if both complete.
Input cost: native source JSON contract UTF-8 bytes, NOT model tokens.
Measure per domain/ambiguity count and expose negative outcomes.
No user-task, tool execution, source-disjoint E2, release or generalized
LLM savings claim. Existing #1346 external E2 BLOCKED, #1477 genuine
agent task pending, #1356 v0.18 HARD HOLD.

## Postmeasurement

Append only after actual Linux CI and inspected complete JSON artifacts.

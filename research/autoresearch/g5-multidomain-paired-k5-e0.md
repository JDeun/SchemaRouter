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

## Postmeasurement — verified 36 correlated E0 cells

Frozen measured code head: `ed6743d7e248f9490589279dbc97a407ae34a211`.
[GitHub Actions #40032415271](https://github.com/JDeun/SchemaRouter/actions/runs/40032415271):
**4/4** native source experimental matrix jobs passed, with
results downloaded and inspected for ALL conditions. Additional
same-head existing scoped K5 benchmark and research sandbox green.
Retained artifacts: `12535227392` (512 normal),
`12535024038` (512 mixed),
`12535821470` (5012 normal), and the fourth 5012-mixed artifact
in the same GitHub run. Each file includes 9 rows and source-safe
per-cell measurement results.

Actual combined registered native routes are **512 and 5,012**,
NOT 500/5,000: the two added LAB/INVENTORY domains contributed
6 registered read-only endpoints apiece. Exactly 3 domain
tasks × 3 user-authored language aliases × 2 inventories ×
2 scope conditions yielded **36 correlated E0 cells**.
Source scanner AND G5 AND schema-aware lexical all agreed
on the original required 3-route producer/consumer fork
**36/36**; no one-sided misses or neither-complete cells.
Lexical and G5 both stayed <= K=5 and live source
revocation for each of the three domains failed closed.

| Domain / principal scope | G5 routes | Lexical routes | G5 scoped contract bytes | Lexical scoped contract bytes | G5 same-correct byte reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| CRM / normal | 3 | 5 | 2,050 | 3,264 | 37.19% |
| CRM / mixed | 3 | 5 | 2,050 | 3,536 | 42.02% |
| LAB / both | 3 | 4 | 2,015 | 2,750 | 26.73% |
| INVENTORY / both | 3 | 4 | 2,053 | 2,819 | 27.17% |

The 3-domain/3-language combined **paired-complete-only**
schema exposure (each scope × one catalog-size; 9 rows) was:
- normal: G5 **18,354 B**, lexical **26,499 B**
  (**30.74%** fewer total serialized bytes);
- mixed: G5 **18,354 B**, lexical **27,315 B**
  (**32.81%** fewer bytes).
The two inventory sizes yield identical per-domain qualified
menu sizes (by design of the source and decoy generator),
NOT independent repeated publication tasks.

All source scans are separate from indexed graph retrieval,
and cross-license/source-type/wrong-identifier decoys are
present. This is a genuinely additional type/domain axis
relative to #1742, but still *developer-designed synthetic
three-fork E0*, not external publisher/task-author-disjoint
E2 and not a statistically general claim. No source execution,
LLM query-token counting, model tool-call reliability, real
multistep final answer or quality-conditioned agent-token
gain was demonstrated. The matched lexical comparator
has explicit FieldGroup knowledge and is reasonable but is not
an externally calibrated BM25/dense/reranker SOTA baseline.

Research interpretation: for these THREE known fork structures
G5's true typed graph filter reduces unrelated schema
exposure without losing the complete declared dependency
under equal K5 and source scope. Paper-wide cost/accuracy
claim remains an open test on #1346 independent provider E2
and #1477 agent execution, with #1356 v0.18 HOLD intact.

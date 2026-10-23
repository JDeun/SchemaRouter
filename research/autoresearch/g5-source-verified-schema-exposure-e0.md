# G5 native indexed fork — paired original-source contract-byte E0

Preregistered: 2026-10-24 (before inspecting NEW cost results). Owner #1560;
stacked on #1740. Reuses *existing* `scripts/benchmark_native_fork_fieldgroup_e0.py`
source-native fork generator and exhaustive original-source three-route reference,
not a new graph algorithm, generated gold, LLM, execution engine or ranker.

## Frozen comparison and outcome

Two original catalog sizes: 500 and 5000 native endpoint routes, each under
normal and source-owner-adversarial mixed policy/hidden-field/unlicensed/
source-type/incorrect-identifier conditions. Queries from SAME owner-reviewed
FieldGroup alias in EN, KO, JA: 2 × 2 × 3 = 12 cells. Shared original read-only
source snapshot; PrincipalContext `reader`, strict K=5. G5 uses the currently
implemented `NativeSchemaPostingIndex` and `NativeSchemaGraphIndex.lookup_shared_root_forks`.
Independently check the exact two-leaf/one-root route tuple against existing
`exhaustive_source_fork_reference`, whose original-source authorization and
canonical field comparator do not use the indexed graph. Abort on mismatch,
unproven provenance, >K, revoked fields/policy and unranked/unsafe outcomes.

For each source snapshot measure:
1. G5's 3-route originally registered, *current principal-visible* model
   disclosure schema envelope as canonical compact JSON UTF-8 bytes.
2. Exhaustive *principal-allowed* FULL native read-only catalog disclosure bytes
   over all allowed present routes, projected by current scope. This is an
   **unbounded inventory upper bound, not a fair K5 model-quality baseline**.
3. Independently verified 3-route *oracle* exposure bytes as ideal size-only
   lower bound on this one synthetic fork. G5 should have the same route set,
   hence the same bytes; no wins over an oracle are possible.
4. Three-language exact native menu parity, source revocation fail-closed,
   bound field coverage, query latency, original route count and CPU/RSS.

Never measure model tokens or incorrectly compare a 3-route G5 K5 menu
to an unbounded FULL catalog as an apples-to-apples agent accuracy/cost gain.
Do not assume 500/5000 irrelevant routes make a better matched K5 lexical
baseline. The already completed 234-case strong schema-aware lexical-vs-
indexed default E0 (#1740) is a **separate** matched-K5 retrieval comparison;
**indexed default is not G5** and results cannot be merged as G5 evidence.

The synthetic fixture has precisely one complete source-owned fork. This is
not independently authored G5 relevance gold, diverse-provider field
semantics, live source execution or agent final-task evidence. No outbound
calls or model weights. External author-disjoint publisher E2 #1346 and
actual paired agent evaluation #1477 remain the publication gates.
Product graph index #1560 and release #1356 remain open/HARD HOLD.

## Postmeasurement

Add frozen SHA/run and all positive/negative measured bytes **only after**
the first valid GitHub Linux artifact has been inspected. No runtime
savings claimed at preregistration.

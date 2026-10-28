# Original Algorithm 1 source-reviewed deterministic Rank (B1 E0)

Date: 2026-10-28. Parent #1560; stack after #1796.

## Purpose and current gap

The original Algorithm 1 specifies `Rank(T_cand, C)` when the model has
not explicitly named tools: prefer stronger exact concept/field matches,
deprioritize web, use schema priority, then fewer fields. The existing
principal-safe native index proves typed output field completeness before
K5, but defaults to `over_k_unranked` above K; a separate untrusted research
ranker is capped at 32 candidates and is not wired to the public paper
session. The ordinary lexical `SchemaPlanner.retrieve()` ranker is a
different API and must not silently substitute for paper source proof.

## Alternatives and decision

1. Extend the injected research model ranker to 5,000 candidates: unsafe
   private schema disclosure, high context cost and no global calibrated
   comparability; rejected.
2. Add `domain`, `web`, `priority` directly to every native `ToolSpec`:
   unreviewed provider annotations could bias rank, and new serialization
   fields could rotate unrelated registered-tool fingerprints; rejected.
3. **Selected:** an explicit bounded owner-reviewed, source-snapshot-bound
   `PaperNativeRankPolicy` keyed by original registered route identities.
   Keep source `ToolSpec` fingerprints unchanged, derive exact/substring
   strength only from already visible matched output names and approved
   concept aliases, and select K5 from the **full authorized qualified**
   direct set with a deterministic local heap. This shares the existing
   canonical index, comparator, authorization and source reattestation.

## Contract and boundaries

- Owner policy carries the exact original `snapshot_id`, optional route
  `priority` (default zero), web-route classification (default not web)
  and domain tags (only used when the owner intent declares domains).
  Never consume free-form adapter `metadata` as rank authority. All keys
  must refer to existing indexed originals; declarations are bounded.
- Add optional `domains` to the existing owner `PaperIntentDeclaration`;
  empty means the exact historical intent contract. If nonempty, only
  approved route-domain intersections enter the pre-K eligible set.
- A policy is passed **explicitly**, never used as a new default. Named
  tool choices keep their source-scoped before-K override and do not
  receive speculative automatic Rank.
- Strong exact normalized visible field/approved alias match beats a
  weaker substring match; web last, higher owner priority next, then
  fewer **principal-visible** output fields, finally exact route ID for
  deterministic ties. The score is a declared structural heuristic,
  **not** independently established semantic relevance.
- The ranker runs in-process (no model/provider/tool calls), over the
  existing canonical fully-qualified original native candidates. It may
  evaluate 500/5,000 candidates without exposing an unbounded model menu;
  `heapq.nsmallest` retains only K5 winners. All source/principal/field/
  availability checks and the entire qualified-count reattestation remain.
- The resulting non-executable `PaperTypedToolPlan` must have an explicit
  `ranked_unverified=True` marker. `ready` still means only that host-owned
  input shape is complete, never provider invocation authority. Historical
  paths with no policy, `sr1:` review cursors, snapshot hashing and source
  fingerprints remain byte-compatible.
- Wire the optional policy through both prepared session
  `compile_understood` and model-assisted `acompile_query`, with rechecking
  after external model callbacks. The legacy unstructured `compile()` and
  default `retrieve()/plan()` remain unchanged while E2 is unqualified.

## Verification, limits and out-of-scope

- RED→GREEN cases: six qualified routes, exact-vs-substring score, web vs
  local, priority, visible-field count, exact tie; domain exclusion before
  K; named override; 5,000 candidates; denied/hidden/disabled/unsafe;
  mutated source, policy and rank owner declaration; callback no-I/O.
- Pair actual shortlisted source identities against an independent full
  authorized fixture oracle for 500/5,000 synthetic registered originals;
  report bytes and p50/p95 CPU without asserting speedup or E2 accuracy.
- Typed G5 1-/2-hop **dependency path** ranking beyond K remains an
  independent follow-up: a direct-route rank cannot be substituted for
  a full producer→consumer path comparator. Do not flatten DAGs.
- No new provider adapters, raw schema disclosure, external model, claims
  of licensed source accuracy, automatic execution, default promotion or
  v0.18 release. #1346/#1477 independent E2 and #1356 HOLD unchanged.

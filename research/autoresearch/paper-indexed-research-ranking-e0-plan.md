# Indexed native FieldGroup research ranking E0 — implementation and verification

Date: 2026-10-25. Issue #1560. Stacked on Draft PR #1748, which is itself stacked on #1746.

## Why this slice

The source-native inverted index and canonical typed field comparator already return
complete principal-visible FieldGroup candidates at more than 5,000 catalog routes.
When a principal has more than five **complete** eligible endpoints, the public
baseline deliberately returns `over_k_unranked`, never an arbitrary alphabetic five.
Original-paper Algorithm 1 requires a separate measured ranking policy before
Top-K5 can choose among those complete candidates.

## Research-only contract

- Keep the product default unchanged. Only an explicit `_research_ranker`
  callback can rank the direct indexed FieldGroup and native-concept path.
- Use the original source-registered, semantic-posting intersection followed
  by canonical typed field-completeness, original principal authorization,
  data-scope field visibility, current availability and pinned schema checks.
  No secret or unauthorized route is ever offered to the callback.
- Limit the research candidate menu to at most 32 already-qualified endpoints.
  If more than 32 qualify, return `over_k_unranked` without invoking the callback.
- The callback receives detached immutable-shaped candidates and must return
  **only exactly five distinct integer offsets** into the eligible snapshot,
  or an empty tuple to abstain. No caller-created endpoint, extra/partial output,
  bool index or duplicate is accepted. Callback errors are sanitized.
- Revalidate ALL prequalified candidates, policy, principal, group declarations,
  availability, registry and retrieval witness after the callback runs. Even
  an unselected revoked candidate invalidates the disclosed candidate count.
- Return original verified source evidence, not callback-mutated objects;
  distinguish `ranked_unverified` and `ranker_abstained_unverified` from
  `complete`, with `experimental_ranked=True`. Never grant execution.
- A separate ranker implementation, independently scored ground truth,
  recall@5, p50/p95/p99 CPU cost, and >32 scalability are **not completed**
  by adding the callback interface.

## Verification

The suite includes EN/KO/JA alias parity, before-K eligibility, default
abstention parity, strict five-choice contract, forged and duplicate offsets,
explicit ranker abstention, callback error redaction, private menu cap,
mid-ranking availability revocation, principal-swap denial and concept lookup
delegation. Execute `tests/test_native_semantic_index.py` plus the existing
native graph and authorization tests. CI is the authoritative source for
the exact remote commit. Do not call this result a trained or validated ranker.

## Release gates

Keep Draft PR, no default route promotion or release approval. Publisher-authored
source-independent case gold (#1346), paired external-agent E2 (#1477),
ranking quality, exact current-source permissions, and #1356 release HOLD remain
requirements.


## Follow-up: real DecisionBackend adapter and paired direct-index DEV harness

- `scripts/research_indexed_decision_backend_ranker_e0.py` reuses the existing
  `DecisionBackend`, `DecisionOption`, `DecisionRequest` and `choose_sync`
  option-ID verification. The callback accepts **only** 6–32 already scoped
  `IndexedNativeFieldCandidate` receipts. Backend-visible text consists of the
  original authorized native route ID, original projected required field names,
  and source-independent query. Tool/endpoint fingerprints, arguments,
  credentials, provider invokers, task gold and registry handles are **not**
  passed. Every serialized model request is capped at 16,384 UTF-8 bytes.
  Exactly five validated selections or full abstention are accepted; partial,
  duplicate, forged or model-mutated choices fail closed in the existing
  `choose_sync` and index proof.
- `scripts/research_indexed_direct_e5_paired_dev.py` reuses the **already
  published** 24-service G5 synthetic source and 9 tasks × EN/KO/JA
  translations plus three OOD prompts. It calls the **real direct
  `NativeSchemaPostingIndex.lookup`** on identical original registered
  sources with K5; it checks default overflow, invokes the adapter through
  the opt-in ranking arm, and computes scorer-only Recall@5, OOD nonempty
  count and measured in-process lookup p50/p95/p99.
- `--mode validate` uses a deterministic **no-model first-five** backend;
  it is merely an executable plumbing/regression control. The separate
  `--mode real-e5-cpu` explicitly loads the existing pinned
  `intfloat/multilingual-e5-small` CPU `EmbeddingDecisionBackend` through
  the project's existing actual-model loader. Only a successful invocation
  of that mode can label `real_model_routing_measured=True`; tests and
  ordinary CI NEVER download or run model weights.
- Even a measured actual-model DEV score is **not** independent validation:
  24 source routes and gold service names are public/reused, many
  consumer tools require inputs not bound in direct lookup, the query
  language conversions were not independently translated or frozen for
  external publication, and no live native provider/agent/answer is used.
  Thus full E2 #1477, independent intake #1346, calibration and release
  #1356 remain HOLD. E5 path comparison must use the same source inventory,
  per-language strata, permissions, K and explicit no-fit policy.

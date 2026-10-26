# Original-paper Algorithm 1 continuation — P2 source-typed ToolCall E0

**2026-10-24 · E0 source-authored diagnostic, not a shipped/default executor.**

### 2026-10-26 A8 new research-only Understood→ranked direct K5 bridge

- **Prior A7 documentation-only Draft HEAD** `f8b7ff5c156d18ca71da3ab71bb8d914cd4aa5b0`
  passed **29/29 PR workflows**, including
  [main CI #7181](https://github.com/JDeun/SchemaRouter/actions/runs/40264271416)
  Linux Python 3.12 **6436 passed, 3 skipped in 1033.42s** with
  **85.00% coverage**. It contains no A8 bridge implementation; the
  following new A8 code requires its own distinct CI qualification.
- `scripts/research_paper_ranked_direct_a8_e0.py` connects the already
  validated host-owner `PaperUnderstanding` concept/intent FieldGroup to
  the **existing native direct index's opt-in Top-K5 research ranker**.
  The original trusted alias proves field eligibility, whereas the actual
  captured natural-language query informs experimental ranking. Only
  originally captured principal-visible authorized routes reach that
  callback; catalog, policy, principal and hints are checked after it.
  Current `compile_paper_understood_direct_plan` remains unmodified,
  conservatively `over_k_unranked` at >K. The new response is
  **`ranked_unverified`** (not executable), never a fabricated
  `PaperTypedToolPlan` or independent source/quality proof.
- Twelve synthetic adversarial tests currently cover >K/denied source,
  actual query, named-before-K, >32 refusal, forged choices, unknown
  source/tool and owner/policy/view mutation. **This A8 slice is pending
  full local and exact-remote CI.** See
  [A8 design](paper-a8-ranked-direct-e0-design.md) and
  [A8 implementation plan](paper-a8-ranked-direct-e0-plan.md).
  **A8 checkbox remains unchecked** until an independently justified
  actual ranker and its EN/KO/JA/OOD quality study exist. #1346/#1477
  external E2 and #1356 release HOLD unchanged.

### 2026-10-26 A6/A7 continuation — byte-pinned intake + separated Understand costs (E0 only)

- **Qualified A6/A7 E0 code HEAD (Draft #1755):**
  `c4466c0878cec58a95d161681201b067a55579ac`, Git tree
  `0a46fb70368fd9ae9f10a47666a453efca85acb6`, byte-identical to the
  locally validated commit. **29/29 returned pull-request workflows passed**
  on this **exact code head**, including
  [main CI #7178](https://github.com/JDeun/SchemaRouter/actions/runs/40256503694)
  with Linux Python 3.12 **6423 passed, 3 skipped in 576.54s** and
  **85.00% coverage** versus 84% floor. Typecheck, Python 3.10/3.11/3.13/3.14,
  Windows, documentation and packages passed. Dedicated original paper and
  native-intake Python 3.12 workflows passed. The prior A5 code head had
  6403 passed; this is a newer separate result. CodeQL is **not claimed**
  because its workflow targets `main` PRs, not this stacked Draft target.
  Any subsequent documentation-only head requires its **own** CI verification.
- **A6 partial engineering only:** Existing `inspect_unscored_native_cohort`
  already checks EN/KO/JA × five source-native dispositions but accepts a
  **self-declared** inventory SHA without the original bytes. New opt-in
  `inspect_source_pinned_native_cohort` / `--native-inventory` compares the
  actual supplied inventory's bounded verbatim bytes with that digest before
  issuing the existing *non-scoring* preflight receipt; the old four-file CLI
  remains compatible. Malformed JSON errors are source-neutral and do not
  chain the private JSON decoder exception. Design and implementation:
  [A6 design](paper-a6-source-byte-intake-design.md),
  [A6 plan](paper-a6-source-byte-intake-plan.md),
  [general intake](independent-native-e2-intake-preflight.md).
- **A7 partial engineering only:** New opt-in
  `scripts/research_paper_measured_episode_e0.py` composes the **existing A5
  source-scoped episode and exact same agent executor**, meters host-observed
  `Understand` wall time and canonical JSON UTF-8 bytes for the scoped model
  request and **per-turn actually offered agent tool schemas**, and keeps
  existing agent model/token/time counters separate. Strict host-adapter
  `PaperProviderUsageResponse` enables distinct *provider-reported* input/output
  tokens; without provider usage they remain `None`, never an inferred zero.
  No extra model callback, route authority, raw query/route/answer or second
  agent executor is added. Only the measurement record and existing
  principal-scoped `public_trace` should be exported; never treat either as
  independently verified E2. Design and implementation:
  [A7 design](paper-a7-understand-metering-design.md),
  [A7 plan](paper-a7-understand-metering-plan.md).
- **A7 same-agent paired E0 continuation (qualified engineering code HEAD):**
  `scripts/research_paper_paired_agent_e0.py` composes original
  principal-scoped authorized ranked first K5 from one frozen source capture
  against the existing measured paper K5, each using the **same fixed5
  executor** with fresh agent instances and matching **host-declared**
  agent/model/seed configuration. It deep-freezes tasks across both runs,
  prohibits nonfinite evidence, rechecks role/policy/source and reports
  sanitized distinct baseline/paper tool-schema JSON bytes, agent tokens and
  paper model-callback usage. No gold is supplied to the callbacks. Baseline
  runs first, so warm-cache effects prevent scientific latency claims; host
  matching configuration does **not authenticate** an external model.
  The old agent presents selected K5 tool definitions alphabetically; only
  **membership** is native-ranked. New actual >K/denied-route and cross-branch
  owner/sampling/gold-redaction tests verified E0 behavior. Local 229 related
  tests, repository Ruff, changed-script Pyright 0 errors; an independent
  reviewer additionally ran 447 scoped tests and found no remaining
  Critical/Important defects. **Exact published Draft code HEAD**
  `6f35b57c8f0d2dd0618ccc43b392dd7cff82d7f4`, Git tree
  `b179d92d558b8fb60fcf0afa08373ec9d364233d` matches the local
  reviewed six-file implementation; **29/29 returned PR workflows passed**.
  [Main CI #7180](https://github.com/JDeun/SchemaRouter/actions/runs/40263102244)
  ran Linux Python 3.12 **6436 passed, 3 skipped in 637.13s** with
  **85.00% coverage**, and the repository CI typecheck, dedicated original
  paper, native ranker and experimental CPU workflows completed successfully.
  CodeQL is not claimed separately green for this stacked Draft target.
  Full A7 independent acceptance remains unchecked.
  [Paired E0 design](paper-a7-paired-agent-e0-design.md),
  [paired implementation plan](paper-a7-paired-agent-e0-plan.md).
- These paths use **synthetic DEV fixtures only**, with no provider-observed
  production usage or same-model paired independent gold evaluation. Both
  **A6 and A7 remain unchecked**, #1346/#1477 `BLOCKED_EXTERNAL`, #1356
  release/default promotion `HARD HOLD`. The new code requires its own
  separate publisher qualification, regardless of the green code-head CI.
  A fresh independent reviewer found no unresolved Critical/Important E0
  defects; source-snapshot validity and full model-quality measurement were
  expressly outside the reviewed E0 scope.

### 2026-10-26 A5 E0 completed — verified code head and bounded limits

**Qualified code head (Draft #1755):**
`24a8cb0448c399f10dbe1dc86c898cbb8d328799`, Git tree
`68731e2770a1eb143bf7901ec6afe60899d27117` (identical to the local
140-test checkpoint). GitHub Actions for this **exact code HEAD**:
**28/28 PR-triggered workflows successful**, including main CI run
[`40251600240`](https://github.com/JDeun/SchemaRouter/actions/runs/40251600240).
Linux Python 3.12 full suite: **6403 passed, 3 skipped in 783.41s; coverage
85.00% against 84% floor**. Main CI `typecheck`, Windows smoke and package
checks also succeeded. CodeQL was **not separately represented** in the 28
returned PR workflows and must not be claimed independently green without
its own check evidence. A subsequent documentation-only head must be tracked
on its own, not silently inherit code-head CI.

- At Draft #1755 head `051705c254ef753b8ca4aaca1816fc050c45dab0`, protected
  Python 3.12 CI run `40242927433` failed: **10 failed / 6386 passed /
  3 skipped** (84.83% coverage), while the CI typecheck, Ruff and the
  separately listed research workflows passed. All ten failures were in
  `tests/test_paper_understood_graph_plan.py`: the recent direct-plan
  `requires_arguments` short-circuit had bypassed source-proven 1-/2-hop
  dependency lookup, ambiguity/overflow and drift checks.
- The original **graph-only API contract** is restored: a named consumer with
  missing inputs still undergoes typed G5 path proof; an unproved path is
  `no_proven_hit`, not a source-executed or implicitly host-filled dependency.
  The separate A5 scoped-agent bridge can preserve a **single source-proven
  direct** `requires_arguments` receipt only if **every missing required
  parameter is source-declared without a dependency `semantic_id`**.
  The same restriction applies when the model omits `named_tools` entirely;
  a read-only review caught that bypass, verified RED, and the bridge now
  returns generic no-proof abstention for it. Any missing typed identifier
  stays unoffered, and the graph DAG is never
  flattened into an agent tool menu. Model `parameter_hints` remain untrusted.
- Actual principal-scoped source + deterministic existing-agent integration
  now covers direct execution, named unknown/empty menus, missing ordinary
  input, missing typed dependency, **actual 1- and 2-hop path receipts with
  zero agent generations/tool calls**, policy drift in `Understand`, and
  authorization mutation during an agent turn. These remain **synthetic
  development** fixtures, not independent publisher E2.
- First local Python 3.12 checkpoint: **136/136** combined paper/direct/graph/G5/A5
  regression tests passed; `ruff check .` passed. Local full Pyright with
  incomplete optional environment reported **85 errors / 8 warnings**,
  mainly import resolution; the previous remote exact-head typecheck passed.
- During follow-up review, an **unnamed typed-input bypass** required a
  second RED→GREEN regression; the additional test and code fix were
  published and qualified in the exact code HEAD above.
  The same review found that counting 33 registry-only named endpoints before
  principal/data-scope filtering returned `budget_unsatisfied` for a denied
  tool, distinguishable from an unknown tool's `no_proven_hit`. A RED→GREEN
  regression now requires generic no-proof for both denied and field-hidden
  many-endpoint names. The graph prefilter first applies source/license,
  principal, data-scope, read-only and availability narrowing **before** its
  bounded 32-route cap; the canonical G5 graph still proves actual paths.
- **A5 checked as an E0 engineering implementation**, not independent E2.
  The next substantive work is A6 independently reviewed EN/KO/JA
  source-native gold (external provenance requirement), then A7
  pre-`Understand` model tokens/time and paired actual-agent measurement;
  A8–A10 and B1 remain open. Never reinterpret E0 as E2.
- Specific design and completion checklist:
  [A5 design](paper-scoped-agent-a5-e0-design.md),
  [A5 plan](paper-scoped-agent-a5-e0-plan.md).


### E0 scoped refusal measurement continuation (2026-10-25)

- Added `scripts/research_paper_refusal_eval_e0.py` and `tests/test_research_paper_refusal_eval_e0.py` on Draft #1755. This opt-in **measurement** maps actual `PaperTypedToolPlan.status` to offer / abstain / request_arguments / request_observation; unknown statuses fail closed.
- Independently source-verified supported and unsupported gold are separate denominators; unresolved cases do not become unsupported. Report EN/KO/JA and aggregate false-refusal, false-accept and deferred counts. An offered plan is not successful execution; a deferred plan is neither success nor an immediate refusal.
- No independent labeled dataset, real-model accuracy, model token/cost, automatic agent execution, calibrated global no-fit, or E2 is claimed. Next: add source-pinned independently reviewed EN/KO/JA gold fixtures, run paired real-model evaluation with current principal snapshots, then check same-head CI and extend research evidence. Keep #1291, #1346, #1477 and #1356 gates intact.

## LIVE IMPLEMENTATION CHECKLIST — single source of truth (2026-10-26)

**Use this list at the start of EVERY new session.** Keep completed items checked (do not delete audit history); update the evidence link, exact HEAD and CI state after each change. A checked implementation is **not** an E2 qualification. Do not reopen already completed slices. Prioritize major vertical behavior over micro-tuning.

**Current Draft:** [#1755](https://github.com/JDeun/SchemaRouter/pull/1755)
stacked on #1754. Latest **qualified implementation code head**:
`6f35b57c8f0d2dd0618ccc43b392dd7cff82d7f4`, 29/29 PR workflows
successful, Linux Python 3.12 **6436 passed / 3 skipped**, 85.00% coverage;
the preceding A6/A7 code head `c4466c08` separately qualified at 6423
passed, and the older A5-only head `24a8cb04` at 6403 passed.
Exact-head CI must be rechecked after any later commit, including a
docs-only handoff revision; do not inherit green from an earlier head.

**The 2026-10-25 A5 paragraphs below are historical checkpoints. The checked
2026-10-26 A5 item and qualified-head evidence supersede them.**


**A5 partial implementation checkpoint (2026-10-25):** `scripts/research_paper_scoped_plan_e0.py` now chains the single host-scoped async model callback into the current direct/one-/two-hop source-proven planner. It returns a bounded non-executing receipt and mapped evaluation decision; rejects an unscoped view and any executable-authority result. **A5 remains unchecked**: the existing fixed-K agent callback/episode has not yet consumed this async result, and full mutation/real-agent regressions are not yet proven. This is not an independent accuracy or E2 claim. New HEAD CI and targeted tests require confirmation.

**A5 continuation (2026-10-25):** `scripts/research_paper_fixed5_menu_e0.py::paper_plan_fixed5_menu` now projects only authorized direct-plan route receipts into the existing fixed-K model disclosure interface. It refuses to flatten 1/2-hop DAGs, refuses model-derived execution authority, verifies visible route fingerprints and source witness, and reuses the existing model-definition byte cap. **A5 stays unchecked:** this is not an integrated existing-agent episode and lacks full adversarial integration coverage. Verify new HEAD CI before claiming green.

**A5 episode continuation (2026-10-25):** `scripts/research_paper_fixed5_episode_e0.py::run_paper_fixed5_episode_e0` wires a preverified paper plan to the **existing** `run_generated_episode` using `EVAL-FIXED5-OPTIN`, the captured principal-scoped tool surface, repeated route-proof checks, and the host-owned empty-menu terminal. No second executor and no dependency DAG flattening. **A5 stays unchecked** until integration tests with actual scoped fixtures, model callback and observed agent turns are green; new commit CI must be checked. The current episode wrapper does not include separate `Understand(q)` token/time accounting, so A7 is also open.

**A5 test expansion (2026-10-25):** added branch-level `tests/test_research_paper_fixed5_menu_security_e0.py` covering valid direct disclosure, all abstentions, dependency no-flattening, hidden/forged/duplicate routes, untrusted execution authority, bad bindings, and registry revision mismatch. These are isolated monkeypatched contract regressions, **not** a complete real-agent end-to-end proof. Exact-head CI must run before checking A5. Prior head `0e06287f`: 24 success / 4 in progress on first-page PR workflows at check time.

**A5 bounded vertical slice update (2026-10-25):** Commits `38e18cfb` and `4791c9e7` add `scripts/research_paper_scoped_agent_episode_e0.py::run_paper_scoped_agent_episode_e0` and six boundary tests in `tests/test_research_paper_scoped_agent_episode_e0.py`. This opt-in async entrypoint sequences source-scoped Understand/plan into the existing fixed5 episode and rechecks source integrity before/after. Tested via mocked model/episode boundaries only: **not** yet a real principal-scoped end-to-end fixture or observed agent execution. Latest HEAD `4791c9e75d943110abb7219b5f61aa8e6709446d`: CI 23/28 success, five running at last check; do not claim green. **A5 remains unchecked.** Next: build real policy-backed fixture with source-visible direct/missing-argument/unsupported/dependency cases, run actual existing generated episode with fake deterministic agent, verify zero tool calls on empty/graph menus, then record same-head CI and only mark A5 if all acceptance cases pass. A7/E2 remain open.

### A. Source-safe Algorithm 1 implementation
- [x] **A1** Host-approved structured `Understand(q)` model callback with scoped source index and strict JSON parsing. Evidence: `scripts/research_paper_scoped_understand_e0.py`. E0 only.
- [x] **A2** Named direct-tool FieldGroup, principal/source guards, K5 prefilter and typed non-executing plan. Evidence: `paper_understood_direct_plan.py`, #1755.
- [x] **A3** Named one-/two-hop G5 typed dependency plan, conservative ambiguity/overflow, no auto-execution. Evidence: `paper_understood_graph_plan.py`, #1755.
- [x] **A4** E0 EN/KO/JA outcome accounting and verified-gold denominator guard. Evidence: `scripts/research_paper_refusal_eval_e0.py`, `tests/test_research_paper_refusal_eval_e0.py`; commit `4b4afe26`. This is evaluator mechanics **only**, not model accuracy.
- [x] **A5 — E0 COMPLETE** Integrated scoped model `Understand(q)` → current direct/graph planner → existing fixed-K agent evaluation adapter as an opt-in **bounded vertical slice**. Reuses existing executor, host authorization and pinned source; does not automatically execute dependency DAGs. Verified supported, unsupported, ordinary/typed missing arguments, 1/2-hop observation deferral, mutable policy/source and empty menu; 140 local targeted tests and full protected Python 3.12 6403 passed at head `24a8cb04`. **Not E2 or model accuracy.**
- [ ] **A6** Add independently reviewed, source-snapshot-pinned EN/KO/JA supported/unsupported/ambiguous fixtures, with explicit labels, provenance, license and permission conditions. Do not fabricate publisher gold.
- [ ] **A7** Run paired same-model/same-agent evaluation; report false refusal, false accept, deferred/unknown, tool attempts, wall time and actual input/output tokens separately from schema bytes; repeat on CI Linux Python 3.12. No E2 claim without independent data.
- [ ] **A8** Independently justified Top-K5 ranking for eligible alternatives and >K overflow, without weakening policy-before-K, deterministic tie handling or rewriting frozen #432 scores.
- [ ] **A9** Source-attested argument semantics and separately authorized observed 1/2-hop dependency execution through the **existing** agent/executor, with fail-closed mutation, typed binding, provenance and budget tests. Do not create a second executor.
- [ ] **A10** Calibrate no-fit on independently labeled supported and unsupported requests. A `no_proven_hit` is not proof of globally nonexistent capability. Related #1291 is closed for its prior specific fix; new calibration remains open in this plan.

### B. Product and independent qualification (not solved by E0)
- [ ] **B1** #1560 full versioned native catalog-wide index, incremental churn/role/availability invalidation and 500/5000 heterogeneous routes with source-authorized exhaustive oracle parity, p50/p95/p99 CPU/RSS/schema bytes.
- [ ] **B2 — BLOCKED_EXTERNAL** #1346 publisher-authored independent route/field/permission gold and provenance/license validation.
- [ ] **B3 — BLOCKED_EXTERNAL** #1477 paired independent end-to-end agent E2, actual data-context tokens, answer/task quality, latency and cost.
- [ ] **B4 — HARD HOLD** #1356 release/default promotion until all independent gates and protected checks are satisfied. Do not merge/release as part of E0 continuation.

### C. Per-session closeout (repeat every session)
- [ ] **C1** Confirm exact remote HEAD, CI/CodeQL and open Draft PR state **for the latest commit**. A pending workflow is not success.
- [ ] **C2** Run targeted tests + Ruff; record counts and limitations; full-suite timeout is not green.
- [ ] **C3** Update this checklist and next actionable item, source/commit evidence, issue #1560 and Draft #1755 description when material work changes. Mark checkboxes only when their stated acceptance is proven.
- [ ] **C4** Preserve cross-session safety boundaries: source ownership, permissions, no untrusted parameters, no new agent/executor, no E2 or release promotion.

## ACTIVE CROSS-SESSION RESUME — 2026-10-25 (supersedes older next-step notes below)

**Canonical continuation:** Original-paper Algorithm 1 is now beyond the P2
typed plan and observed-execution slice described in this historical handoff.
Do **not** restart at P1/P2 or open another parallel agent/executor. The active
stack is **Draft #1754** (native indexed direct FieldGroup → existing fixed-K
agent) followed by **Draft #1755** (structured paper `Understand` hints →
intent-required field union → exact named-tool direct receipts → host-owned
empty-menu terminal), on top of the earlier paper work (#1745–#1753).

| Current surface | Exact resume evidence | Limit |
| --- | --- | --- |
| Source-bound typed direct plan | `src/schemarouter/paper_understood_direct_plan.py`; [Draft #1755](https://github.com/JDeun/SchemaRouter/pull/1755) | Untrusted structured hints are already parsed externally; not a validated LLM parser |
| Original named tool before K | `NativeSchemaPostingIndex.lookup(..., allowed_tool_keys=...)` | Unknown/denied/hidden/unlicensed tools produce `no_proven_hit`; owner schema and principal permissions are still mandatory |
| Existing agent E0 adapter | `scripts/research_authorized_concept_fixed5_agent_bridge.py::AuthorizedPaperUnderstoodDirectFixed5Selector` | The original captured principal-visible lexical menu may still exclude an otherwise index-eligible route |
| Host-owned no-offered-tool refusal | `run_generated_episode(..., experimental_host_empty_menu_terminal=True)` | Exactly zero model generations and tool attempts on **empty verified menu**, with `REQUEST_MORE_TOOLS` generic benchmark terminal; default off; not global no-fit |
| Real model callback → structured paper hint (later E0 slice) | `scripts/research_paper_scoped_understand_e0.py::analyze_paper_understanding_scoped` | Explicitly host-approved intent/concept disclosure and source-scoped `catalog_index()` only; no calibrated language understanding; model hints remain untrusted |
| Named `Understand(q)` → source-typed 1/2-hop path (latest E0 slice) | `src/schemarouter/paper_understood_graph_plan.py::compile_paper_understood_graph_plan`; [design](paper-named-graph-understand-e0-design.md), [plan](paper-named-graph-understand-e0-plan.md) | Reuses original G5 joins; non-executing `PaperPlanBinding`, no original agent auto-execution or independent E2 |
| Outcome taxonomy | `ready`, `requires_arguments`, `requires_observation`, `ambiguous_paths`, `no_proven_hit`, `over_k_unranked`, `budget_unsatisfied` | Missing tool proof, unranked path ambiguity, K overflow, missing input and semantic absence remain different outcomes |

**Previous direct-selector checkpoint (historical):** local branch
`feat/1560-paper-understood-direct-e0-20261025`, local Git commit
`e917341` and Git tree `d53b2cb80c516470bcd693520cfbdd77820fbd87`.
Published [Draft #1755](https://github.com/JDeun/SchemaRouter/pull/1755)
head `669c4577c45af5e6ac8cb251da72bfb0c54c2cde` has **the exact same
Git tree**, despite different local/remote commit metadata. Keep it **Draft**;
do not merge into the stacked parent or release. Source-proven predecessor
[Draft #1754](https://github.com/JDeun/SchemaRouter/pull/1754) already passed
its protected workflow suite before #1755's continuation.

**Tests and protected workflows (latest observed 2026-10-25):** seven related
paper/agent/posting suites **210 passed**, repository-wide Ruff passed,
changed research selector Pyright 0 errors. The **entire** local `pytest`
command still times out at ~12% (85-second cap, exit 124); full local
Pyright reported 85 environment-wide errors/8 warnings with optional
imports unresolved, so neither entire local suite is claimed green.
For the exact remote head `669c4577`, **21/22 GitHub Actions workflows
were successful and the remaining Python 3.12 full-suite CI run was still
in progress** when recorded; no final all-green assertion until a new read.
Remote Actions/CodeQL and exact SHA remain the authority after changes.

**Mandatory immediate next steps, in order:**

1. Check #1755's **exact remote HEAD and remaining protected CI**, fixing any
   failure by test-first changes; do not infer success from ancestor PRs.
2. Read [direct source design](paper-understood-direct-e0-design.md),
   [direct implementation plan](paper-understood-direct-e0-plan.md),
   [new host refusal design](paper-host-empty-menu-refusal-e0-design.md), and
   [host refusal implementation checkpoint](paper-host-empty-menu-refusal-e0-plan.md),
   plus [model response source-scope design](paper-scoped-model-understand-e0-design.md)
   [model response implementation plan](paper-scoped-model-understand-e0-plan.md),
   [named graph design](paper-named-graph-understand-e0-design.md) and
   [named graph plan](paper-named-graph-understand-e0-plan.md).
   These internal, English-only research notes stay out of reviewed bilingual
   `docs/**/*.md` and **must be cited here** on each continuation.
3. Prioritize **major remaining Algorithm 1 behaviors**, not minute selector
   tuning: E0 now accepts a bounded **actual model callback**, and named
   tools can obtain **1/2-hop non-executing typed receipts**. It still lacks
   independently measured EN/KO/JA understanding accuracy and its extra
   model-time/token cost in a same-agent comparison. Continue with an
   independently justified ranking decision when >K; explicit host-attested
   parameter semantics, observed source values and separately guarded
   existing-agent dependency selection (no automatic execution authority).
   Preserve both supported **false refusal** and unsupported **false accept**
   measurements. For missing-tool refusals distinguish a currently unproved
   *authorized* capability from a globally nonexistent tool. #1291 owns
   prospective calibrated no-fit and #1477 owns paired independent agent E2.
4. Continue updating **this canonical handoff**, issue #1560, stacked Draft
   PR description and exact results after material changes. Independent
   publisher-authored #1346 and paired #1477 remain `BLOCKED_EXTERNAL`, while
   [release #1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains
   **HARD HOLD**. No frozen #432 benchmark rewriting or default promotion.

The sections below record P2 history and remain useful as implementation
evidence; their older PR heads and next-step instructions are **not** the
current resumption point.

### Post-checkpoint continuation — model-named 1/2-hop typed G5 plans (2026-10-25, latest)

The original bounded model `Understand(q)` adapter is followed by a new
**opt-in** `compile_paper_understood_graph_plan`. Explicit exact named tool
keys narrow the canonical G5 **target routes before K5** for both one-hop
and two-hop lookups; they never authorize a source or replace the typed graph.
For a single fully proved path it produces ordinary `PaperPlanCall` receipts
plus real `PaperPlanBinding` producer-output→consumer-input metadata, with
status `requires_observation`, no tool execution and no model-derived
arguments. Multiple complete dependency paths remain `ambiguous_paths` rather
than an unsafe merged call DAG; >K stays `over_k_unranked` with no receipts.
G5's owner-typed source proof is preserved, with additional all-dependency
reviewed-license and explicit source-type constraints. Unrecognized/denied/
hidden/unhealthy/unsafe or wrong-type dependencies never receive a graph plan.

The existing *direct* plan and fixed5 direct selector have not been changed to
execute dependencies or to silently trust model hints. With an explicit named
target requiring inputs, the **graph** API returns `no_proven_hit` if no
complete typed dependency is proved; the **direct** API can separately
report `requires_arguments` where legitimate host scalars may still exist.
Neither means the capability is globally absent. No same-agent empirical
quality improvement, automatic one-/two-hop source execution, calibrated
unsupported classifier or independent publisher E2 is established.

New source/test local commits: `172ee12` (G5 pre-K target filter) and
`fc4bb7d` (graph ToolCall compiler and source constraint self-review fix).
Published Draft #1755 **code checkpoint**:
`ac9115dd5442e9f253b8ffb8ac40037b7781b972`, with remote Git tree
`80222a36617730a14bcacbf2d04dfb082742de35` matching the locally
verified code snapshot byte-for-byte. This checkpoint is not a merge or a
release; the newest docs-only branch head can be newer and is tracked in
the Draft PR itself.
Local focused paper/G5/scoped-model/agent regression: **260 passed**;
repository-wide Ruff: **pass**; targeted new graph-module Pyright:
**0 errors, 0 warnings**. Pyright checking the older direct file together
still encounters a local unresolved `pydantic` import, so no complete Pyright
claim. The bounded **75-second full local pytest run timed out at about 12%**
(exit 124), as in earlier checkpoints. Protected GitHub CI must be read from
the *new exact branch head* after publishing; do not infer green status from
the prior model-callback head. Canonical linked work and verification:
[new design](paper-named-graph-understand-e0-design.md),
[new implementation plan](paper-named-graph-understand-e0-plan.md),
[stacked Draft #1755](https://github.com/JDeun/SchemaRouter/pull/1755),
[issue #1560](https://github.com/JDeun/SchemaRouter/issues/1560).

### Post-checkpoint continuation — scoped model `Understand(q)` (2026-10-25)

The prior `PaperUnderstanding` API was externally pre-constructed. New
`analyze_paper_understanding_scoped` takes one **real supplied model callable**
(synchronous or asynchronous), sends only the current principal-authorized
`AuthorizedAgentToolSurface.catalog_index()` and an explicitly reviewed
intent/concept disclosure allowlist, then strictly decodes bounded model JSON.
Zero authorized routes mean **no model call** and a `None` diagnostic. The
model's hallucinated named tools still face the original direct selector,
which cannot offer denied/hidden/wrong-license source routes. It detects
post-callback policy/source/principal/catalog/intent drift, malformed or
duplicate-key/oversized/nonfinite output and undeclared IDs, without adopting
any model-provided parameter value as trusted host input.

This is one E0 **input adapter**, NOT a trained model improvement, full natural
language intent accuracy, inference latency accounting, independent no-fit or
real provider execution. The existing `ModelQueryAnalyzer` remains unchanged;
its unscoped whole-registry prompt is not reused for this privacy-sensitive
paper research route. Local implementation commit `dd75cfb`; see the new
research design/plan above for current reproducibility and publication status.
New scoped pre-model bridge tests and the original paper/native/agent
regression combined **226 passed**, full repository Ruff passed and targeted
Pyright 0 errors. The full local pytest run again **timed out after 75 seconds
at ~12% (exit 124)**, so the remote exact-head CI remains authoritative.
The external model callback has no in-function deadline or cancellation:
production hosts must bound it separately. This **E0-only** pre-call's
CPU/token cost is not included in existing agent evaluator metrics.

## Source of truth, predecessors and gates

- The research objective is the original [SchemaRouter paper §4 Algorithm 1](https://github.com/JDeun/paper_SchemaRouter/blob/main/paper/schemarouter.tex): query understanding, original graph/field selection, explicit `(tool, params, fields, meta)` plan. Source-grounded parity map: [Draft #1745](https://github.com/JDeun/SchemaRouter/pull/1745).
- P1 source-visible required field **AND** before K5: [Draft #1746](https://github.com/JDeun/SchemaRouter/pull/1746), [canonical P1 handoff](paper-field-union-implementation-e0.md), issue [#1535](https://github.com/JDeun/SchemaRouter/issues/1535). Exact GitHub commit `472122bd2d97ed073baaeb7dd576e97c64f6e04b` has **13 successful Actions workflows**, including full CI, CodeQL, and Original Paper Required Field Coverage E0.
- This P2 implementation is scoped to issue [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), now published in [Draft PR #1748](https://github.com/JDeun/SchemaRouter/pull/1748) on **stacked branch** `feat/1560-paper-toolcall-plan-e0-20261024` based on P1 commit `472122bd2...`. The PR's live **head SHA** is authoritative; do not infer it from the local Git SHA because connector-authored commits have different metadata but verified-identical trees.
- The independently source-authored E2 [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) is **BLOCKED_EXTERNAL**; live reader/agent E2 [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) is not completed. v0.18 release [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains **HOLD**.

## Implemented bounded P2: `compile_paper_typed_tool_plan`

Entry point: `src/schemarouter/paper_typed_tool_plan.py` (also explicit public exports in `src/schemarouter/__init__.py`). Tests: `tests/test_paper_typed_tool_plan.py`, plus real OpenAPI-producer → host-attested MCP-consumers assertions in `tests/test_native_graph_shared_root_forks.py`, and host-parameterized producer → consumer validation in `tests/test_native_graph_host_root.py`. Focused workflow: `.github/workflows/original-paper-toolcall-plan-e0.yml`.

**New P2 executor-observation slice (Draft #1748 continuation):** `src/schemarouter/paper_observed_binding.py::observe_and_bind_paper_plan` is a separate **explicit async** API. Only after an exact complete P1/P2 source proof and fully supplied host-root inputs, it invokes **one read-only producer** once via the existing `SchemaRouter.execute(ExecutionPlan, RunConfig(max_tool_calls=1,max_attempts=1,max_remote_attempts=1))`. It uses the executor-produced `ToolResult`, not an arbitrary caller-supplied observation. For each P1 child, it obtains a fresh, *same original root + consumer + exact binding* G5 proof over the source-owner's relevant required FieldGroup, then reuses G5's internal scalar/field-contract checks to validate actual projected ID type, field presence, source schema and consumer input schema. It re-compiles P2 after the producer and after binding, and rechecks current principal data scope on **all concrete calls**. The return is `PaperObservedBinding(producer, plan)` with fully bound but **UNEXECUTED** consumers, `executable_authority=False`, `provider_provenance_verified=False`, `independent_e2=False`. It never runs leaves or accepts a fake caller-supplied `ToolResult` as authentic; fresh executor policy checks remain mandatory for any eventual consumer invocation.

**New explicit actual-consumer slice (2026-10-24):** `src/schemarouter/paper_consumer_execution.py::observe_and_execute_paper_plan` executes **producer + original consumers**, but only in this opt-in async call (not the default planner, `observe_and_bind_paper_plan`, or normal batch API). It owns the prior real executor observation *internally*; it does **not** accept a forgeable caller-constructed binding receipt. It pins the original `PrincipalContext` claims using a deep executor copy and rejects original or pinned claim mutation after every awaited source/consumer operation and immediately before publishing; `observe_and_bind_paper_plan` also rejects principal swaps during source observation. It re-compiles the same P1/P2 proof and verifies current caller scope before **and after each consumer**, executing the next leaf only after those checks. Each read-only original leaf uses a separate `ExecutionPlan` and existing executor principal authorization with `ExecutionBudget(max_tool_calls=1,max_attempts=1,max_remote_attempts=1)`. At most K-1 leaves execute sequentially, and any revocation, changed typed shape or transient failure halts without publishing a partial combined result. The API rejects source-required consumer fields absent from actual executor data using existing `ToolResult.field_contracts`, including **nested/wildcard `FieldSpec.result_path`** instead of assuming every selected field is a top-level key; object payloads and lists of objects are accepted, an empty list means no matching records. An explicitly present `null` can carry field metadata but `has_observed_value=False`; invocation success is not a claim of non-null factual evidence. Result: `PaperExecutedToolSequence(producer, consumers, plan)` explicitly `executable_authority=False`, `provider_provenance_verified=False`, `independent_e2=False`. This is measured **local E0** tool execution, not source-authenticated live E2 or paper answer quality. See [internal consumer execution plan](paper-consumer-execution-e0-plan.md).

**Review-driven K5 correction:** the original P1 shared-root fork can remain complete even when individual, *unrestricted* G5 one-hop result sets exceed K5 due to unrelated native roots. A review found that the first observed-binding implementation did an unrestricted per-leaf G5 lookup and could execute the root unnecessarily before failing `over_k_unranked`. A failing regression now proves one attested three-route P1 fork alongside **six unrelated status one-hop paths**. The corrected implementation preflights each **P1-pinned exact root+consumer pair before execution**, using the existing G5 `_lookup_native_paths` internal fork-arm **root and target filters**, which still perform source, type, scope, policy, health and fingerprint checks. The public K5 limit is NOT changed. To reuse G5's strict scalar/field-contract validator without forcing another unrelated public K5 menu, `native_graph_observation.py` now shares its internal `_materialize_original_observed_edge` between public observation (which retains BOTH normal unrestricted authorization lookups) and the paper path (which proves the selected exact pair before and after scalar materialization). No private candidate/count leaks into the result. The new regression is RED before and GREEN after the fix. Additional negative tests: missing/null/wrong/oversized original ID, revoked consumer authorization/availability after producer, exactly one producer attempt on transient failure, and no-fit host-parameterized 1:N fork.

The source-native **1:N shared-root fork proof deliberately excludes roots requiring host input** (`native_fork_index.py` rejects `source_root_parameters`). A host-approved parameterized original producer can be observed only in already proven **1:1 G5** shape. A separate source-owner-reviewed fork-root contract would be needed before lifting this constraint; do not manufacture a P1 proof for 1:N by repeating the root or inferring a join. The new observed binding test runs bound local invokers with one root + two leaves (zero consumer invocations) and a separate approved 1:1 host-parameterized root case. All of these are development-local E0; a registered invoker execution does not authenticate independent provider identity or establish answer quality.

Input: same **trusted** principal, owner-reviewed `NativeConceptCatalog`, source-native `NativeSchemaGraphIndex` and **exact** K5 as P1. First require `retrieve_paper_field_coverage` to prove a **complete** selected alternative. No tool/field inferred from text or untrusted metadata; no independent ranker/index/agent/LLM call. Then compile *only original source-attested routes* into standard `ToolCall` models:

- `.tool`, `.endpoint`, `.schema_fingerprint`, `.tool_fingerprint` from the original registry/index proof;
- `.fields` from the exact source-visible projection, `.evidence` from standard `available_evidence`, and projected `unit`, `qualifiers`, source/license per original field in `PaperPlanFieldMeta`;
- `.arguments={}` until **validated** host values or observed results are actually available; required inputs listed under `ToolCall.missing_required_arguments`;
- optionally `host_source_arguments={"original.approved_root": {"required_scalar": value}}` to supply an **exact complete** 1–4 scalar input envelope for an **already approved original G5 host source root only**. This reuses `_host_source_input_names` and exact JSON-schema validation, strict primitive types and bounds, and never accepts partial/default/unknown/consumer inputs. Only the source call's missing-input list is cleared; dependent consumer arguments remain deferred. No input values are inferred from the query or retrieved from a provider here;
- for an original record producer and up to four typed consumer branches, explicit `PaperPlanBinding(consumer_call_index, parameter, producer_call_index, producer_field)` with *no synthetic customer IDs*.

`PaperTypedToolPlan` has `status` = `ready` (only the call shape contains no missing required inputs), `requires_arguments`, `requires_observation`, or the source abstention (`no_proven_hit`/`over_k_unranked`/`budget_unsatisfied`). It is **not** `ExecutionPlan`, and sets `executable_authority=False` even for `ready`. Never feed dependent partial calls to the normal executor in one batch: that would be misleading because a producer might execute before a consumer's missing input fails. Actual invocation stays behind the existing per-call executor/authorization/evidence boundaries after runtime observation. No default `retrieve`, `plan`, or `execute` code was modified.

Two checks bound compilation: each route's original fingerprint/read-only/authorization/availability/scope and output projection is checked again, then the **entire** P1 result is recomputed and compared. For **argument-bearing calls**, the existing executor's `AuthorizationPolicy.validate_data_scope` and current **scoped input schema** are checked *before and after* the final P1 observation. For example, a scalar `max_hops=999` is **rejected** if the current principal's `DataScopeRule` caps it at `2`, although the original unscoped source schema allows integers. Original registry/index, principal, catalog, policy digest and retrieval witness must remain the same. Host callback errors during compilation are sanitized to generic `PolicyViolationError` without leaking private exception text. This is **two observations, not a linearizable provider transaction** and not a guarantee against revocation after the returned receipt.

Safety regression expectations:

1. Direct source complete: typed schema/projection/evidence, explicit IDs, no irrelevant fields and no execution.
2. 500-original-route mixed-scope fork: original root ID, one typed deferred consumer per required field, exact parameter/field bindings, no invented arguments; hidden/denied/unlicensed decoys excluded.
3. Missing leaf or unapproved required input: **no partial tool plan**.
4. Wrong K5, invalid alternative, stale original registry, revocation while compiling: fail closed.
5. Converter-native OpenAPI + MCP fixture: cannot publish a fork without the owner-reviewed input/output semantic attestation; EN/KO/JA aliases cover same original field contract.
6. Host-approved required producer input (`post_id`) stays explicitly *missing*, downstream `user_id` remains dependent on observed `userId`. An unapproved host root is `no_proven_hit`; no bound local test invoker is called.
7. When the caller explicitly provides `posts.by_id.post_id=42`, the source's typed call carries precisely `{post_id: 42}` but its consumer still awaits `userId`. Absent, wrong-typed, unbounded, extra, unknown-route, or consumer-prebound host arguments are rejected; three owner-declared languages are covered and nothing executes.
8. Call-level data scope: max-hops host scalar must satisfy the *scoped* principal-specific maximum before any typed receipt is returned. A real code review found and reproduced this missing scope validation; the new negative test was red before the fix and green after both scoped-schema and executor data-scope checks were added.
9. Mid-compilation policy shrink: an initially permitted `max_hops=2` is rejected if the authorized limit drops to `1` before the final source proof. No partial typed call, execution or private output is produced.

## Remaining acceptance work (do not mislabel as finished)

- **P2 domain-specific host input semantics:** bounded, validated **original G5 source-root scalars are now supported** via explicit caller arguments, but owner-reviewed semantic value sourcing (including OPTIMADE `get_structures(id)`, complex enum/date domains and numeric unit canonicalization) is **not** yet implemented. No argument values are parsed from language; an explicit separate observed-execution API can now obtain a producer's ID, but only through the existing execution authority and without running leaves.
- **Paper Understand(q):** bounded small-model (intent/concept/parameter/source/tool) contract and explicit host-review/provenance of parameter binding; current P1 uses exact owner-approved aliases only.
- **Paper meta and data:** source-visible field descriptors are metadata *declarations*. Opt-in observed binding and separately authorized consumer execution can now return actual locally registered executor `ToolResult` data, but this is **not** independently authenticated publisher provenance or source-owner canonicalization, nor a complete multi-tool answer/quality assessment.
- **Full E2:** independent dataset, actual data reader, retrieved **data-context** tokens vs schema/input/output tokens, answer/provenance/license correctness, same K5 and same hardware. Source-authored E0 tests are **not** E2.
- **PR gates:** inspect new remote P2 exact-head Actions/CodeQL and review, keep P2 Draft and stacked on #1746 until P1 can safely merge. No production or release promotion.

## Cross-session resume procedure

1. Read this file, the [internal observed-binding implementation plan](paper-observed-binding-implementation-plan-20261024.md), the [consumer execution continuation](paper-consumer-execution-e0-plan.md), the P1 handoff and paper Algorithm 1; inspect issues #1535/#1560, Drafts #1745/#1746 and any P2 Draft; inspect their **current exact head SHAs**. These plans are intentionally outside `docs/**/*.md` so unreviewed internal engineering pages cannot masquerade as part of the independently reviewed bilingual public-documentation corpus.
2. Check working tree, branch and CI results. For test execution use `uv run --offline --no-project --with-editable '.[mcp]' --with 'pytest>=8,<10' --with 'pytest-asyncio>=0.23,<2' --with 'hypothesis>=6.130,<7' --with 'ruff>=0.9,<1' python -m pytest -q` with `UV_CACHE_DIR=/tmp/sr-uv-cache` or equivalent resolved dependencies.
3. Begin next implementation from a **failing test** for source-owner attestations covering actual OPTIMADE host values and canonical physical units, or bounded original-paper `Understand(q)` semantics. The earlier `observe_and_bind_paper_plan` API still only populates consumer `ToolCall` arguments; actual consumer I/O requires the **separate explicit** `observe_and_execute_paper_plan` API and its current authorization, data and one-attempt constraints.
4. Update this handoff after any measured change with local/full test counts, exact remote commit, GitHub workflow conclusions and outstanding gates. Do not close #1346/#1477 or promote #1356 based on E0 alone.

**Local verification checkpoint (2026-10-24):** focused original-paper/native observed binding/consumer execution/native host-root/real-converter/public-API regression **172 passed**; repository-wide Ruff **green**. Independent whole-slice review found two Important defects: source A → leaves B after mutable principal swap, and incorrect denial of valid nested `result_path` consumer outputs. All three added regression scenarios (source/leaf principal mutation, nested output) were **RED before / GREEN after** correction, and the original observed-only receipt gained a separately RED→GREEN principal swap guard. The whole repo local pytest ran with a **240-second cap and timed out at about 12%**, no overall pass claim. Prior GitHub head `7de59e8` had **14/14 successful Actions workflows**; the new consumer-execution head must be checked separately once published. The Korean whole-corpus exact-review-ledger audit remains unchanged: internal plans live in `research/autoresearch/`, with no fabricated translation review. Independent live E2 and #1356 release remain blocked.


## OPTIMADE source-attestation follow-up (E0, 2026-10-24)

- Added an explicit host-review API for one original OPTIMADE entry type. It pins the discovery fingerprint, versioned base URL, source identity, source license, field semantic IDs, source-unit declarations, and host-authored conversion factors. It returns a new single-entry-type ToolSpec without mutating discovery or inferring a conversion from provider unit strings.
- The reviewed GET endpoint has a closed required scalar ID schema. Runtime GET responses must echo the requested entry ID and entry type; a mismatched HTTP 200 is rejected before field projection.
- Paper field planning may select a host-approved, parameterized root only when the complete owner-declared semantic/unit contract is visible. The plan remains non-executable; absent host ID yields requires_arguments. Plan metadata distinguishes source unit from canonical unit.
- This remains E0. It does not authenticate a provider independently, certify licensing beyond the host declaration, establish actual-materials answer quality, or clear independent E2 / release HOLD.

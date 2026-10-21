# G5 source-scoped Top-5 overflow ranking boundary (E0 only)

**Issue #1560 — 2026-10-20.** Existing G5 graph index currently returns
`over_k_unranked` with no candidates when more than five complete native
producer→consumer paths survive. Alphabetic first-five is **not** a ranking
policy, and exposing the full index before current authorization is unsafe.

## Narrow opt-in engineering change

The existing `NativeSchemaGraphIndex.lookup` behavior is **unchanged by
default**. The private, explicitly research-named `_research_ranker` callback
is considered ONLY after the full canonical graph/typed binding check,
original-source fingerprint verification, principal authorization, current
availability, data-scope hidden-field projection and all K-boundary
result checks. The supplied callback sees only the original, bounded user
query; up to 32 already-authorized, fully typed and source-pinned immutable
`NativeIndexedGraphCandidate` objects; and fixed K=5. It receives **no**
registry, invoker, hidden fields, private execution state, expected
route/gold or tool executor. The callback is trusted host code and should
not be exposed to arbitrary untrusted tenant input.

A candidate callback may choose **exactly five distinct offered tuple
offsets** or return an empty tuple to abstain. Partial, duplicate, boolean,
out-of-range and non-tuple output is rejected; the host MUST not
replenish/guess missing choices. After callback execution, the original
live source version, authority witness and authorization policy are
revalidated before any candidate result leaves the operation.
A catalog with more than 32 fully authorized graph paths returns the
original `over_k_unranked` without invoking the callback, rather than
exposing unbounded schema bytes or arbitrarily truncating the evidence.

**Results are explicitly unverified:** `ranked_unverified` or
`ranker_abstained_unverified` with `experimental_ranked=True`;
`independent_quality_evidence`, `calibrated_no_fit` and
`executable_authority` remain false. An empty model callback result is
**not** proof that a task is unsupported. There is no new default ranking
policy, embedding model, claimed multilingual quality, or API semantic
promotion.

## Regression and next qualification

The no-model contract suite includes baseline unchanged overflow,
authorized exact-five ordering, source evidence, hidden output fields,
denied and unavailable providers before any callback, malformed/forged
callback output, 32-path hard cap, model abstention without no-fit claims,
registry/policy/availability changes during callback and no agent/tool
execution. GitHub Python/CI CodeQL is necessary but NOT sufficient for
experimental model quality.

**Before any production promotion**, test a pinned actual ranker on
publisher-authored original EN/KO/JA/OOD tasks with source rights and
declared field/argument/operation requirements (#1346); preregister
supported required-path Recall@5, forbidden/unsupported behavior, scored
agent completion (#1477), per-stage p50/p95/p99 CPU and schema bytes;
compare source-native FULL/lexical/E5/hybrid/typed policies on identical
task+principal cohorts. Calibrate no-fit separately. Frozen negative
#432 and v0.18 release #1356 HARD HOLD are unchanged.

## Existing DecisionBackend integration, still E0 and unscored

`scripts/research_g5_decision_backend_ranker_e0.py` implements a
`ResearchAuthorizedG5DecisionRanker` callback using the existing
`DecisionOption`, `DecisionRequest` and host-owned `choose_sync` response
validator. Each already source-scoped graph path becomes a unique local
`path_00` option. The only model-visible label/description is its
authorized consumer route, validated producer route, complete output field
names and typed parameter→producer-field bindings. No raw backend registry,
gold, hidden field, credential, tool results or invoker is included in
options or metadata. The entire serialized request, **including original
bounded query**, has a separate fail-closed 16,384 UTF-8-byte cap.

A model response is *not trusted*: `choose_sync` checks typed selection
envelopes, offered option IDs, duplicate/overflow and malformed decisions.
The adapter additionally requires **exactly five results** or a full
abstention; a partial model output fails rather than padding from alphabetical
candidate IDs. The enclosing G5 lookup rechecks current authority after the
untrusted model call and marks any returned Top-5 ranking explicitly
`ranked_unverified`. This adapter is backend/provider-neutral; no actual
embedding quality is asserted. The regression suite uses an injected
deterministic backend to check positive ordering, model-forged options,
partial selection, explicit abstention and byte budget; no injected mock
may claim real-model or independent E2 evidence.

Before measured comparisons, choose and pin a real model/option-text policy,
freeze unexposed author-independent EN/KO/JA + supported/OOD cases, and
qualify candidate relevance AND task completion under #1346/#1477. This
integration is wiring only, not validation of a reranking algorithm.

## Preregistered actual pinned multilingual E5 model DEV (no external gold)

`scripts/research_g5_e5_overflow_cpu_dev.py` builds 25 registered
synthetic native routes: one current-policy read-only customer/account ID
producer and **24 one-hop read-only typed consumers** all advertising the
identical required account-ID input and the identical `service.status`
output field. This is a deliberately ambiguous 24-path graph. The only
consumer identity available to the E5 model is the English route key
(`service_refund.read`, `service_invoice.read`, etc.); it is NOT a
publisher-authored heterogeneous schema catalog or a trusted independent
multilingual translation/ontology.

Frozen *before measuring weights*: nine hand-authored supported
service-specific queries each in EN, KO and JA (**27 supported**, one
expected native consumer path per query), plus one explicitly unsupported
lunar/space task per language (**3 OOD**). The source-typed host supplies
a single exact query alias into `NativeDeclaredFieldGroup` per request
because this E0 setup has no validated query-to-concept model. The
author-generated expected route is available only to the scorer AFTER the
G5 ranker has made its full selection, never to the backend, candidate
descriptions or K5 construction.

Compare: (a) original G5 default `over_k_unranked`; (b) a deterministic
first five of the **same fully authorized scoped** candidate source list;
and (c) real `intfloat/multilingual-e5-small` CPU, pinned to the exact
existing 40-hex revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98`, using the existing
`real_cpu_backend` + E5CachedEmbedder/DecisionBackend + new strict G5
decision adapter. Report each language's supported `Recall@5` counts,
first5→E5 paired rescue/regress counts, model-ranking whole local
source-lookup p50/p95/p99 and the number of OOD tasks with **nonempty**
lists. The script refuses any changed default over-K contract, unverified
response status, out-of-source route, executable-authority claim or
invalid native dependency path. The output contains only aggregate
counts, hashes/revisions, model runtime and timings: no raw queries or
case-by-case gold leakage.

**Known limits**: first5 and E5 rankings of 24 paths are unverified
synthetic DEV, and K5 recall has a 5/24 chance-level reference, not a
production task pass rate. Because E5 input contains only English route
identifiers and generic same-status input/output semantics, failure for
KO/JA can reflect insufficient source-owned multilingual metadata as
well as model behavior. For unsupported queries, a nonempty Top5 is NOT
a calibrated false positive; no no-fit classifier exists. No vendor
permission attestation, external API, agent/tool execution, hidden
independent test, or full production schema-byte model is included.
#1346/#1477 and frozen #432 remain the product qualification gates.

## 2026-10-20: Actual Qwen3 + actual E5 paired *agent fixture* preflight (#1477 A)

The new research script `scripts/research_g5_qwen_agent_fixture_dev.py`
**reuses** the canonical `run_generated_episode`, `FrozenCorpusExecutor`
and principal-scoped `AuthorizedAgentToolSurface`; no new agent loop or
tool executor. Only the experiment condition
`EVAL-FIXED5-OPTIN` is used. Each original candidate callback maps the
already source-revision/policy/field-checked G5 consumer path Top-5 to the
original agent tool inventory, revalidating source and visibility after
the model. Both arms use the same registered native source, principal and
model-visible tool definitions; one uses first-five source order, one uses
pinned actual CPU E5. Gold/expected routes and post-call observations live
exclusively in the unchanged fixture grader; they are not passed to the
selector or Qwen agent.

Before any model run, the **six deliberately disclosed DEV** tasks are
frozen: refund status (English), invoice status (Korean), delivery status
(Japanese), each with the declared synthetic `acct_demo_7` account ID and
one local read-only fixture step, plus one unsupported space exploration
task per language. Exact K=5 is enforced and arm order alternates.
This is explicitly a **one-step** task per supported request, not proof of
executing producer→consumer root chaining. Each unsupported task has no
fixture steps; an agent must refrain from any tool and answer the exact
`REQUEST_MORE_TOOLS` sentinel to pass.

The CLI's real mode first constructs the existing pinned
`intfloat/multilingual-e5-small` CPU backend and frozen Qwen3-0.6B
agent; only then, **after all episodes finish**, it may label the
result as real-model **fixture DEV**, never independent native E2.
The public JSON contains just language × arm aggregate fixture
completion, unsupported attempted tool calls and strict no-call,
observed stage labels, aggregate tokens and paired timing. It contains
no source requests, fixture expected routes, raw arguments, executor
state, observations, generated answers, task IDs or model CoT.
Injected models are always reported as un-attested, and a private HMAC
is kept out of artifacts.

A green experiment validates wiring and reveals real downstream agent
failures, but does **not** establish native external-provider execution,
publisher gold independence, result/final-answer factual correctness,
multi-step compositional retrieval, calibrated no-fit, or production
task-success noninferiority. Frozen #432 negative task success and
v0.18 #1356 release HOLD remain unchanged; #1346 independent intake is
the blocker to stronger claims.

## 2026-10-20: Actual Qwen+E5 *negative downstream attribution* and bounded stage funnel

The predeclared actual CPU [Qwen+E5 G5 fixture run 39342383185](https://github.com/JDeun/SchemaRouter/actions/runs/39342383185) succeeded at the **experiment execution** level. Pinned real Qwen3-0.6B and multilingual-E5-small produced task-level **fixture completion** **0/3** (fixed first-five) versus **1/3** (E5 K5). EN supported E5 completed, KO and JA supported E5 failed. Both arms had **0/3** strict unsupported `REQUEST_MORE_TOOLS` responses despite making **zero unsupported tool-call attempts**. The Qwen agent's visible evidence after retrieval is insufficient for automatic no-fit; a no-tool decision is not necessarily a calibrated abstention. Earlier supported E5 24-route **25/27** Recall@5 is a separate frozen public synthetic DEV retrieval cohort; never read it as 25/27 agent pass.

The existing `sanitized_e0_trace` already reports only trusted **post-execution observed stages**. Without changing the executor, task corpus, system prompt, model weights, ranking policy or frozen independent #432, the same E0 runner now additionally aggregates a **funnel**, explicitly separating:

- supported expected source path *exposed at K5* vs not exposed;
- attempted tool call, observed wrong operation/schema rejection/argument mismatch;
- completed deterministic fixture task, then separately whether a final agent turn followed that completion;
- unsupported no-call vs strict **correct terminal refusal** vs incorrect terminal response.

This is calculated from the sanitized per-episode evidence and same trusted post-run summary, not from any new model-visible gold or scorer feedback. All aggregate stage counts must be internally consistent: `completed_with_final_turn ≤ fixture_complete ≤ required_route_visible ≤ 3` and `correct_unsupported_refusal ≤ unsupported_no_call ≤ 3`, separately for both arms. Unrecognized source/evidence contract, changed route budget or missing stage evidence must fail closed.

This does **not** repair the publicly exposed DEV failures, change the existing language queries or model prompt, tune a threshold on three OOD tasks, or introduce a separate agent loop. It produces a more falsifiable breakdown for prioritizing genuine independent externally sourced (#1346) supported/OOD/multi-hop completion (#1477). With only six disclosed source-authored tasks, it is **not** a causal or statistically stable estimate of production route-exposure rates, operational agent pass, final response factual accuracy or SLA. Keep PR #1612 DRAFT and #1356 HARD HOLD.

## 2026-10-20: Original fixture prompt confound — predeclared A/B

The previous actual-agent 6-case G5 fixture experiment found E5:
**2/3 required source paths exposed**, **1/3 fixture completed**,
**1/3 completed with final turn**, **2/3 wrong-operation attempts**, and
**0/3 exact unsupported terminal refusals** despite no unsupported tool
attempts. The source-first-five control exposed 0/3 required paths and
completed 0/3. These are exposed public synthetic DEV tasks.

Source inspection identified a **confound in the original research-only
system prompt**: it advertises the example function name
`service__read`, while none of the 25 actual registered native function
names equals that value. The old agent runner independently provides the
real function list. Therefore any agent/tool-choice comparison using only
that prompt cannot isolate the model's understanding from conflicting
instructions. There is NO evidence proving that this typo caused the
observed failure, and historical results remain unchanged.

A same-run prompt counterfactual is now scheduled using unchanged
Qwen3-0.6B/E5 pinned weights, exact same six tasks, same scorer gold
(separate from inference), same source/principal/typed G5 K5 ranker,
same existing agent loop and frozen tool executor. Original
`SYSTEM_PROMPT` is preserved as `legacy_unregistered_example`.
`GROUNDED_PROMPT` refers to **no concrete tool name at all**, instructs
the agent to choose an exact name and JSON arguments only from the
currently provided function definitions, and preserves the same strict
`REQUEST_MORE_TOOLS` unsupported terminal convention.

Both existing source-first5 and actual E5 K5 arms are rerun under each
prompt; the report publishes only identical sanitized per-stage
source exposure / wrong op / fixture complete / exact OOD refusal
aggregates, with explicit `PUBLIC_SYNTHETIC_DEV_PROMPT_CONFOUND_DIAGNOSTIC`
tier, and no raw model output. The prompt comparison has **fixed
legacy-before-grounded order**, thus inference warmup and order are
confounded; do NOT interpret a difference as fully causal or as an
independent post-hoc confirmation of a winning prompt. The public cases
have already been inspected and are now developer-tuning examples.
No model, API, field policy, native tool inventory, task gold, or
production system prompt is modified by this research-only change.

If a difference is observed, next acceptance requires separate
**unseen publisher-authored** cases and a counterbalanced evaluation
of both prompt orders, genuine original provider-owned tools and
a calibrated OOD/no-fit outcome, including task and final-answer
correctness. Keep #1477/#1346 OPEN, #1612 DRAFT and release #1356
HARD HOLD. Historical independent #432 metrics never change.

## 2026-10-20: ABBA order-control remeasurement — same public DEV

Following the original observed A→B (legacy bad-name example →
inventory-grounded names) synthetic DEV difference of **1/3→2/3**
fixture completion with E5 source K5, we preregister a **two-block**
A→B→B→A comparison. This reuses the original six public fixture
tasks, the original one-step `FrozenCorpusExecutor`, the same
source/authorization/role/typed G5 K5 callback, pinned actual
Qwen3-0.6B and E5 checkpoints, scorer-only gold and original prompt
strings. Thus the only experimental intervention is the system-prompt
condition, and each condition occupies both first and last block
positions rather than being exclusively earlier/later. A total of
**48 agent episodes** (4 blocks × 6 original requests × 2 fixed-K5
selection arms) run on actual Linux CPU using the existing original
`run_generated_episode` path. No data labels or trained weights change.

`summarize_balanced_prompt_runs` is an entirely post-execution,
no-model aggregation and enforces exact A→B→B→A ordering; two
independent source-arm records per block; identical source snapshot
SHA-256, gold/permission constraints and original case count;
unchanged **unverified** authority flags; finite integer E0 counts
and monotonic route-exposed→fixture-complete→final-turn and
OOD-no-call→exact-refusal stages. It reports both observed block
positions and pooled descriptive counts **/6 supported and /6 OOD**
per prompt × source arm. It exposes neither query text nor target
tool names, arguments, task IDs, generated answers or gold.

**Limits remain material:** the cohort is developer-authored,
already seen and used to revise a prompt; ABBA is deterministic,
not randomized or independently evaluated and cannot remove agent
nondeterminism, adaptation across repeated identical tasks, passage
representation limitations, hidden order/time drift, or performance
uncertainty across domains. Four passes are a diagnostic robustness
check, not a causal/statistical performance estimate or independent
E2 success. We keep the original 2026-10-20 A→B first-leg result
intact as historical evidence and expose the later two reversed
passes separately. The output must remain
`PUBLIC_SYNTHETIC_DEV_ABBA_PROMPT_ORDER_DIAGNOSTIC`, not a claim
that the model was externally confirmed; unsupported no-fit is not
calibrated. An independently authored, permission-reviewed,
publisher-disjoint task+OOD holdout remains blocked by #1346,
and v0.18 PR #1356 stays HARD HOLD.

## 2026-10-20: real E5 score shadow audit — zero threshold tuning

The source-native G5 ranker now has an optional `UnscoredE5ScoreObserver`
wrapped around the existing pinned `EmbeddingDecisionBackend`. The wrapper
passes the **exact same verified `DecisionResult`** back to the original
G5 authorized ranker, without resorting, shortening, rejecting by score,
granting execution permission or changing any model prompt or inputs.

Only after each successful current-authorized G5 lookup does the
scorer aggregate **top cosine**, **fifth selected cosine**, and the
**difference between those two selected candidates** across the 27
developer-authored supported EN/KO/JA cases and three public OOD
cases. Crucially that last difference is **NOT the fifth-versus-sixth
rank-selection boundary**, nor the top-versus-next margin. It must
never be substituted into `RetrievalAbstentionPolicy` as a fitted
threshold. Source labels (supported/OOD) are scorer-only and never
visible to the decision backend. All values are finite, type
validated and emitted as stratum/language counts and min/p50/p95/max;
no case/query text, embedding vector, gold IDs or option scores per
case are published.

**Safety correction:** `run(DecisionBackend)` is a testable Python
entry point and previously declared any injected fake backend a
`REAL_PINNED_E5...` result. It now returns explicitly
`E0_INJECTED_G5_DECISION_BACKEND_DEV_NOT_ATTESTED`, and
`real_model_routing_measured:false` for **all** injected backends.
Only the CLI path, after `real_cpu_backend()` constructs its pinned
model and verifies CPU/model identity/revision and the complete E5
score-only trace, may attest an actual pinned E5 run. A deterministic
fake-embedding test asserts that even perfect-looking score records
cannot self-certify as real inference; forged NaN/nonmatching score
envelopes fail closed before entering descriptive statistics.

This is a **public, in-sample source-owned diagnostic**. Three OOD
queries are far too few to choose a statistically robust no-fit
threshold; score scale changes across providers/catalogs and E5
cosine values are not probabilities. Without *separately*
provider-reviewed, author-disjoint calibration and confirmation
task cohorts and supported false-refusal / unsupported false-match
measurement, the opt-in external calibration gate in
`src/schemarouter/retrieval_abstention.py` must remain independent of
this G5 experiment. No thresholds or product defaults changed,
no-calibrated-fit and independent E2 both remain false, and frozen
#432/release #1356 remain unchanged.

## 2026-10-20: deny candidate witness mutation across untrusted ranker

The native G5 graph originally passed `tuple(found)` into the experimental
`_research_ranker` callback, then used **those same mutable-by-ref
dataclass instances** for the final candidate result. Although
`NativeIndexedGraphCandidate` is `frozen=True`, adversarial Python code
can still do `object.__setattr__` on a delivered candidate and alter the
route ID, output-field list or pinned fingerprints **after** source,
permission, hidden-field and availability checks. Later registry/policy
witness validation does **not** detect mutations of detached candidate
objects. This is an actual integrity risk at a callback trust boundary,
not merely a semantic ranking quality issue.

The research-only G5 callback now receives detached
`dataclasses.replace(...)` copies of the completely authorized source
candidate records. The original `found` list remains exclusively
owned by the source validation path and is the **only** origin for
returned candidates at selected offsets. No scorer gold, registry
executor, authority or new visibility is passed. An adversarial
regression deliberately bypasses frozen-dataclass restrictions to forge
`admin.erase_all_records`, secret output fields, fake fingerprints and
parameter bindings, then selects the corrupted offered offset. The
returned evidence must remain exactly the pinned original safe route,
field set, bindings and fingerprints. The source-unranked/default
result must remain identical.

This is a source-authority **engineering correction**; it does not
increase independent route recall, make a model's chosen operation
correct or qualify no-fit. G5 cannot execute a tool and remains strict
K5 and experimental over-K ranking only. Keep #1612 Draft until exact
head CI and real model tests are all green; #1477 E2 and #1346 external
independent heldout remain blockers, release #1356 HARD HOLD.

## 2026-10-20 account-identifier carrier query perturbation (public DEV only)

Previously source-native G5 24-route E5 ranked standalone tasks use a short
semantic request with no execution arguments: EN9/9, KO8/9, JA8/9
supported Recall@5, 25/27 total. The later pinned Qwen fixture supplies
a longer actual user request containing an account identifier
(` for account acct_demo_7`) and saw one EN/KO/JA task each: EN+JA
authorized K5 path found (2/3), KO source route missing (1/3).
The **task-only** versus **request-with-identifier** mismatch can make
per-request retrieval measurements and end-to-end agent performance
appear inconsistent. This does NOT establish why KO failed.

The paired `scripts/research_g5_e5_overflow_cpu_dev.py` CLI now uses
the same existing pinned actual `intfloat/multilingual-e5-small` CPU
model, original 24 identical synthetic route/source schemas, source
policy/actor and **same original 27 author-written EN/KO/JA positive
task intents and their scorer-only route gold**, with two frozen
query-surface conditions:

- `task_only`: the already measured original text, completely unchanged.
- `account_carrier`: append the *same exact source-neutral, original
  agent-fixture* ` for account acct_demo_7` to **all 27** supported
  requests, without selecting which tasks receive it based on
  model outcomes. Negative OOD tasks remain the same three original
  texts and are **not** new calibration examples.

This is an **ablation of query content**, not translation, question
rewriting, new label construction or fit classification. Before
running the pinned CPU model, exact source snapshot and model revision
are checked, and the same frozen origin requests/source/gold remain
fixed. The ranker receives only original source-scoped G5 candidate
path evidence and the supplied query, never gold. Outputs report
only per-language supported Top-5 recall counts and top cosine p50
for each surface, not individual task/route/account ID or full text.
The ablation runs **sequential task-only then account-carrier**
and is not interleaved/randomized; warming and source embedding
caching effects are not controlled. The synthetic account suffix is
a deliberate public fixture string, not a real customer ID.

This is a directly falsifiable diagnostic of **model retrieval
robustness to non-intent arguments** on previously exposed synthetic
DEV. Query stripping or any product behavior change is NOT authorized
by a favorable result. Neither the observed 3 OOD scores nor any
publicly exposed alternate query surface supplies prospective
independent no-fit calibration or publisher-authored task gold.
#1346 and #1477 E2 remain blocked; PR #1612 stays DRAFT, release
#1356 HARD HOLD.

## 2026-10-20: non-discriminative common-source-description A/B (E0 public DEV)

The 27×2 **account-carrier** perturbation run is already observed on real
pinned E5: task-only Top5 Recall@5 EN **9/9**, KO **8/9**, JA **8/9**,
versus full actual original account-ID carrier EN **9/9**, KO **7/9**,
JA **6/9** (total **25/27→22/27**), while top cosine p50
INCREASED in all three languages. That is a negative direct finding:
generic field/argument overlap can raise model similarity without
raising correct routing. It **does not** imply that removing identity
arguments from the production user query is safe or effective.

All 24 fully source-authorized synthetic G5 candidates in this
controlled source share the same description:
`source=customer_directory.read; output=status;
input=account_id<-account_id`. This description is derived from
the original live native G5 typed path proof and is identical among
all choices; it therefore offers **zero inter-option discrimination**.
The conventional E5 DecisionOption passage also contains each source
route's unique `service_<name>.read` label. The hypothesis is that
matching the user's added `account_id` against a large common
description can swamp the distinctive route label.

The opt-in **research-only** `ResearchAuthorizedG5DecisionRanker(
omit_identical_descriptions=True)` computes each scoped path's
original bounded description and removes it from **model-visible
DecisionOption text only if ALL authorized candidates have
byte-for-byte identical descriptions**. Heterogeneous descriptions
are preserved for **every** candidate; no token-level selective
masking, schema rewrite, route-name rewrite, query rewrite, hidden
field disclosure, path removal, privilege change, permission grant or
direct tool call occurs. No use of the query, task gold, expected
route, language ID or model ranking feedback in the omission gate.
The default ranker option remains unchanged.

The same real pinned E5 CPU and original G5 source now compare four
sequentially executed publicly disclosed *DEV* arms on the **same
27 original task intents**:
(1) full source description / task-only query,
(2) full / account-carrier query,
(3) source-description omitted iff identical / task-only,
(4) omitted / account-carrier. The three unchanged published OOD
tasks run in each arm but are NOT calibration data. Scorer-only
positive Recall@5 by EN/KO/JA and aggregate counts are the primary
diagnostic; no Task E2, agent performance, unique newly generated
gold, confidence intervals, source-publisher holdout, OOD
threshold, p-value, or stochastic ordering equivalence is claimed.
The four arms run sequentially, not interleaved, and repeated
model/text caching may confound differences.

A positive ablation does NOT authorize removing metadata from actual
source-owned catalog, or promoting a product ranking policy. It only
supports developing a later **source-scoped discrimination-oriented
candidate representation** with independently authored
provider-native cases and rights/permission approval, before
any production ranking or no-fit validation. #1346/#1477
block qualification; #1612 stays Draft and #1356 HARD HOLD.

## 2026-10-20: Transfer from E5 route recall to original Qwen task stage — no gold feedback

The four-arm **actual pinned E5 CPU** option-description ablation on
the original public 27 supported + three OOD developer-authored
tasks completed in [Actions 39357305326](https://github.com/JDeun/SchemaRouter/actions/runs/39357305326).
The supported route Recall@5 results were:

| Language, 9 supported each | Full text/task-only | Common text omitted/task-only | Full text/account-carrier | Common text omitted/account-carrier |
|---|---:|---:|---:|---:|
| EN | 9 | 9 | 9 | 9 |
| KO | 8 | 8 | 7 | 8 |
| JA | 8 | 9 | 6 | 8 |
| **Total /27** | **25** | **26** | **22** | **25** |

Thus removing identical candidate text restored three route matches in
the *account-carrier* condition on seen synthetic data, and one on
task-only, with no token-level language-specific rules. It does NOT
establish product-general corpus or independent provider improvement.

To check the **actual downstream model task outcome**, the same
research-only `run_fixture` now accepts a rigorously restricted
`source_arms=("e5_fixed5",)` and
`omit_identical_descriptions=True` **only with the previously
registered inventory-grounded system prompt**. It runs a *single
additional original six-task* pass through the original
`run_generated_episode`, original `FrozenCorpusExecutor`, original
authenticated source view, model and scorer-only gold, **after** the
existing four-block A→B→B→A prompt comparison. This avoids a new
executor and leaves the historical ABBA outcome unchanged. It reports
only one grounded source-text-omitted arm and compares its typed
route-visible / attempted-wrong-operation / fixture-complete /
correct-unsupported-terminal counts with the original two grounded
prompt positions. Model-visible named routes and the original
permissions/field bindings are unchanged; only their provably
identical and otherwise nondiscriminative description strings are
omitted in the research selector.

**Important**: this final extra 6-case pass is **after** all ABBA
runs, not randomized/interleaved. Warmup, repeated deterministic cases
and time/order are confounded, and the old three supported plus
three unsupported tasks are already publicly exposed. A true
successful fixture count would not establish independent E2, final
answer factual accuracy, provider-authorized native execution,
confidence bounds or a calibrated no-fit threshold. No product default
was promoted, no real service was invoked, and both #1346 and #1477
remain blocked. #1612 stays DRAFT; #1356 stays HARD HOLD.

## 2026-10-20: source-safe scorer-only E5 rank versus Qwen actual tool slot

The latest pinned actual Qwen3+E5 source-common-description experiment
[Actions 39358374072](https://github.com/JDeun/SchemaRouter/actions/runs/39358374072)
observed source route exposure increasing **2/3→3/3**, but original
synthetic one-step task completion staying **2/3**. The original KO
request acquired its gold path in Top-5 but Qwen selected a wrong
operation. Exact unsupported no-fit terminal remained 0/3. This
**separates retrieval failure from model tool-use failure**.

Further code inspection found a necessary ordinal distinction:
`ResearchAuthorizedG5DecisionRanker` selects source-scoped Top-5
**in E5 rank order**, whereas original `run_generated_episode`
then applies `visible_routes = sorted(selected)`, and displays
these tools to Qwen in **lexicographic route-name order**. Therefore
an E5 rank #1 path is **not necessarily the first tool shown to Qwen**,
and observing the model call slot #1 cannot be read as an E5 score
ranking choice.

A new experiment-only `GraderOnlyAttemptObserver` wraps the original
agent's `generate()`, passes messages/tools and the original return
object unchanged, and applies the same canonical
`_parse_tool_calls` parser used by the unchanged executor solely to
record transient route names. It discards generated text and all
arguments. The existing typed G5 source callback independently
records the five already source-authorized *ordered* IDs in a private
one-episode receipt (not gold or model inputs). **After**
`run_generated_episode` completes, the evaluator requires exactly
one rank receipt; exactly the observed original tool-call count; and
agreement between its sorted selected IDs and the actual first-turn
model-visible tool names. It then compares the private original
fixture expected operation with the private rank receipt and first
attempted route, publishing ONLY:

- expected path's 1-based rank within the selector's K5 (or absent);
- first attempted operation's K5 ranking position, if selected;
- first attempted operation's name-sorted *model-visible* slot;
- Boolean whether the first attempt matched the original scorer-only
  expected operation, plus whether the first operation was outside
  the selected K5.

No route names, raw queries, arguments, completions, account IDs,
original case identifiers, final answers or tokens are emitted in this
new ordinal report; the original model/permissions/registry/agent and
tool selection are unchanged. These rank receipts are **scored
after** all tool execution and never exposed to the decision backend
or to Qwen. New adversarial unit tests reject inconsistent
candidate/attempt counts, duplicates, rank/view permutation
mismatches, while deliberately distinguishing name-sorted slot from
E5 rank and verifying no raw arguments are captured.

This diagnosis is limited to the same three already-public synthetic
supported cases with a one-step deterministic fixture (and same
three unsupported cases). A first attempted operation can differ
from a later attempt, and E5 rank is not the original Qwen visible
ordering. It cannot establish independent publisher E2, live
provider success, causality, calibrated no-fit or general language
accuracy. No default ranking or production policy changed; #1612
stays DRAFT, #1346/#1477 remain blocked, #1356 release HARD HOLD.

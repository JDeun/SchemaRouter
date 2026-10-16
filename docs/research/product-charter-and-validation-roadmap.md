# SchemaRouter product charter, evidence map and acceptance tests

**Decision baseline: 2026-10-16 · Status: documented design, NOT a new performance claim or release permission**

This is the cross-session **product-and-evaluation decision contract**, not a proposal to discard or redesign the stable public facade. Read it alongside [Design principles](../concepts/design-principles.md), [What SchemaRouter is](../concepts/schema-router.md), [Stable core contract](../stable-core.md), [Architecture and trust review](../architecture.md), the [experiment index](../research/experiment-index.md) and the [prior OSS investigation wiki](../research/tool-routing-landscape.md). Where an older document calls a past activity `active`, distinguish that recorded date from this 2026-10-16 checkpoint. Canonical source results and frozen score reports always outrank this narrative.

## 1. Mission and product thesis

**Mission:** allow a host application or agent to discover, select, plan and invoke the *smallest justified set* of genuine, source-registered capabilities across APIs, MCP, tools and data systems, with typed semantic fields and **host-controlled** authorization, validation and execution.

**Not the mission:** build another autonomous agent framework, host a chat/memory/graph runtime, route between LLM price tiers, replace MCP/Pydantic AI/LangGraph/LlamaIndex tool lifecycles, synthesize fictional executable schemas, or let the retrieval/model score authorize a call.

**Product value proposition:** tool routers usually answer `query → likely tool`. SchemaRouter must support `query → logical data/operation need → required source fields/inputs → currently eligible tool/endpoint/provider/access path → bounded typed plan → checked invocation → validated, minimized result`. The downstream agent owns goals, dialogue and multi-step orchestration; the local host owns policy, credentials, source registration, dispatch and approvals.

## 2. Principles that must survive all optimization

| Invariant | Engineering implication and required failure behavior |
| --- | --- |
| **Source provenance precedes model inference** | Executable identity comes from the registered `ToolSpec`/`EndpointSpec` or verified adapter source; source fingerprint and current registry identity/version remain checkable. A model cannot invent endpoints, fields, schema privileges or aliases. |
| **Fields/operations are typed contracts** | Distinguish required inputs vs obtainable outputs, `semantic_id`, type, unit/qualifier, effect class, provider and access mode. High semantic similarity must never override a missing required field/operation or an incompatible unit. |
| **Auth and data scope filter discovery** | Host Principal/RBAC/ABAC, hidden fields and local availability apply *before* untrusted model input. Ranking over hidden tools or leaking counts/descriptions is unacceptable. Public candidate count is **positively scored pre-Top-K eligible**, not proof of authorized registry completeness. |
| **Retrieval != action** | Search and model shortlists only return suggestions, not execution authority; never call providers inside a retrieval benchmark. Approval and executor revalidation occur later, including argument JSON Schema, fingerprints, trusted bound invoker, policy, retry/budget and raw/result field scope. |
| **Bounds remain explicit** | K, tool calls, schema-token/byte budgets, latency, memory and fallback width must never silently grow to win recall. Measure **model-input bytes**, **tool-schema disclosure bytes/tokens** and **whole-agent tokens** separately. |
| **Supported, missing info, ambiguous, unavailable, unauthorized and unsupported differ** | An empty/nonempty Top-K or model abstention is not a calibrated classifier. Unsupported false acceptance and supported false refusal are distinct failure modes; no heuristic becomes product no-fit until fresh disjoint calibration and confirmation. |
| **Failure is visible; metrics are reproducible** | No unreviewed policy override, invented completion, erased negative trial, retroactive tuning on frozen holdout, post-hoc changing gold, or equating synthetic/local DEV with independent external-agent evidence. |
| **Small dependency and interoperable host boundary** | Default CPU-first Python API stays deterministic and dependency-light; multilingual models, remote services, vector search and frameworks remain optional and replaceable unless acceptance evidence justifies another contract. |

**Stable core:** `SchemaRouter.retrieve/aretrieve` and executable/state-aware variants remain read-only discovery; current planning, execution and integrations keep their owned boundary. A pure benchmark improvement alone does not reopen the [stable-core contract](../stable-core.md). For external systems, the SDK/host retains native approval, execution and lifecycle.

## 3. Evidence reconciliation — existing, negative, unresolved

| Evidence / task | What is **actually established** | What it **does not establish** |
| --- | --- | --- |
| Stable typed registry, adapters and guarded executor; #1466, #1470, #1472 fixes | Source/field contract integrity, honest scoped retrieval counts, bounded source-identity swap refusal; targeted CPU/CI regressions | Atomic multithreaded policy snapshots (ABA and in-place mutation remain #1450), broad autonomous success |
| #644 Pydantic AI, #645 Agents SDK, other adapter smokes | Concrete compatibility, limited filter/disclosure/no-call evidence; 12/50/100/250 Pydantic E0 size controls over a tiny 5-case synthetic set | Native SDK end-to-end answer win, independent user adoption, general no-fit success |
| 2026-10-15 Aurelio/LlamaIndex-inspired local CPU ablations | Four previously-visible EN/KO/JA configurations all **NOT PROMOTABLE**; forced choices falsely accept 18/18 OOD, raw cutoff variants reject 32/54 or 53/54 supported | Aurelio v1 `fit(None)` calibrated method was NOT the tested hard-coded cosine formulation |
| Real native Open-Meteo K5 pinned E5 vs lexical | Existing author-visible 27 supported multilingual DEV: 26/27 vs 18/27, with E5 one regression; 9/9 OOD returned nonempty | Independent fresh tasks, required native input-field recall, no-fit, end-to-end agent success |
| Real native ServiceNow K5 pinned E5 vs lexical | Existing author-visible 20 supported English DEV: 15/20 vs 17/20, all 4/4 OOD nonempty | Global E5 promotion, same language/provider quality across catalogs |
| Frozen #432 780-task held-out agent comparison | **SR-5 task success 29.19%, SR-10 31.03%, progressive 25.09%** vs **FULL 49.62%, ORACLE 70.98%**; every deployable condition failed the historical product/noninferiority gate. Initial KO/JA source-era 0/160 vs EN 153/160 required-route recall at 500 endpoints | A later DEV retrieval uplift does not retroactively repair these actual agent episodes; progressive eventual recall does not equal completed tasks |
| Opt-in semantic diagnostic #1474 / real CPU DEV #1475 | Authorized finite fixed-K local model comparison wiring and source-pinned CPU measurement; research code without new default | Independent provider-disjoint model winner or v0.18 readiness |
| External suites inventory #1346, provider/publisher review #1228 | Named source pins, executable/intake protocols and honest blockers | Independent human-authored gold and consent, completed external E2 or broad production SLA |

Authoritative detailed evidence: [OSS routing wiki](tool-routing-landscape.md), [frozen heldout benchmark](large-heldout-agent-utility.md), [research status](routing-status.md), [full experiment index](experiment-index.md) and [external evaluation tracker #1346](https://github.com/JDeun/SchemaRouter/issues/1346). Reported values above are **not one pooled benchmark**: different source providers, authoring, models, sizes and outcome definitions.

## 4. Single target pipeline — hypothesis, not product commitment

`host-authenticated query and typed context → (A) registered eligible catalog / scoped field contracts → (B) recall candidates using reproducible lexical BM25 AND opt-in multilingual dense (no unauthorized surface) → (C) fixed-K native source identity fusion → (D) declared operation/input/output semantic fit and unknown-input distinction → (E) separately calibrated no-fit / ambiguity / missing-info decision → (F) bounded tool schema disclosure to downstream agent → (G) executor-time source/argument/evidence/approval verification → (H) actual multi-step task and final answer`.

The pipeline is divided into **four independently observable questions**:

- **Discovery:** did every required source-native capability enter an eligible K-bounded shortlist without unauthorized disclosure?
- **Fit:** does the candidate truly supply the operation and *required fields* (including input variables), with units, side effects and dependencies intact?
- **Disposition:** supported and actionable vs information needed vs unsupported vs unauthorized/unavailable; was the refusal correct or over-conservative?
- **Agent utility:** when passed to the same agent, did *the complete authorized task* succeed, with correct answer/provenance, safe calls and lower resource cost?

Do not let an LLM or cosine score silently replace any one of these four independent gates.

## 5. Test roadmap — backlog with ordered evidence gates

| ID / priority | Question and reproducible test rows | Comparison / pass evidence (not invented target scores) | Blocker / owner |
| --- | --- | --- | --- |
| **P0-01: current-contract baseline** | Freeze commit/package, Python version, CI Ubuntu CPU, genuine registered source tool/field fingerprints, principal rules and canonical **FULL, lexical K5, existing optional model** behaviors. Re-run only **existing** tests to detect regressions, not rescore frozen rows as new science. | 0 unauthorized execution or hidden-field disclosures; no invalid source ID; default/public typed facade and tests intact. | Engineering; reuse current product CI and #1450 |
| **P0-02: test/task eligibility ledger** | Before reading labels or optimizing, record **who authored queries/gold**, license/permission, provider + commit + native schema/field hash, train/calibration/dev/confirmation separation, EN/KO/JA and mixed-source distribution, unsupported/ambiguous/insufficient scenarios. | A **new disjoint independent case set** or explicit `BLOCKED_EXTERNAL`, no made-up gold, reproducible manifest and duplicate/semantic-overlap checks. | Publisher/author review; #1228/#1346 |
| **P0-03: zero-call and authorization** | Positive/negative principal RBAC/ABAC, denied actions, all-hidden fields, visibility changes during ranking/inference/dispatch, stale schema fingerprints, local availability and source-swap/ABA adversaries, mutating input after approval. | Unauthorized/model-generated IDs/fields/credentials never reach backend or invocation, fail closed on changed source; keep stronger atomic snapshot #1450 separate. | Host safety; #1450 and existing execution security gates |
| **P1-01: multilingual route candidate coverage** | Supported EN/KO/JA, names/aliases, natural paraphrases, transliterated/mixed identifiers, missing outputs, 100/250/500 tools and multi-required-tool tasks with similar distractors. Paired **lexical / dense / hybrid** under *exact same K=5*, auth-visible native source and comparable serialized exposed schemas. | Per-language and per-provider **required-route-set recall**, false insertions, field-level coverage, per-task paired wins/losses, no variable-width union; external independently frozen split. Historical #432 product lower bound is NOT reset. | Separate opt-in retrieval experiment; #1339 |
| **P1-02: typed operation + parameter fit** | Find/read vs update/delete; wrong required request parameter, equivalent-looking output field, different unit/qualifier, vendor alias, multi-field/2-source requirements, empty/null result semantics. | Route/operation/required **input** and **output** field exactness; no model-excused absent fields; schema-compatible fallback only, checked on native publisher specs. | Typed compiler; source field reviewer |
| **P1-03: supported refusal vs OOD** | Near-domain unsupported action, totally unrelated request, unknown resource, missing parameters, ambiguous action, revoked permission; deliberate hard negatives in EN/KO/JA. **Train/calibrate/confirm on separated sources**, no thresholds tuned to previously visible 2026-10-15 trials. | Supported false-refusal, unsupported false-accept, unknown/ambiguous dispositions, **actual no-call** after abstain, calibration reliability/CI; threshold selected only using calibration set. | #1339/#1346; independent authoring |
| **P1-04: real agent completion A/B** | Same pinned agent/model/temperature/context budget/tools, identical actual task and source rights; FULL vs lexical K5 vs optional hybrid+fit/no-fit vs ORACLE (diagnostic only). Sequential read/state-dependent 2–3 steps, parameter propagation, result-grounded final answer, recoverable error, forbidden mutation. | **Actual task success as PRIMARY**, valid tool sequence, evidence/provenance, answer correctness, rate of safe refusal; paired task-cluster CI by task/language/provider, no task-repeat pseudoreplication. Existing #432 independent gate: lower 95% paired CI vs FULL ≥ -2pp, route recall ≥97%, tool-schema tokens ≤40% FULL, total input tokens below FULL and zero unauthorized destructive executions **only when valid same protocol**. | #1346 E2; cannot substitute a retrieval smoke |
| **P2-01: operational viability** | Linux GitHub Actions warm/cold startup, CPU-only no-secret installation, 100/250/500 size, indexes/cache invalidation under registry+role churn, p50/p95/p99, RSS peak, serialized **model input vs disclosed schema vs agent tokens**, provider dispatch wall time; Windows and fresh wheel/sdist smoke. | Report overhead and distributions on identical runner; prove reliability and source-completeness first. A measured CPU p95 is **not** an SLA without repeated production-equivalent trials. | Product performance work |
| **P2-02: external reproduction & release** | Third-party native author confirms source schema/gold and independently runs pinned harness; full negative outcomes visible, sign-off/permissions explicit; reconcile stable facade, docs and release artifact provenance. | External E2 only with genuine agent trajectories, no hidden missing cases, qualifying release gates and protected CI. Until then **v0.18 PR #1356 HOLD**. | #1228/#1346/#1356, external partner |

### Minimal case inventory for a genuinely new prospective suite

Cover **six task families** across EN/KO/JA (and optionally ES/DE/mixed): (1) one native read-only endpoint with exact required parameters, (2) multi-route field union, (3) stateful multi-step read and identifiers, (4) same-domain sibling operation read/write/destructive distinction, (5) insufficient/ambiguous/missing-field request, (6) truly unsupported/near-domain OOD. Cross with catalog sizes 100/250/500 and at least two independently sourced tool publishers. **Do not invent a sample size or pass percentage after seeing data**: preregister the actual available independent population, primary estimand, statistical precision and stop/go thresholds before any new scored run. All cases keep query, source gold, permission policy and downstream outcome provenance; duplicates by task/provider/source must be recognized.

### Failure diagnosis mapping: stop repeating whole studies

| Observed failure | Next subsystem to inspect — not another generic embedding trial |
| --- | --- |
| Gold route absent from authorized eligible registry | Ingestion/source metadata, policy, invalid field contract, catalog scope |
| Gold authorized, absent from shortlist in KO/JA | Query tokenization, alias/semantic candidate representation, K budget, retrieval-only fixed-K |
| Gold in shortlist, wrong operation/arguments | Typed operation-input/output fit and decision backend option contract |
| Supported request refused | Calibration/threshold/false-refusal, missing-info confusion, field-fit gate |
| Unsupported request accepted or called | Distinct open-set disposition **and** host execution/no-call gate |
| Candidate correct, task fails after later tool step | Downstream orchestration, timing, state, identifiers, evidence, final answer; cannot fix from Recall@K alone |
| Access revoked, cached result leaked | Versioned registry/policy snapshot, cache scope and executor-time authorization |
| Better recall but slower/too-large | Exact K, schema budget, index CPU optimization; do not grow the exposed candidate count |

## 6. Research operating rules and stop/go decision

**Do not start another model/framework comparison before:**

1. Reading this charter, [old-pattern failure wiki](tool-routing-landscape.md), [prior art](prior-art-roadmap.md), [92-record historical experiment index](experiment-index.md), and the status of [#200](https://github.com/JDeun/SchemaRouter/issues/200), [#1339](https://github.com/JDeun/SchemaRouter/issues/1339), [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), [#1450](https://github.com/JDeun/SchemaRouter/issues/1450).
2. State the **single failure** the change will fix, the source/task/permission it can legally inspect, exact existing benchmark duplicate check, baseline/candidate and **same K/schema budget**.
3. Lock data and native gold **before** scoring, distinguish E0 synthetic/compatibility, E1 provider source-verified author-visible DEV and E2 independent external full-agent proof.
4. Run the smallest safe mechanistic test first; if it does not diagnose an actual failure, **stop rather than opening another near-identical research PR**.
5. Promote only if **paired end-to-end task evidence and negative safety/cost gates** pass, with immutable result artifacts and explicit approval. No fake status upgrades, default E5 promotion, retroactive frozen edits or v0.18 tagging.

**Decision summary, 2026-10-16:** Keep the stable typed, policy-governed execution architecture; consolidate research and external code already written; direct new engineering toward **a single testable candidate → typed fit → calibrated disposition → completed agent task pipeline**. The architecture is relatively mature; **generalizable task success and reliable unsupported handling are not**.

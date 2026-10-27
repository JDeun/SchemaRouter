# Original-paper Algorithm 1 continuation — P2 source-typed ToolCall E0

### 2026-10-27 A5 Crossref native E1 — curated scalar fields and actual ToolCall wiring

- The built-in Crossref REST `get_work` method previously returned only an
  opaque `message` object and had no closed required DOI input envelope. The
  original G5/P2 graph therefore refused to recognize it as a typed
  host-approved source root. Its curated *existing* response has now been
  declared with nested scalar `message.DOI` and `message.publisher` fields,
  an identifier annotation and an exact closed `doi` input contract. The
  generic executor already supports nested paths and field projection; no
  new graph/planner/executor heuristic was added.
- The opt-in `inspect_crossref_paper_source` produces the **curated local
  declaration fingerprint** without contacting the provider; separate
  `register_reviewed_crossref_paper_source` requires the host-pinned
  fingerprint and official base URL, then composes the existing host semantic
  attestation, HTTP/JSON native invoker and bound tool registration. It does
  not prove the current remote schema, verify Crossref license terms, grant
  execution automatically or widen default provider permissions.
- The deterministic `research_paper_crossref_native_e1` runner executes
  actual original Understand/P2 → A5 agent ToolCall → host DOI binding →
  native Crossref GET, and compares returned DOI against the host DOI.
  Model-forged DOI never reaches the native invoker. A source-specific
  response guard rejects malformed response, wrong DOI, null/ill-typed
  publisher, unexpected status or untrusted host DOI; selected native output
  is only DOI/publisher. Scoped MockTransport regressions and a manual-only
  keyless CI run are separate from independent E2 evidence.
- The research scope remains E1 wiring and host-only receipts; real public
  Crossref and independent E2 still require separate verification. The
  optional live request with a previously printed local manifest digest
  `a8b5ad8a494a6580e49c1bd0db82bc566a72d3f188620ebc99d90a21f5ace296`
  and `10.1038/nature12373` could not resolve `api.crossref.org` under either
  normal or separately approved read-only network execution; the host-only
  HTTP mock integration succeeded, but remote data has **not** been observed
  here. [Design](paper-a5-crossref-native-e1-design.md)
  · [plan](paper-a5-crossref-native-e1-plan.md).

### 2026-10-27 A5 COD OPTIMADE native live E1 — reviewed source registration and real-invoker wiring

- Prior E1 heterogeneous tests proved actual adapter *compilation* and native
  executor dispatch, but provider output was simulated. The separate keyless
  public matrix used live providers only with **host-selected** calls. A new
  opt-in `register_reviewed_optimade_paper_source` SDK entrypoint now wires
  **actual remote discovery → a prior host-pinned unreviewed fingerprint →
  original `review_optimade_paper_tool` → the unchanged discovered native
  invoker published in `SchemaRouter`**. It does not replace existing tools,
  invent fields, bypass reviewed owner license labels, or create a second
  executor. The default egress policy rejects internal destinations.
- Independent review found that legitimate OPTIMADE fields may declare
  `type=[string,null]` plus `x-optimade-type`, which original P2 correctly
  rejects as an unconditional scalar. An **explicit host-reviewed runtime
  non-null string refinement** now accepts only pinned source `string` or
  `string|null`, mirrors that refinement in the reviewed endpoint response
  schema, records the original nullable shape and **rejects null at
  execution**. This is a conditional runtime constraint, not source-wide
  non-null evidence. GET formula must exactly match its host search value.
- `scripts/research_paper_optimade_live_e1.py` has separate `probe` and
  fingerprint-pinned `run` commands. Its deterministic example first executes
  a **distinct host-selected OPTIMADE filter** for one source-reported record
  ID. It then executes the existing original P2/Understand → scoped A5 agent
  ToolCall → **host-bound source ID** → registered native OPTIMADE `get`
  route. The scripted agent deliberately forges an ID: the mock transport
  confirms the real invoker receives only the host-validated record ID.
  Remote ID and formula mismatches fail, with no fallback data.
- Dedicated CI runs a live-shaped `httpx.MockTransport` matrix, guarded schema
  publication cases, the original OPTIMADE contract tests and native A5
  heterogeneous regressions. Separately, the CI workflow offers a **manual**
  public keyless COD `probe` and a `run` requiring its independently approved
  fingerprint; neither is run automatically on pull requests.
- Local simulated native integration passes; **real-provider A5 evidence is
  currently unverified**. The attempted public COD probe failed because this
  executor cannot resolve `www.crystallography.net`, including a permitted
  escalated read-only attempt. No E2 inference, commercial license proof,
  autonomous model planning or release permission is claimed. Keep #1346/
  #1477 externally blocked and #1356 on HARD HOLD. [Design](paper-a5-optimade-live-e1-design.md)
  · [plan](paper-a5-optimade-live-e1-plan.md).

### 2026-10-27 A5 heterogeneous E1 — one G5/native catalog across three adapter protocols

- Following opt-in native direct Draft #1760, the new bounded
  `run_paper_heterogeneous_native_e1` composes **one original-paper
  `Understand` → P2 direct proof → original A5 agent ToolCall → registered
  `SchemaRouter.execute` per approved scenario**, across a **single**
  principal-scoped catalog. Real OpenAPI, MCP and OPTIMADE *adapter compilers*
  populate one shared native registry. This is a sequential set of independent
  direct source choices, **not** a model-planned cross-source synthesis,
  multi-hop derivation or an independent E2 reasoning evaluation.
- The entire trusted scenario manifest (up to five unique, source-approved,
  read-only routes) is proven with the original G5/P2 compiler before the
  first model generation or provider I/O. Unreviewed license/source identity,
  hidden or duplicate routes, incomplete or ill-typed host roots and invalid
  model/agent interfaces abort the **whole matrix with zero native calls**.
  Model-forged input values never reach any invoker; only reviewed, explicitly
  host-supplied scalar arguments can be materialized by the existing binder.
- The shared concept catalog, intent registry, native graph, source contracts,
  root approvals, consumer set and **each case's native invoker identity,
  schema fingerprint and binding generation** are now **pinned for the whole
  matrix**, not
  only independently within each source call. An independently RED-then-GREEN
  regression showed a mutated graph *between* otherwise valid calls used to
  be accepted as the next direct call's fresh snapshot. A later unbound
  invoker previously allowed the first two sources to run, and a second
  invoker could be rebound between calls without a source-version change;
  both are now rejected. A third adversarial regression proved that an
  availability predicate **during preflight** could rebind an as-yet-unpinned
  later invoker; the matrix now captures **all** registered tool bindings in
  a callback-free first pass, then starts the original P2 readiness proofs.
  Further RED-then-GREEN cases caught missing or
  wrong-arity model/agent interfaces in a *later* scenario triggering earlier
  native requests, and a compatible **different model-selected no-input
  source** executing before the matrix's post-execution route check. The
  existing E1 direct bridge now accepts an optional **expected route** and
  refuses a nonmanifest selection **before agent/native execution**;
  existing unpinned single-call E1 behavior is unchanged. If a later
  provider raises, no successful matrix receipt is produced and no subsequent
  provider runs. Earlier completed read-only requests cannot be rolled back.
- Successful host-only receipts report the **exact registered source types**
  and a derived `heterogeneous_sources` boolean; a valid single-source call
  does **not** claim heterogeneous coverage merely because it used the
  matrix API. The actual three-adapter fixture positively establishes its
  own three distinct registered source types.
- Integration tests use **locally scripted/native simulated provider outputs**
  but compile all three genuine protocol descriptors and actually dispatch
  through their registered bound native invokers. Separate keyless **public
  live E1** probing through the preexisting **host-selected** native matrix
  succeeded on Crossref REST, COD OPTIMADE and DeepWiki MCP:
  `registered_access_modes=[http_json,mcp,optimade]`, three native tool
  executions, four task endpoint invocations and all three source-specific
  probes passed (~16 s). **That live result does not establish live A5
  model-selected ToolCall dispatch for all three providers.** Real Crossref
  `message` object, OPTIMADE collection arrays and some MCP responses need
  further source-reviewed identity/scalar-or-structured typed projection
  before a strict P2 field group can legitimately route them. Do not fake
  source identity or flatten arrays into claims of paper correctness.
- New matrix tests: **18 passing** after multiple reproduced red cases; broader
  regression/typing/CI evidence recorded on the stacked Draft PR separately.
  [Design](paper-a5-heterogeneous-native-e1-design.md) ·
  [implementation plan](paper-a5-heterogeneous-native-e1-plan.md).
  This remains opt-in E1 scripted evidence: no independent E2, no product
  default, no publication permission uplift. External #1346/#1477 remain
  blocked, and #1356 stays release **HARD HOLD**.

### 2026-10-27 A5 E1 — source-proved direct agent selection reaches native executor

- A major remaining wire after Draft #1759 was that A5's correctly
  host-bound direct ToolCall could run **only in the frozen synthetic fixture**.
  The new **opt-in async E1 adapter** composes the current principal-scoped
  `Understand(q)` and P2 direct proof, one actual original-agent
  `<tool_call>` selection, the existing A5 host-source argument binder and
  **the original `SchemaRouter.execute` registered invoker**. No second
  executor, fixture fallback, production default or historical benchmark
  change. The one-call execution budget allows only one attempt and reapplies
  the current principal. Its host-only `ToolResult` receipt is **not** a
  model-visible observation, a final answer, source-authenticity attestation
  or an independent E2 result.
- Unready, ambiguous, multiple-route, dependency, missing-input, denied-review
  and unoffered routes produce **zero native I/O**. A model's scalar input
  hints never supply actual invoker values; when a model chooses the right
  offered route but fabricates another ID or extra parameter, only the
  separately supplied/reviewed original P2 host input reaches execution.
  The host-owned route/menu, graph, full declaration set and policy are
  rechecked before and after agent generation and the awaited provider
  call. An independently failing test caught mutable **model-visible tool
  definition** tampering: the agent could change its received name and then
  appear to select an unoffered function. We now pin and recheck the
  detached definitions before using the original offered name. Deep nested
  tool JSON and non-scalar model argument envelopes are also refused.
- The E1 parser rejects duplicate JSON keys and string-wrapped argument
  objects before using the unchanged historical ToolCall parser. A raw
  response naming an unoffered and an offered route together is rejected,
  not silently resolved by JSON's last-key-wins behavior.
- Independent read-only review exposed a **native invoker rebind** gap:
  a host callback could replace a tool's registered execution function
  while retaining the same schema fingerprint. Two regressions reproduced
  it RED (rebind during agent generation and during an awaited before-call
  hook). The bridge now pins the exact original executor identity, binding
  generation and invoker identity; an opt-in task-local witness is
  enforced at the **actual executor lookup**, closing the hook/preflight
  gap without changing default invocation semantics. Both tests are GREEN;
  replacement invokers receive zero calls.
- **Real public E1 execution:** the same new A5 bridge registered Open-Meteo's
  already source-reviewed *noncommercial-only* HTTPS geocoding contract and
  ran one **actual anonymous HTTPS request** after a host-scripted agent
  deliberately chose wrong city parameters. Result was
  `status=success`, `native_invocations=1`, `source_http_attempts=1`,
  `host_bound_tool_calls=1`, `provider_result_contract_matched=true`;
  report redacted original coordinates and response bytes. Separate
  `httpx.MockTransport` integration tests exercise this exact native HTTP
  adapter deterministically, including a 503 source failure that cannot
  become a success receipt. The first restricted-sandbox network attempt
  was interrupted without success evidence; the permitted public run
  succeeded. This is still a **scripted chooser, no inference model**;
  `model_selected_calls=0`, `independent_e2=false`. It does not prove
  provider semantics for Crossref/OPTIMADE/MCP or qualify publisher gold.
- Final post-review checks: **810** original-paper/P2/A5/G5/scoped/native
  tests and **261** historical frozen-agent tests passed; executor hook,
  registry binding and startup suites passed, along with 50 normal executor
  tests. Four offload-thread executor cases hung in this sandbox and were
  explicitly excluded from the 50-case pass (the full suite likewise did
  not finish before timeout). Repository Ruff passed; changed E1 and core
  executor modules Pyright reported **0 errors, 0 warnings** with a
  temporary dependency path. The final post-review public Open-Meteo
  HTTPS read also succeeded with one request; this remains E1 scripted.
- Implementation notes:
  [design](paper-a5-native-direct-e1-design.md),
  [plan](paper-a5-native-direct-e1-plan.md). External original-provider
  E2 #1346/#1477 is still BLOCKED_EXTERNAL and #1356 remains HARD HOLD.

### 2026-10-27 A5 execution gap — approved direct root actually bound at fixed-K5 dispatch (E0)

- **The missing A5 runtime wire is now implemented locally**: previously a
  host-reviewed input reached the `ready` original P2 typed plan, but the
  existing fixed-K5 agent loop executed the agent's independently generated
  argument object. An opt-in scoped callback now materializes **the exact
  approved, original-source direct-root scalar arguments** at the existing
  `FrozenCorpusExecutor.execute` boundary. This preserves the existing parser,
  agent-chosen tool call, fixture executor and all historical experiment
  conditions; it does not create a second ToolCall or executor.
- Eligibility is deliberately narrow: a single `ready`, dependency-free P2
  direct root; source-declared complete closed scalar input envelope; original
  approved G5 host-root set; principal-visible route; explicit host input or
  a positively host-reviewed model proposal. The bounded callback rejects
  graph/source/schema/policy/principal/plan drift before materialization and
  again immediately afterward. No callback occurs for non-tool generations,
  unoffered routes or parallel/multiple tool calls. The original scoped
  boundary continues to reject hidden-route observations.
- Independent read-only review identified two further fail-closed cases,
  both reproduced RED before the fix: an explicitly present but empty host
  input dictionary could bypass a simultaneously configured review gate;
  and a stateful availability callback could mutate owner declarations
  during the *last* proof check. A reviewer-present `requires_arguments`
  receipt now exposes no agent menu, even with `{}` host input, while a
  valid explicit `ready` source input still runs. Every pinned declaration,
  schema and graph manifest is rechecked after the last availability probe.
- **Host assist is separately measured** by the redacted public E0 trace
  `host_bound_tool_calls`; it is *not* evidence that the model generated the
  correct argument. A scoped registered-tool agent regression deliberately
  outputs the **wrong** case ID with an extra unapproved property: with a
  reviewed/explicit source root the preexisting fixture completes, and without
  review it does not. Rejected host review yields **zero agent turns and zero
  tool calls**. Tests also cover no-tool, unknown-route, parallel-call,
  policy and graph mutation branches.
- Fresh broad local paper/P2/G5/scoped-authority regression (including the
  new tests): **777 passed**; separate frozen/historical agent utility
  regressions: **261 passed**. Whole-repository Ruff **passed**. Changed
  execution modules Pyright: **0 errors, 0 warnings**. Exact-head GitHub
  Actions must be reported separately; do not infer CI success from local tests.
  [Design](paper-a5-runtime-host-arguments-e0-design.md) ·
  [implementation plan](paper-a5-runtime-host-arguments-e0-plan.md).
- This validates **synthetic E0 fixture dispatch**, not real provider execution
  through the original agent, end-to-end independent E2 reasoning, accurate
  unhinted multilingual ranking, or default release authority. Public live E1
  remains at 0/9 exact top-1; #1346/#1477 external and #1356 HARD HOLD remain.

### 2026-10-27 A5/A9 gap closure — model parameter suggestions with explicit host review (E0)

- The opt-in original-paper `Understand(q)` returns bounded *untrusted*
  `parameter_hints`, but only separately supplied source-validated host arguments
  reached the existing typed planner. A new opt-in host **review boundary**
  connects these without granting authority to model output. A suggested value
  is considered only if the already-compiled P2 proof has an incomplete
  source-authored, explicitly approved scalar root, all exact required
  parameters are present, JSON Schema validates the primitive values, and
  the root belongs to the current captured principal-visible scope.
- Before the host callback sees any value, the publicly constructible plan is
  independently reconstructed with the **original** G5/direct compiler to
  avoid letting a forged plan become a trusted review proposal. The callback
  receives only a detached proposal (source route/fingerprints, exact named
  values) and must return the literal Boolean `True`. It is *not* called
  for unknown routes, missing, surplus, invalid or model-invented consumer
  values. The decision and model/host/source snapshots are rechecked after
  the callback. Rejected proposals remain deferred with **zero tool I/O**.
  An independent code review found that the legacy A5 fixed-K5 episode still
  offered a missing-input direct route to its agent even after the *new*
  host callback rejected its model proposal. The opt-in episode now sends
  only an empty verified menu for `request_arguments` with a supplied
  reviewer when there are no separately supplied host arguments; the
  no-reviewer and explicit-host-input legacy paths remain unchanged.
  The helper also declines multi-alternative direct receipts rather than
  approving only their first incomplete root. A source-native endpoint-schema
  mutation and positive integer/number/boolean cases remain useful follow-up
  coverage, not independent semantic verification.
- This opt-in helper is wired to the scoped A5 direct-plan/fixed-K5
  episode bridge, the existing A9 1-/2-hop observed DAG runner **and its
  tool-free final-answer wrapper**. A reviewed
  source root travels as `host_source_arguments` through the preexisting
  original typed compiler and registered SchemaRouter executor. No reviewer
  leaves *all existing behavior unchanged*, and separately provided host
  arguments bypass model review. No new graph executor, default ranking,
  automatic approval or production privilege has been added.
- Important status detail: the existing graph compiler can return
  `requires_observation` **even while its first root input is missing**;
  reviewing only `requires_arguments` would leave that real wiring gap
  unresolved. A root's actual `missing_required_arguments` controls review
  eligibility, and the graph cannot execute until the checked host value
  makes that root runnable. The scoped A5 result now reports such a blocked
  graph as `request_arguments` (without changing its source-typed planning
  receipt or flattening it into an agent menu). The synthetic real-registered-tool
  regressions cover success, rejection, typed refusal, G5 origin, mutation,
  and original agent adapter. The complete local paper/native-graph related
  suite after review safety fixes: **678 passed**;
  whole-repository Ruff **passed**; five changed scripts' Pyright
  **0 errors / 0 warnings**. The current change's exact
  GitHub Actions CI is **pending** and the independent E2 gate
  remains open. [Implementation plan](paper-reviewed-model-arguments-e0-plan.md).
- **Historical handoff note (now superseded by the A5 execution section
  above):** this revision still had an A5 direct-plan-to-agent-dispatch gap.
  The new opt-in E0 host-materialization layer closes *that specific gap*;
  independent live-provider E2 remains unimplemented/unverified.

### 2026-10-27 P2/A5 gap closure — trusted direct host-source scalar wiring (E0)

- A previously **unwired** Algorithm 1 branch discarded explicit host-owned
  scalar values when a structured `Understand(q)` named a direct original
  source route. It therefore returned `requires_arguments` even with a valid
  original G5-approved host root. The opt-in direct compiler now forwards
  only separately supplied `host_source_arguments` through the existing
  `_compile_one_route` and live per-call scope validation. The original
  route, registered scalar envelope, current principal, field visibility,
  policy, health, license and fingerprint remain authoritative. Untrusted
  model `parameter_hints` still **never** bind a ToolCall.
- Named graph planning now forwards approved values **only** to a source-
  verified direct route; otherwise it retains the proven producer/consumer
  path and existing host-root checks. The scoped A5 model→plan→fixed5
  episode entrypoints accept the same optional host mapping and reject
  mutations across the asynchronous model and episode boundaries. This is
  an opt-in *non-executing typed receipt*, not an agent-derived parameter
  extraction engine or implicit tool invocation grant.
- New RED→GREEN tests exercise a real registered direct root, model-value
  forgery, closed typed arguments, unknown/non-root input, direct-vs-graph
  selection and mutation during the model callback. Read-only review also
  found a route-probe-time mutation gap: a host callback could replace a
  direct scalar **between** the graph's first direct proof and its second
  argument-bearing proof. A separate failing regression preceded the new
  original-input snapshot guard in the graph compiler, which also covers
  graph-source verification. Fresh full related paper, native G5 and opt-in
  fixed5 agent regression after the review fix: **664 passed**; whole-repo
  Ruff passed and changed-module Pyright reported 0 errors / 0 warnings
  before the additional typed-equivalent input guard. The initial full local
  pytest was interrupted after the mid-run review change and is **not a
  full-suite pass**; exact new GitHub Actions checks are still pending.
  [Implementation plan](paper-direct-host-arguments-wiring-e0-plan.md).
- Remaining major behaviors remain unchanged: source-authored independent
  `Understand(q)`/binding accuracy, qualified >K ranker, default-path
  promotion, genuine external agent E2 and independently approved
  publisher semantics. #1346/#1477 BLOCKED_EXTERNAL, #1356 HARD HOLD;
  Draft #1755 remains unmerged.

### 2026-10-27 B1 E1 — unhinted real-provider multilingual route/field planning baseline

- Extend the preceding real 3-provider registration (Crossref HTTP JSON,
  COD OPTIMADE and remote DeepWiki Streamable HTTP MCP) from **execution of
  host-chosen endpoints** to **unhinted native query retrieval and planning**.
  Use two actual remote contract discoveries (COD OPTIMADE and DeepWiki MCP)
  plus the bundled Crossref provider profile in one shared registry; the
  preceding separate matrix verified real Crossref REST execution, but **this
  selection run does not remotely rediscover Crossref's schema**. No API keys,
  model calls or invocations of selected/wrong routes. The frozen 12-case
  host-labeled suite contains three source-shaped tasks in each of English,
  Korean and Japanese, plus one out-of-scope credential/account mutation
  request per language. DOI and repository identity appear literally as
  user-provided task inputs; no `preferred_tools`, concepts or source
  answer labels are passed to `PlanRequest`.
- **Actual public E1 baseline:** **0/9** positive-score exact endpoint
  Top-1, **5/9** positive-score Top-5 (EN 3/3, KO 1/3, JA 1/3); raw Top-5
  had **7/9** but **two of those hits scored zero** and are not counted as
  positive matches. Native `plan_executable` selected the expected route
  in **0/9** cases, so exact intended output fields were present on the
  correct planned route in **0/9**. The unrelated mutation queries gave
  **3/3 no-positive-score outcomes and 0 actual native plan proposals**;
  this is a small host-authored observation, not a calibrated refusal rate.
- English original-plan mistakes are semantically consequential: a DOI
  journal work lookup selected COD's **reference-by-ID** endpoint; a
  bounded Si/O crystal search selected COD's **structure-by-ID** endpoint;
  public repository wiki structure chose COD's structure endpoint. Their
  plans reported missing `id`, not a fabricated identifier. The regression
  reports **native candidate order, score, planned fields, missing expected
  fields and missing source-required arguments**; it never executes a
  mismatched route.
- Source-shaped [design and observed input audit](public-anonymous-route-selection-e1-design.md),
  [TDD/CI implementation plan](public-anonymous-route-selection-e1-plan.md),
  fixed-case opt-in live script and offline regression suite provide the
  next measured optimization baseline. An initial public discovery attempt
  failed with a sanitized `SchemaSourceError` and did **not** report a
  success; later two-source true remote discovery, bundled Crossref profile
  registration and 12-case native evaluation **succeeded again after review**.
  **248 related regression tests passed**, whole-repository Ruff passed,
  changed-script Pyright reported zero errors/warnings; whole pytest was
  **capped at 75s around 8% (exit 124), not green**. Independent read-only
  review found and corrected misleading three-remote-schema provenance.
  Exact new-head GitHub CI still needs its own qualification; do not inherit
  previous commit's green.
- **E1 source-native retrieval characterization**, not independent
  publisher-judged route gold, an actual inference-model trial, original
  Algorithm 1 end-to-end E2, 500/5000 heterogeneity qualification or
  production release authority. This code **does not change** the default
  planner, source metadata, permissions or ranking. Keep #1346/#1477
  BLOCKED_EXTERNAL, #1356 HARD HOLD and #1755 Draft/unmerged.

### 2026-10-27 B1 E1 — actual keyless REST/OPTIMADE/public remote MCP source-task matrix

- A **single live SchemaRouter registry** discovered and bound three authentic,
  unrelated public sources at once: Crossref REST (`http_json`), COD OPTIMADE
  (`optimade`), and DeepWiki Streamable HTTP (`mcp`). All three host-pinned
  source-described read-only calls executed through the existing native
  `ExecutionPlan`/`ToolCall` and the **same registry version**, with no
  model-derived URLs, API keys or custom executor. This is **three real
  providers / three native executions**, not the previous 1,009-route
  publisher-source-only E0 audit or a claim that 1,009 protected operations
  were run externally.
- Independent public Europe PMC JSON REST was actually contacted as a
  **fourth task-endpoint invocation** using only the DOI verified from the
  Crossref work lookup (`10.1038/nature12373`). Europe PMC reported **one
  matching DOI**, COD's returned structure satisfied original Si/O elements,
  `nelements=2`, source ID and formula checks (**one matching structure**),
  and DeepWiki's real `read_wiki_structure` MCP source-declared `result:
  string` projection returned one valid bounded document outline. The
  separate Europe PMC validation is **not** misrepresented as a fourth
  SchemaRouter-registered source.
- The actual real-network script completed with all three source-shaped
  scenario checks **PASS** on four observed local runs:
  **4.32 s / 5.14 s / 5.00 s / 4.94 s** (last after stricter MCP validation,
  per-response transport byte controls and compressed-response rejection); it also
  performs registration/discovery reads beyond the four counted task calls.
  During RED→GREEN validation the first COD attempt failed safely because
  the required identity `id` was absent from the explicit projection; adding
  the source-declared `id` projection produced the observed real-network
  PASS. Real DeepWiki likewise requires its actual declared `result` string,
  not a fabricated generic MCP text-block output. Offline negative cases
  reject inconsistent DOI, no hit, wrong elemental composition, missing
  structure identity, oversized MCP text, source-error messages masquerading
  as an outline, untrusted output fields and unsafe route selection. Europe
  PMC uses byte-capped streamed HTTP reads; the research-only MCP factory
  caps each HTTP response **before the SDK buffers it**, requests identity
  encoding and fails closed on compressed responses, and disables
  tool-session DELETE teardown. Untrusted SDK exception text is suppressed
  from CLI/CI logs; only an error type and nonzero exit are reported. These
  are bounded **harness-level** defenses, not a core production protocol SLA.
- New [source design](public-anonymous-api-mcp-optimade-e1-design.md),
  [TDD execution plan](public-anonymous-api-mcp-optimade-e1-plan.md),
  [opt-in live script](../../scripts/research_public_heterogeneous_live_e1.py),
  and dedicated PR offline/dispatch-only live workflow
  `research-public-heterogeneous-e1.yml`. Local offline source tests
  **15 passed**; extended original native provider/OPTIMADE/MCP invariants
  **114 passed**. Repository Ruff green; changed-code isolated Python 3.12
  Pyright **0 errors/0 warnings**. Repository-wide pytest again timed out
  under the 110-second local cap at ~8–9% (exit 124); **not full-suite
  green**. Exact new-head CI must be checked separately.
- Evidence = **real anonymous read-only source interoperability E1** for
  fixed, host-authored, per-source scenarios. This is not an independent
  publisher-reviewed semantic gold, shared ontology, multi-turn generated
  agent route accuracy, E2, public service SLA or commercial license grant.
  Preserve #1346/#1477 `BLOCKED_EXTERNAL`, #1356 `HARD HOLD` and Draft #1755
  unmerged; no default routing/release promotion.

### 2026-10-27 B1 E0 — one authentic 1,009-operation four-provider native registry

- Extend the separate original OpenAI 355-operation and GitHub 651-GET
  source audits into **one actual versioned registry**, alongside the two
  original Ollama GETs and one Pirate Weather GET: **four publisher tools,
  1,009 genuine source-native routes**. This is not arithmetic addition of
  two separately observed source receipts. Original OpenAI source includes
  371 GET/POST/DELETE operations; exactly seven literal-query and nine
  non-JSON-only operations remain explicitly excluded, with no adapter
  semantic widening. Preserve path, verb, original operation ID, required
  source path inputs, JSON body requirements and source-declared auth.
- Exercise two whole-provider removal/restore cycles through the unchanged
  native posting/graph journal: **1,009→358→1,009→654→1,009**, comparing
  every state with the *independently derived original-source operation
  manifest* and a fresh full rebuild. Stale lookups are rejected at all
  four changes. Record fresh-build and journal replay wall times and
  process peak RSS as **single-machine observations**, never E2/SLA.
- [Four-publisher genuine-source design](official-four-provider-1009-e0-design.md)
  and [TDD/CI implementation plan](official-four-provider-1009-e0-plan.md).
  New **four-source bundle / native journal / measured-cost / forged journal
  tests: 4 passed in 365.00s**. Existing native posting/graph regressions:
  **133 passed in 5.86s**; repository Ruff green; new module Pyright
  **0 errors/0 warnings**; workflow YAML and diff syntax clean. Local
  repository-wide pytest again timed out at ~8% / 110s (exit 124),
  **not green**. Read-only independent code review found no actionable
  Critical/Important/Minor findings. New exact-head CI is **pending** at
  this checkpoint. Independent offline diagnostic on the local Linux host:
  five full-rebuild wall samples **[20.21, 6.70, 19.86, 16.23, 21.55]s**;
  four corresponding journal refresh samples **[0.0017, 12.92, 0.0018,
  6.03]s** (cheap provider removals; heavier full-provider restorations).
  Peak *whole-process* Linux RSS reported **1,032,076 KiB**. These small,
  sequential, environment-dependent samples do **not** establish p95/p99,
  production memory isolation or an E2 speedup. Keep #1755 Draft/unmerged, #1346/#1477
  BLOCKED_EXTERNAL, #1356 HARD HOLD. No owner-reviewed semantics/permission,
  genuine independently sourced 5,000-route oracle, agent E2 or promotion.

### 2026-10-27 B1 E0 — genuine GitHub 651 GET publisher source and whole-provider churn

- Read the official MIT-licensed `github/rest-api-description` original
  `api.github.com.2022-11-28.json` at immutable revision `755ee33b`:
  **823 source paths, 651 GET operations**. The complete unchanged
  **13,429,427-byte** upstream JSON and LICENSE.md are Git-blob/SHA-256
  verified; a deterministic gzip fixture is container-byte pinned before
  decompressing. The untouched existing native OpenAPI complexity guard
  handles each exact original GET/component closure, no whole-file bypass.
- Consolidate 651 real GET operations into **one original publisher tool**
  with 651 distinct original operation IDs; register alongside separate
  byte-pinned Ollama (2) and Pirate Weather (1) provider tools in the
  existing registry (**654 actual source-native routes**). Remove and
  restore the GitHub provider atomically: **654→3→654**, two stale lookup
  rejections; canonical source-owned journal = full rebuild = original
  operation manifest at each registry version. Distinct from the
  preceding 358-route OpenAI/Ollama/Pirate all-method audit; **do not sum
  separate catalog receipts as one 1,012-route experiment**.
- [Genuine provider design/source pins](official-github-rest-651-e0-design.md)
  and [TDD/CI plan](official-github-rest-651-e0-plan.md).
  **10 source/journal tests passed locally in 195.35s**, and the expanded
  **187 related provider/index/graph tests passed in 288.28s**. Changed-code
  Pyright 0 errors/0 warnings and repository Ruff green. Repository-wide
  local pytest reached ~8% and timed out at the 110-second cap (exit 124),
  **not claimed green**; new exact-head GitHub CI remains pending.
  No host-approved source semantics/license permissions, verified foreign
  MCP/OPTIMADE input, executable invoker, independent gold/E2 or default
  promotion. B1 full 500/5000 heterogeneous acceptance remains unchecked,
  A6/A7/A10 and #1346/#1477 external evidence still blocked, #1356 HARD
  HOLD, #1755 Draft/unmerged.

### 2026-10-27 B1 E0 — 355 real OpenAI HTTP operations, native journal churn

- Extended the pinned original OpenAI `8243cc8f` source beyond 161 GETs
  to the **full 371-operation GET/POST/DELETE inventory**, with exactly
  bounded original `(path, method)` projections. **Seven** literal
  query-bearing operations and **nine** non-JSON-only request-body POSTs
  cannot be faithfully represented by the existing native adapter; they
  are deliberately excluded, **not silently rewritten or offered**.
- Original-source convertible subset: **355** actual OpenAI HTTP operations
  (**161 GET, 142 POST, 52 DELETE**). Combined with exact Ollama and Pirate
  Weather publisher sources: **358** registered source-native operations in
  one canonical registry. Preserve each verb, original operationId, path
  inputs, required JSON body and declared auth; write methods are never
  marked read-only. An actual original `DELETE /models/{model}` removal and
  restoration proves **358→357→358** source-owned journal parity with full
  rebuild and independent original manifest, and stale lookup rejection.
- A RED→GREEN upstream parser regression now retains bare YAML ISO-date
  examples as strings instead of PyYAML `datetime.date` objects, without
  rewriting the byte-pinned provider source or modifying the default global
  YAML loader. The prior GET audit remains separately tested.
- [Design/ruling](official-provider-all-http-e0-design.md) and
  [implementation/test plan](official-provider-all-http-e0-plan.md);
  dedicated offline Python 3.12 provider-source workflow expanded.
  **177 related real provider/index/graph tests passed** on local Python 3.12,
  repository Ruff green; changed-script Pyright 0 errors (2 local YAML source
  resolution warnings). Repository-wide local pytest reached ~8% and
  **timed out at the 110-second cap (exit 124); not claimed green**.
  **Exact OpenAI code HEAD `ab125b3591437d685bce032e318d0a86d098b468`
  qualified 36/36 GitHub PR workflows.** Main Python 3.12 CI run
  `40418913072`: **6663 passed, 3 skipped in 1739.50s, coverage 85.12%**.
  That prior green must not be inherited by the new GitHub source code HEAD.
  No provider execution, independent source-owned semantic gold, model/agent
  E2 or release/default promotion. A6/A7/A10 and B1 full acceptance remain
  unchecked; #1346/#1477 BLOCKED_EXTERNAL, #1356 HARD HOLD, #1755 Draft.

### 2026-10-26 B1 E0 — third genuine provider, 161 source-preserved native GET routes

- A third original published source, the official OpenAI OpenAPI document at
  commit `8243cc8f`, adds **237 actual source paths / 371 HTTP operations / 163
  GET operations**. Only **161 GET paths** are supported by the existing
  native converter; two query-bearing source paths remain explicitly
  unsupported, **not silently rewritten**.
- The full **4,210,167-byte original** and its MIT notice are checked against
  original upstream Git blob and SHA-256. The deterministic repository gzip
  container is separately pinned (486,142 bytes), decompressed only after
  verifying its hash. Each GET projection follows only original local
  component references and passes the **existing unmodified OpenAPI
  complexity guard**, with no new converter/index/executor. Direct whole-doc
  conversion correctly rejects >50,000 nodes; the guard is not weakened.
- Actual native registry/graph: 161 read-only GET endpoints, including **116
  routes with preserved mandatory path inputs** and **161 with source-declared
  authentication**. Together with the two prior official sources, one native
  registry now contains **164 genuine three-provider routes**, but **zero** approved semantic postings, typed
  cross-provider joins or execution grants. The provenance/negative tests
  and offline dedicated Python 3.12 PR workflow are expanded.
- [Source design, exact pins and limitations](official-provider-openai-bounded-get-e0.md).
  This is E0 original publisher-*source* scale beyond the earlier 3-route
  Ollama/Pirate sample, **not** independent field/permission/gold proof,
  500/5000 heterogeneous E2, actual model/agent utility or release
  qualification. #1346/#1477 `BLOCKED_EXTERNAL`, #1356 `HARD HOLD` and
  Draft #1755 unmerged; latest HEAD CI must be qualified separately.

### 2026-10-26 B1 E0 — authentic two-provider journal removal/restoration

- The existing genuine, byte-pinned Ollama/Pirate Weather source test now
  checks **three original native catalog versions (3→2→3 routes)**. Each
  provider removal/restoration makes the preceding G5 lookup fail closed;
  the source-owned in-memory posting/G5 journal refresh must exactly match
  an independent full rebuild and actual original registered endpoint
  manifest. The unchanged source definitions produce no invented semantic
  postings, typed cross-provider joins or execution permission.
- Added a RED→GREEN source-lifecycle regression and a no-op-journal
  corruption regression; both run in the dedicated offline Python 3.12
  provider CI. This remains **E0 structural source evidence only**, not
  owner-reviewed semantic field gold, 500/5000 genuine provider routes,
  remote execution or E2. Full B1, A6–A10, #1346/#1477 remain open;
  #1356 `HARD HOLD`, #1755 Draft/unmerged. Exact new-head CI must
  separately qualify this code and these receipt claims.

### 2026-10-26 B1 E0 — two genuine provider-native original OpenAPI documents

- Extended the genuine upstream Ollama OpenAPI pin with an **unmodified**
  Pirate Weather original OpenAPI 3.1 plus Apache 2.0 license, exact upstream
  commit `6c3b4b0d9890d19b2199f8315488e8669c6951c3`, original source
  Git blob `1b417160dc385c8d10897d88ec37fa4793d50816`, original
  license Git blob `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`.
- New [two-provider provenance and negative fixtures](official-provider-pirate-weather-e0.md)
  use the existing OpenAPI compiler and a single canonical 3-endpoint
  native index/graph. Required source `api_key` and location input cannot be
  silently discarded; no credentials are provided or invoked. Neither the
  upstream license declaration nor public OpenAPI metadata grants execution
  authority or verified semantic joins.
- Exact native bytes and separate license bytes must match SHA-256 and Git
  blob SHA; byte mutation/length tampering fail closed before any adapter
  registration. The existing dedicated Python 3.12 offline native-provider
  source CI is extended for both sources.
- Real *provider-authored schema* **E0 source-only**, NOT independent
  provider-permission review, publisher-authored query/gold, or model/agent
  E2. #1346/#1477 `BLOCKED_EXTERNAL`, #1356 `HARD HOLD`.
  Latest new-head CI results must be checked separately.

### 2026-10-26 B1 E0 — authentic Ollama provider OpenAPI bytes, not independent gold

- New verified upstream **Ollama** actual published OpenAPI 3.1 source, commit
  `66ab8482e08035a3238dff04a5739c4371c61bfe`, original
  `docs/openapi.yaml` **87,348 bytes**, Git blob
  `3d0f5db4e71f1cb8331170c4d209902a00dfecc0`, SHA-256
  `e94c8f02969c6807f431b7d0643eb0f8368f1d1baa719a4edaf07989b758f257`.
  Original MIT license from the SAME exact upstream revision is retained,
  with original blob `8e3dc978a7ca8c53f56bbedc5b558116140fc02e`.
- Offline source audit strictly verifies immutable byte sizes, SHA-256 and
  original Git blobs before parsing. Selects **original** documented
  `GET /api/tags` and `GET /api/ps` operations and their response schema
  components, runs the **existing** OpenAPI ToolSpec compiler, and indexes the
  resulting two-route native catalog without inventing host-approved license,
  semantic IDs, policy grants, graph joins or execution permission.
- Separate exact-head 3.12 workflow includes source tamper tests and an
  explicit **E0 source-only, no E2** audit receipt. [Reproducibility,
  license, and limitations](official-provider-ollama-openapi-e0.md).
  **Full exact-head CI is pending at publication; do not inherit prior CI**.
- This is the first pinned genuine publisher-native **source** in this B1
  continuation, NOT 5000 independent provider schemas or publisher-authored
  cases/gold. #1346/#1477 independently evaluated E2 remain blocked,
  #1356 release HARD HOLD, PR #1755 Draft and unmerged.

**2026-10-24 · E0 source-authored diagnostic, not a shipped/default executor.**

### 2026-10-26 B1 E0 — nonempty 1-/2-hop G5 graph source churn

- The preceding 500/5000 mixed-source B1 journal audit had **zero G5 graph
  edges**, despite strong direct field/posting parity. New opt-in
  `scripts/benchmark_native_heterogeneous_graph_churn_e0.py` replaces four
  existing synthetic ToolSpec sources (OpenAPI → MCP → OPTIMADE 2-hop and
  OpenAPI → custom 1-hop). It requires independent original-source typed
  edge witnesses and the exact **3→2→3→1→3 edge transitions** over five real
  registry versions; all four old-index lookups must fail closed.
- Six live principal/hidden-field/denied-route/availability scopes × two
  principals × EN/KO/JA produce **180 1-hop + 180 2-hop** independently
  enumerated path checks per catalog size, with both explicit typed bindings
  verified. Four same-predicate root/middle health flips are also checked.
  Canonical incremental graph/posting refresh must exactly equal full rebuild
  *and* a separate source-only edge oracle, preventing vacuous agreement.
- The nonempty RED test uncovered a real canonical incremental accounting
  defect: an unchanged 2-hop intermediary that consumed and produced typed
  identifiers incorrectly increased `native_root_count` after a root change.
  Fixed by counting only producers with no required inputs. Source edges
  themselves were unaffected. [Design](native-heterogeneous-graph-churn-e0-design.md) ·
  [plan](native-heterogeneous-graph-churn-e0-plan.md).
- Local related scoped source/graph/SQLite-journal regressions **375 passed in
  190.70s**; strengthened nonempty acceptance tests **9 passed in 10.96s**
  after independent review, and both 500/5000 executable CLI audits emitted
  gated counts. Repository Ruff green, changed-module Pyright 0 errors,
  YAML parse and `git diff --check` clean. Full unbounded local suite was not
  rerun; exact published HEAD must pass its own CI before qualification.
- **E0 only**: source graph, host oracle, mixed provider-*like* ToolSpec,
  zero execution/model calls and no independent provider/publisher gold;
  B1 E2, #1346/#1477 remain BLOCKED_EXTERNAL, #1356 HARD HOLD and
  Draft #1755 unmerged. Exact-head CI must be verified after publication.

### 2026-10-26 B1 E0 — mixed-source versioned journal churn and live-scope parity

- New opt-in `scripts/benchmark_native_heterogeneous_churn_e0.py` reuses
  the existing 500/5000 registered original ToolSpec mixed-source fixture.
  It exercises license revocation and restoration across **three real
  registry versions**; the two old-index reads must fail closed, and each
  source-owned in-memory journal delta must equal a complete graph/posting
  rebuild and independent exhaustive original-source oracle.
- At each version, all four policy/scope/health scenarios, both a reader and
  an unprivileged principal, four distinct source types and EN/KO/JA aliases
  receive **288 indexed/oracle/rebuild comparisons** per catalog size. A
  mutable health set changes behind one fixed predicate callable with no
  source version update; source-exhaustive oracle and both current indexes
  must immediately agree with **independent expected scenario outcomes**.
  No model, transport, extra executor or default
  routing change is introduced.
- Focused RED→GREEN **16 tests passed in 162.05s** covering separate 500/5000
  audits, invalid size/sample controls, forged-oracle and stale-journal
  rejection, common-mode anonymous/hidden-field leak rejection and an
  unrelated-route manifest-corruption regression. Added
  both catalog sizes to the existing opt-in direct-parity
  PR workflow matrix and bounded E0 aggregate evidence artifact.
  Existing related retrieval/index/graph regressions **185 passed**; repository
  Ruff and changed-module Pyright **0 errors**, workflow YAML valid. The
  unbounded local suite is **not green**: a capped run reached 95s at ~8%.
  [Design](native-heterogeneous-churn-e0-design.md) ·
  [plan](native-heterogeneous-churn-e0-plan.md).
- **Prior B1 direct-churn HEAD CI qualified:** commit `2828af8ea9e6f9d7b33fcc708e94d204f01f899e`
  passed **35/35 workflows**, including [dedicated 500/5000 matrix
  run](https://github.com/JDeun/SchemaRouter/actions/runs/40307241489);
  [main CI](https://github.com/JDeun/SchemaRouter/actions/runs/40307240978)
  reported Python 3.12 **6600 passed, 3 skipped; 85.02% coverage**. The
  *following nonempty graph-edge churn patch is separately gated on its own
  exact HEAD*. These B1 E0 audits still do not prove live provider churn,
  externally verified licenses/permissions, production schema bytes or
  independently labeled E2. B1 remains unchecked,
  #1346/#1477 remain BLOCKED_EXTERNAL, #1356 HARD HOLD; Draft #1755 stays open.

### 2026-10-26 B1 E0 — heterogeneous 500/5000 original-source indexed parity extension

- New opt-in `scripts/benchmark_native_heterogeneous_parity_e0.py` exercises
  original registered native `ToolSpec` catalogs with four OpenAPI/MCP/
  OPTIMADE/custom-like source types, typed wrong-license/shape decoys,
  principal authorization, hidden output, availability and post-registration
  source schema mutation. No duplicate routing/agent/executor or provider I/O.
- **Observed local TDD RED→GREEN**: 13 tests; 177 related index/graph/A9
  regressions passed. Both 500/5000 developer-synthetic catalogs separately
  passed **96 exact original-source oracle parity checks** over EN/KO/JA
  aliases and four scenarios. Indexed wall p50/p95/p99 for 5000 routes:
  **1.313/2.315/2.475ms**, Python 3.12.14 Linux; not a general SLA.
- Reuses the existing `indexed-concept-direct-parity-e0.yml` matrix
  (500/5000), with explicit E0/independent-gold gates and a second
  bounded artifact; no default or release promotion. [Design](native-heterogeneous-5000-e0-design.md)
  and [plan](native-heterogeneous-5000-e0-plan.md). Full B1 heterogeneous
  real-provider/permissions/churn/oracle test remains **unchecked**; this
  source-authored synthetic test does not satisfy #1346/#1477 E2.
- Latest verified prior HEAD was `bfedf637` 35/35 PR workflows. The new
  code/docs/workflow publication must receive its **own exact-HEAD CI**.
  #1560 open; Draft #1755 unmerged; #1356 HARD HOLD.

### 2026-10-26 A9 E0 — actual observed graph → one tool-free answer generation

- Built research-only `scripts/research_paper_scoped_answered_graph_a9_e0.py`,
  composing the **existing** scoped Understand → registered 1-/2-hop G5
  `SchemaRouter.execute` observation with **one** pre-existing agent
  `generate(messages, [])` call. There are **zero extra tool grants, no new
  invoker, and no default agent loop**. The agent receives the exact captured
  user query and **only the last tool's scalar, source-projected output** in
  bounded JSON; intermediate producer IDs, host root arguments, graph
  fingerprints, principal identities and other routes are never prompted.
- Fail closed on incomplete/refused original graph, absent owner-approved root
  arguments, current source drift, invalid/nonfinite/oversized projected
  observations, leaked fields, context overflow, malformed/duplicate-key
  answer JSON, tool-call markup, nonzero tool-schema token accounting and
  tampered metering. Response is an **unverified answer proposal** with all
  E2/source/provider/executable authority flags explicitly false.
- **RED→GREEN local**: 18 new focused tests (1-/2-hop real registered
  execution, zero-tool agent callback, no upstream IDs, unknown/denied/no
  host input, revocation during finalizer, adversarial observation, malformed
  completion and token/byte bounds); expanded 16-file A9/typed/agent/ABI
  regressions **258 passed**, Ruff green and changed module Pyright 0 errors.
  Local unbounded full pytest did **not** complete: the previously known
  `test_capability_removal.py::test_remove_tool_sync_wrapper` stalled around
  collection progress 12%; an independent isolated reproduction hit a 20s
  timeout, so do not claim the full *local* suite green.
- **A9 answer CODE HEAD qualified on 2026-10-26:** commit
  `74b9adbbdc2abcc53febdf5be9896d5a04137836`, tree
  `ae961192d3b30cf2ed0d3771db863a9d9907785f`, passed **35/35 returned
  PR workflow runs** including the dedicated original-paper A9 test, public
  ABI, Python 3.10/3.11/3.13/3.14, Qwen CPU DEV and package checks.
  [Main CI #7187](https://github.com/JDeun/SchemaRouter/actions/runs/40278095040)
  Python 3.12 reported **6500 passed, 3 skipped in 1091.42s**, core coverage
  **85.02%** against 84% required. This is exact-head *engineering E0*
  qualification, **not E2 or independent semantic answer accuracy**.
  The ensuing docs-only HEAD is a separate commit and must qualify independently.
- Design [A9 answered graph](paper-scoped-answered-graph-a9-e0-design.md),
  execution [A9 answer plan](paper-scoped-answered-graph-a9-e0-plan.md).
  Original independent A9 source semantics, agent answer accuracy, publisher
  provenance and #1346/#1477 independent E2 **remain unchecked**. Keep Draft
  #1755 unmerged and #1356 HARD HOLD.

### 2026-10-26 A9 named 1/2-hop observed execution (local E0 implementation)

- Added opt-in `observe_and_execute_paper_understood_graph` in the existing
  `paper_consumer_execution.py` module. The model only names the target;
  owner-approved original G5 typed paths still determine root, intermediate,
  target, required input names, output projections, policy and scope. No
  model `parameter_hints` become tool arguments.
- The named compiler accepts explicitly supplied scalar values **only** for
  its one approved G5 host root; absent inputs refuse before invocation. A
  pinned current complete named-DAG G5 proof is checked before/after every
  real `SchemaRouter.execute` call and observation binding. The existing
  `_materialize_original_observed_edge` validator checks each projected
  identifier and consumer schema. Empty string identifiers are additionally
  refused for dependent reads. Each original read-only call uses its own
  single-call/single-attempt/single-remote-attempt budget; no new executor,
  autonomous agent loop, parallel fan-out or partial result receipt.
- The public explicit E0 result remains
  `provider_provenance_verified=False`, `executable_authority=False`,
  `independent_e2=False`. **No actual model/agent-triggered automatic graph
  execution or provider/source-independent semantic E2 is claimed.** A9
  broader checkbox remains open, including independent semantic/provider
  qualification and actual agent scheduling. Preserve #1346/#1477 BLOCKED,
  #1356 release HARD HOLD and Draft #1755 unmerged.
- Local RED before implementation: **19 failures** (missing callable/host
  input parameter). GREEN after implementation: **27 A9 tests** and expanded
  A9/typed-plan/G5 2-hop/host-root/observed-consumer/real scoped-agent
  regressions **193 passed**, repo Ruff green, changed
  source-module Pyright 0 errors. Added an explicit CI step to the existing
  original-paper typed-plan workflow. Exact remote-head CI will be recorded
  only after publishing. [A9 design](paper-understood-observed-graph-a9-e0-design.md),
  [A9 plan](paper-understood-observed-graph-a9-e0-plan.md).

**A9 first remote-head failure and next scope (2026-10-26):** Published
commit `1a20df99c7e32a3ab5f7581e4150acb8a42fe081` had **29/35 workflows
successful, 6 failed**. Root-cause analysis of [CI #7184](https://github.com/JDeun/SchemaRouter/actions/runs/40270899439)
and the other five failed job logs confirmed **one shared public API ABI
expectation failure**: the two deliberate public A9 symbols were absent
from `tests/test_public_api.py`'s frozen `__all__` set. This was reproduced
locally RED and corrected; do **not** inherit old green from A8 or falsely
claim A9 full CI green at this checkpoint. A further explicit scoped
`Understand(q)` → graph bridge in
`scripts/research_paper_scoped_observed_graph_a9_e0.py` reuses the one-shot
captured-model callback, validates every named DAG route against the same
captured principal-visible inventory, defers missing host inputs before
I/O and runs the real A9 source-checked executor. **7 new RED→GREEN
end-to-end tests** cover 1-/2-hop, no-menu/unknown-tool, forged model
inputs, source mutation and root-argument deferral. Expanded 15-file
regressions **283 passed**, Ruff green, changed-source Pyright 0 errors.
This is opt-in local code only, **not** default fixed5 agent scheduling,
publisher provenance, independent E2 or release qualification. Next exact
published HEAD must rerun and pass protected CI before engineering claim.

**A9 E0 exact qualified code HEAD (2026-10-26):** Draft commit
`5683426c7ea6adf41d53ec699741e042e2e2db41`, Git tree
`5b344964eea83d1f08e7abac634e025bbfe43f09`, passed **35/35 returned
PR workflows**. [Main CI #7185](https://github.com/JDeun/SchemaRouter/actions/runs/40273198187)
Linux Python 3.12 **6482 passed, 3 skipped in 798.88s**, total coverage
**85.02%**. Dedicated original-paper typed-plan A9 workflow, original
native G5, full public ABI, Windows, package/runtime and Qwen E5 CPU DEV
workflows all passed on **that same code HEAD**. Prior `1a20df99` was
**red** due its omitted frozen public ABI expectation; do not conflate.
This evidence qualifies the source-safe *local E0* named G5 observation and
one-shot scoped model→executor wiring **only**. The broader A9 checkbox
remains intentionally **unchecked** until actual autonomous-agent answer
scheduling, independently reviewed source semantics/provider provenance and
E2 task evidence. #1346/#1477 remain BLOCKED_EXTERNAL, B1 full catalog
500/5000 and A10 no-fit calibration open, #1356 release **HARD HOLD**.
CodeQL not triggered/claimed on this stacked non-main Draft. Any later
documentation-only HEAD must run its own 35-check qualification.

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
- Twelve synthetic adversarial tests cover >K/denied source,
  actual query, named-before-K, >32 refusal, forged choices, unknown
  source/tool and owner/policy/view mutation. **The exact new A8 code HEAD**
  `9ea21e4c05e26c2b6a344576c20f5d7f32ac887e`, Git tree
  `f411198169790a2f5696a62a6897b5c9b47bfea7` matches the reviewed
  local implementation and passed **29/29 returned PR workflows**.
  [Main CI #7182](https://github.com/JDeun/SchemaRouter/actions/runs/40266138929)
  Linux Python 3.12 **6448 passed, 3 skipped in 1057.93s**, **85.00%
  coverage**. Local 190 relevant tests, repo Ruff and changed-script
  Pyright also passed; no independent CodeQL claim for this stacked
  Draft. Any later docs-only head needs its own exact-head checks. See
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
- **A6 E0 per-case witness continuation (2026-10-26):** optional
  `inspect_witness_pinned_native_cohort` and paired private CLI arguments
  `--native-authority-witnesses` / `--gold-reference-witnesses` now verify
  separate *original opaque bytes for each individual case* against that
  case's pinned `native_authority_sha256` / `gold_reference_sha256`. Both
  collections must exactly match the source-pinned EN/KO/JA × five-label
  cohort. They are bounded, fail closed on duplicate/foreign/missing or
  cross-paired evidence, and export no source/gold/route/credential bytes.
  The existing four-/five-file entrypoints remain unchanged; native-intake
  CI explicitly checks the seven-stream path. **This is still E0 structural
  integrity, not independent reviewer, publisher authority or license proof.**
  [Witness design](paper-a6-per-case-witness-intake-design.md),
  [witness plan](paper-a6-per-case-witness-intake-plan.md).
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
- **A7 order-crossover engineering continuation (2026-10-26):** The existing
  `run_paper_paired_agent_e0` now has a strict, default-compatible
  `execution_order` and runs the original fixed5 baseline/paper branches
  in the requested real order. New opt-in
  `run_paper_counterbalanced_agent_e0` obtains two fresh same-type Understand
  callbacks and four distinct, host-config-matched agent instances, then
  executes *both* baseline→paper and paper→baseline trials against the
  original source-checked A5/A7 runner. Owner/task/source mutation or any
  mismatched agent/model factory refuses without a partial crossover record.
  A separate regression-proven guard **pins owner declarations and original
  task digest before the model factories themselves run**, preventing a
  factory from silently rewriting publisher gold or source semantics before
  either original pair could snapshot them.
  Only the two existing sanitized per-condition receipts and explicit order
  labels are returned; no gold, raw query, route identities or provider
  claims. The original-paper workflow explicitly tests the order and negative
  cases. **Crossover is E0 source-authored engineering only**: two ordered
  rehearsals do not eliminate provider caches, authenticate the model or
  replace pre-registered randomized multicase independent EN/KO/JA E2.
  [Crossover design](paper-a7-counterbalanced-pairs-e0-design.md),
  [crossover plan](paper-a7-counterbalanced-pairs-e0-plan.md).
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
`9ea21e4c05e26c2b6a344576c20f5d7f32ac887e`, 29/29 PR workflows
successful, Linux Python 3.12 **6448 passed / 3 skipped**, 85.00% coverage;
the preceding A7 paired code head `6f35b57c` separately qualified at 6436
passed and its docs-only HEAD `f8b7ff5c` also passed 29/29;
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
- [ ] **A6** Add independently reviewed, source-snapshot-pinned EN/KO/JA supported/unsupported/ambiguous fixtures, with explicit labels, provenance, license and permission conditions. **Seven-stream source + per-case native-authority/gold witness-byte intake is implemented E0**, with original four-/five-file compatibility and CI. Real source-owner signatures, verified semantics/permissions/license, independent reviewer and original publisher-authored fixtures have not been supplied; independent qualification remains BLOCKED_EXTERNAL. Do not fabricate publisher gold.
- [ ] **A7** Run paired same-model/same-agent evaluation; report false refusal, false accept, deferred/unknown, tool attempts, wall time and actual input/output tokens separately from schema bytes; repeat on CI Linux Python 3.12. **E0 counterbalanced both-order same-agent runner now exists**, retaining original measured token/schema byte separation, source and role guards. Independent model/provider identity, randomized cohort E2, original gold and robust latency bounds remain external; do not claim E2 without them.
- [ ] **A8** Independently justified Top-K5 ranking for eligible alternatives and >K overflow, without weakening policy-before-K, deterministic tie handling or rewriting frozen #432 scores.
- [ ] **A9** Source-attested argument semantics and separately authorized observed 1/2-hop dependency execution through the **existing** agent/executor, with fail-closed mutation, typed binding, provenance and budget tests. **Local A9 E0 source-checked executor slice exists** (`observe_and_execute_paper_understood_graph`, registered real tool bindings and guards); actual model/agent-triggered graph scheduling, independent source semantics/provenance and E2 remain open. Do not create a second executor.
- [ ] **A10** Calibrate no-fit on independently labeled supported and unsupported requests. A `no_proven_hit` is not proof of globally nonexistent capability. **E0 evaluation mechanism implemented (2026-10-26):** `scripts/research_paper_no_fit_calibration_a10_e0.py` now ingests the existing five *exact source-pinned* native intake streams plus complete observed Algorithm 1 statuses. It reports EN/KO/JA supported false refusal, unsupported false accept, deferred and source-unknown counts with separate denominators and host-predeclared minimum/maximum diagnostics; no case IDs, gold or source contents are exported. Synthetic tests and paper CI wiring are present. **Still unchecked:** independent publisher authorship/review/permission, real model outcomes and grounded calibration thresholds are not available; even a perfect synthetic diagnostic cannot qualify E2 or release. Related #1291 remains closed for its prior fix.

  **A7→A10 E0 bridge:** `observation_from_paper_paired_agent_e0` now accepts the existing *actual paired A7 episode* and projects only its coarse planning `decision` plus host-recorded `tool_call_count`. It records ambiguous abstentions as `abstain_unclassified` (not forged `no_proven_hit`), distinguishes absent attempt receipts (`None`) from observed zero, refuses unbounded counters/malformed metering and requires **every case's host dispatch counter** before an E0 `candidate_within_declared_limits` can be non-null. An unsafe unsupported/nonbinary call, post-abstention call or supported offer without dispatch blocks that diagnostic; planning-only acceptance is reported separately. A synthetic paired-run integration regression proves this adapter uses the original fixed-K executor, not a second agent. The independent host remains responsible for joining the correct case IDs and for truly independent gold. **A7 and A10 stay open** for that external evidence.

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

## 2026-10-27 — DeepWiki real-shape MCP scalar result → original P2/A5 E1

- **Missing seam addressed:** previous mixed-provider scripted MCP scenario
  invented a `repoName` output identifier that the real DeepWiki
  `read_wiki_structure` source does **not** declare. The earlier native-only
  live matrix validated the actual `result: string`, but did not wire it
  through original `Understand → P2 direct plan → A5 agent ToolCall`.
- **Original G5 fix:** `NativeSchemaGraphIndex` now accepts a separately
  host-approved source route with a semantically typed scalar, even without
  a declared output identifier. Its graph capability explicitly has **zero
  produced identifiers**, hence no downstream identifier-binding edge.
  This is a direct-P2 option only, not inferred graph composition.
- **Native source wiring:** `src/schemarouter/paper_deepwiki_registration.py`
  implements live MCP `tools/list` probe and a separate **exact unreviewed
  adapter-visible discovery snapshot digest + source URL** review gate
  (not a raw-wire hash or signed source-owner receipt). The approval publishes only the
  original `read_wiki_structure(repoName: string) → result: string` operation
  through `MCPRemoteInvoker` with a narrowed closed input schema; remote
  `readOnlyHint` is never trusted as authority. Existing fields receive
  host-owned semantics `wiki.repository_id` and `wiki.outline`; **no result
  identifier is fabricated**. Source license label remains
  `source-license-unverified-research-only`. An independent read-only review
  found a real-world schema incompatibility: the provider annotates
  `repoName` with a description and marks its result envelope
  `x-fastmcp-wrap-result: true`. Both are source-preserved at inspection;
  only the nonvalidation parameter description is stripped after fingerprint
  approval. Unknown source constraints and annotation drift fail closed.
  Source observation: https://manufact.com/leaderboard/deepwiki (Oct 24, 2026).
- **Original A5 pilot:** `scripts/research_paper_deepwiki_native_e1.py`
  supplies a host-selected bounded repository. A scripted agent intentionally
  submits a different repository, which is not executed. P2 uses one reviewed
  original direct route and the normal principal-scoped native execution.
  Returned source content must match the exact repository heading and have
  at least two numbered pages within the size bound. Scripted E1 proves
  routing/wiring, **not** autonomous model E2 or provider answer quality.
- **Verification:** `tests/test_paper_deepwiki_native_a5_e1.py` includes
  source-shaped asynchronous discovery and native execution, stale source,
  malformed schema, wrong outline and host parameter refusal tests;
  `tests/test_native_graph_host_root.py` proves no scalar-to-identifier
  graph edge. Original-paper plus native regression **612 passed**,
  additional real local MCP HTTP/stdio tests **2 passed** after the
  sandbox's local socket restriction was lifted, Ruff **PASS**, targeted
  Pyright **0 errors/0 warnings**. All actual network-backed DeepWiki
  results still require a public runner: this environment's approved
  `probe` fails DNS resolution before MCP discovery. No real live A5
  execution or E2 success claimed.
- **Resume:** exact source issue/stacked Draft PR and CI receipts should be
  checked at their current remote head; run the mock GitHub Actions job and
  manually dispatch `research-paper-deepwiki-native-a5-e1.yml` in `probe`
  mode on an environment with public DNS. Review the probe fingerprint
  **independently** before manual `run`. Keep predecessor Draft PRs and
  external #1346/#1477 plus release #1356 HOLD unchanged.

## 2026-10-27 — Europe PMC native HTTP/JSON DOI search → original P2/A5 E1

- **Missing feature closed locally:** `research_public_heterogeneous_live_e1.py`
  previously made an independent Europe PMC HTTP crosscheck, which never
  entered SchemaRouter's registry, original-paper P2 graph or A5 agent call.
  Issue #1769 introduces an opt-in curated Europe PMC native profile and a
  reviewed `GET /search` HTTP/JSON route. New files:
  `src/schemarouter/paper_europepmc_registration.py`,
  `scripts/research_paper_europepmc_native_e1.py`,
  `tests/test_paper_europepmc_native_a5_e1.py`, and
  `.github/workflows/research-paper-europepmc-native-a5-e1.yml`.
- **Source shape:** query `DOI:<explicit host DOI>`, `format=json`,
  `pageSize=1`, source `hitCount:int` and nested `resultList.result[*]`
  `doi`/`id` string fields. The native executor uses typed wildcard projection
  on original JSON, with no invented top-level DOI and no graph-join edge.
  The source-specific wrapper requires an exact matching DOI and nonempty
  source record ID before returning the provider response; `hitCount` remains
  an unverified provider **search-hit count**, not a verified match count.
- **P2/A5:** separately host-approved exact local source fingerprint and
  origin; source-semantic attestation, original G5 host-approved direct
  scalar inputs, scoped reader authorization, EN/KO/JA concept aliases, one
  native typed read-only call. A deterministic agent emits a forged DOI and
  incompatible `format/pageSize`; neither is executed.
- **Local tests:** initial source module import RED, then GREEN. The source-
  shaped and existing provider/public-API regression ran **128 passed**; the
  wider original-paper/provider/native group ultimately ran **692 passed**
  in 30.69s, including source-row failure branches and search metacharacters.
  Full-repository Ruff **PASS**; targeted Pyright **0 errors/0 warnings**.
  Exact remote tree, review and GitHub PR/CI status must be appended after
  publication; these local checks alone are **not** a live-provider claim.
- **Independent review:** a significant query-language boundary was identified:
  the generic Crossref DOI validator allowed `*`/`?`/grouping punctuation to
  pass into Europe PMC's unquoted search grammar. The specific failing
  regression was RED before / GREEN after a conservative literal-DOI suffix
  allowlist, enforced both by the host runner and native invoker before I/O.
  This pilot intentionally rejects less common standards-valid DOI punctuation
  outside `[A-Za-z0-9._/-]`. Reviewer's remaining test coverage suggestions
  were added for malformed records and provider hit-count semantics.
- **Live verification attempted:** sandboxed public API call failed on local
  proxy connection; the approved unsandboxed `curl` attempt returned HTTP 503.
  There was no successfully observed Europe PMC payload this turn. Use the
  manual-only GitHub Actions live job on a public-DNS runner, with a separately
  approved prior source fingerprint, before claiming public E1 success.
- **Remaining gates:** manual-only public-DNS `probe/run` on GitHub Actions,
  independent model E2 data and answer-quality assessment, #1346/#1477,
  release #1356 HOLD. Do not merge stacked Drafts as a side effect of E1.

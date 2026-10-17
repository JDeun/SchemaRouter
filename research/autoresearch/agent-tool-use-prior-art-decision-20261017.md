# Prior-art-first decision: agent/tool-use quality, not another ad-hoc prompt trial

**Decision type:** Research-first architectural decision (PROPOSAL only)
**Reviewed:** 2026-10-17
**Owners:** #200 qualification control; #1477 R04/R05/A02; #1346 independent provider E2; #1510 upstream research integration checklist
**Evidence:** upstream documentation + exact source files; no SchemaRouter performance is established by this review.
**Current state:** v0.17.0 stable; 0/19 independent E2; v0.18 #1356 and default-model promotion HOLD.

## 0. Reuse existing repository research BEFORE making experiments

The existing [tool-routing landscape](../../docs/research/tool-routing-landscape.md),
[prior-art roadmap](../../docs/research/prior-art-roadmap.md),
[history](../../docs/research/design-and-experiment-history.md),
[experiment ledger](../../benchmarks/research-experiment-ledger.json) and
[qualification](../../QUALIFICATION.md) remain authoritative. They already
cover Pydantic AI native ToolSearch (E0), OpenAI Agents dynamic MCP tool filters
(E0), multiple rejected cosine/cross-encoder routing variants, real E5 source
dependent negative/positive results, and the separate provider-native E2 block.
**Do not rename these experiments as native BFCL/Qwen-Agent measurements.**

Current new observations on the exposed, self-authored three-case EN/KO/JA
bound-host study:

- [#1506 baseline](https://github.com/JDeun/SchemaRouter/actions/runs/39029981154):
  frozen Qwen3-0.6B actual real package-host execution, 0/3 complete; each
  language executes the first read then returns a premature final.
- [#1507 reminder](https://github.com/JDeun/SchemaRouter/actions/runs/39030372571):
  one generic TASK_INCOMPLETE message, 0/3 complete.
- [#1508 transcript](https://github.com/JDeun/SchemaRouter/actions/runs/39037998330):
  EOS-only and assistant structured-tool-call history, both 0/3.
- [#1509 larger local model](https://github.com/JDeun/SchemaRouter/actions/runs/39039011251):
  Qwen3-1.7B completed KO/JA and final answer, but EN still prematurely
  finalized; total 2/3 in 135s CPU load+generation, peak ~10.3 GiB process RSS.
  This is a **cross-run development comparison**, not a model promotion gate.

The pattern does not prove that hand-tuned prompts, a larger model or a new
custom parser is the best general solution. Benchmark leakage is already
possible: all three tasks and the intermediate findings are published.

## 1. Actual upstream prior art and transfer boundary

| Upstream and pinned source of inspection | Verified published contract | Transfer into SchemaRouter | What NOT to infer |
| --- | --- | --- | --- |
| [Qwen3 official function-call guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md), inspected file blob `4950f37dee85c075b1b45d19a8bb67aa59123300`; [Qwen-Agent function-call implementation](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/function_calling.py), blob `09963012829490037f3b1f4c84c0e6858201b299` | Qwen3 recommends Hermes-like functions; Qwen-Agent owns canonical message rendering/parsing and function response protocol | **Priority 1**: pin/install a licensed upstream version; establish protocol conformance from real Qwen outputs to a typed *proposal* and back to a faithful function/tool message. Compare canonical parser and model-specific template to the current hand-written XML regex and manually reconstructed history. Use the same previously frozen source only as a *regression/conformance surface* | Qwen-Agent parsing alone is not an execution permission, a no-route classifier, E2 or proof that the agent will issue step 2. Do not copy framework execution privileges into the trusted host |
| [Berkeley Function Calling Leaderboard BFCL V4](https://gorilla.cs.berkeley.edu/leaderboard), [code and data](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) | Relevance/irrelevance and hallucination diagnostics, single/multiple/parallel calls, multi-turn and format sensitivity; executable comparisons | **Priority 2**: map AST/typed arguments, no-call when functions irrelevant, missing function or missing parameter, multi-turn outcomes and rejected invalid tool calls to R02/R04/R05 and A02. Pin the exact suite/runner before consuming cases | BFCL relevance is not authorization, and its programming-language varieties are not evidence of natural-language EN/KO/JA competence. Public examples are not independent private SchemaRouter task gold |
| [Apple ToolSandbox research](https://machinelearning.apple.com/research/toolsandbox-stateful-conversational-llm-benchmark), [upstream code](https://github.com/apple-aiml-research/ToolSandbox), paper 2408.04682 | Stateful tool execution, implicit inter-tool dependencies, intermediate/final milestones, insufficient-information cases, interactive user simulation | **Priority 3**: transfer trajectory-level state-transition/side-effect assertions, milestone correctness, early-final and tool-recovery classification to A02/R03/R05. Score the *whole task*, not just first authorized call | Do not import its test tasks as new independent SchemaRouter E2, conflate simulated providers with original native providers or require paid RapidAPI/Gemini access for local standard-CPU qualification |
| [tau2-bench / tau-bench](https://github.com/LLM360/tau2-bench), inspected README blob `59890417d6db478bdd641cf083b0b6ea35f0cbab` | Domains define policy, tools, tasks and optional user simulator; end-to-end policy adherence / task outcome | **Priority 4**: adapt policy-compliant/incorrect/no-op/needs-user-information trace accounting; build a deterministic host-policy oracle with no route-existence disclosure | Do not use simulated-user approvals to replace per-invocation RBAC/ABAC or count its baseline cases as provider-publisher E2 |
| [Hugging Face smolagents](https://github.com/huggingface/smolagents), [MultiStepAgent API](https://github.com/huggingface/smolagents/blob/main/docs/source/en/reference/agents.md), blob `c2463c8414729c2ad1f2ccf3cf36ffe2ccab654b` | Maintained multi-step agent protocol, tool-call representation, memory and bounded iteration | **Comparison only**: use its ToolCallingAgent as one **external orchestrator**, never copy arbitrary CodeAgent execution into SchemaRouter's privileged source host | LocalPythonExecutor is not a sandbox; running agent-authored Python is not required to deliver SchemaRouter's trusted typed source/field route |
| [LangGraph](https://github.com/langchain-ai/langgraph), [state/persistence](https://langchain-ai.github.io/langgraph/concepts/durable_execution/) | Persistent graph checkpoint, state/interrupt/retry, lifecycle outside each individual tool | **Integration contract**: the orchestrator owns state, checkpoints and completion loop; SchemaRouter supplies principal-visible typed candidates, execution receipts, source-projected observations, and current-authority validation | Do not turn SchemaRouter into a new graph/checkpointing framework or treat a successful graph run as proof a native provider call was authorized |

All source blobs are inspection identities, NOT formal dependency/version pins.
Before installation/import: verify exact release/tag, Python dependency compatibility,
license and redistribution terms, GitHub Actions Linux CPU RAM/time, error behavior
and source-host authentication/authorization boundary.

## 2. Recommended product architecture — retain separation of concerns

```text
External orchestrator (Qwen-Agent / smolagents / LangGraph / consumer app)
  controls: user dialogue, multi-turn state, clarification, final answer, retries
          |
          v typed proposed operation + structured inputs
SchemaRouter's principal-scoped discovery and typed validation boundary
  controls: source-registered route/field/parameter IDs; K/schema budget;
  visibility masking; correct permission/no-authority distinctions
          |
          v host-authorized plan, current-policy and source fingerprint
Provider adapter + trusted executor
  controls: original provider schema; fresh per-call RBAC/ABAC, data scope,
  approval, argument and response validation, projected public result
          |
          v only approved observation returned to orchestrator
External agent continues or reports non-completion; never invents receipt
```

Do **not** allow an upstream agent to mark a hidden operation as permitted,
construct an authorization receipt, infer inaccessible routes from 'forbidden',
or bypass original-provider validation. The model's entire tool call is an
**untrusted proposal**. Host policy always wins.

This preserves the purpose explicitly described in
[product north star](../../docs/research/product-north-star-and-test-matrix.md):
SchemaRouter is a typed capability/execution layer, **not a general agent framework**.

## 3. New research order and falsifiable gates

**Gate A — Upstream protocol equivalence first (zero model search).**
Pin the Qwen-Agent version and inspect the original Qwen3 tools/function
template; capture *safe/synthetic* hand-created records of:
single correct call, two ordered calls with intermediate observation,
a premature final, malformed JSON, missing required field, wrong extra field,
unknown/denied tool, stop/EOS, multi-call response and context overflow.
Generate expected callable-proposal outputs through upstream implementation.
Build an adapter comparison that requires exact source-bound tool ID and
argument equivalence; do not execute model-selected routes in Qwen-Agent
without the SchemaRouter host validator. **Fail** if ambiguity, leaked hidden
tool, route spoofing or untrusted receipt can reach the invoker. A parser
matching published sample messages is merely *protocol conformance*, not
task accuracy.

**Gate B — Adopt evaluation *methodology* before another prompt/model trial.**
Map BFCL multi-turn, irrelevant function, missing parameter and AST result
categories; adopt ToolSandbox state and intermediate/final milestones, and
tau2 policy-violation/unsatisfied-user distinctions. Store separate
reasons: `no_supported_operation`, `required_input_missing`,
`multiple_authorized_hypotheses`, `opaque_unavailable`,
`premature_final`, `invalid_tool_proposal`,
`untrusted_call_blocked`, `native_provider_failure`,
`partial_task`, `final_answer_wrong` and `task_complete`.
Avoid flattening all cases into one '0/3 task pass' score.

**Gate C — Independent source-author E2 before promotion.**
Obtain approved original provider-native tool descriptors, case/gold author
independent of experiments, query-disjoint and provider-disjoint EN/KO/JA
cases, permissioned live execution or independent immutable provider fixture,
separate locked tune/test partitions, hashes and reviewer. Require no hidden
route information in any model message; cap K/tokens/CPU p50/p95. Do not
relabel BFCL or ToolSandbox's public tasks as new independent E2 evidence.

**Gate D — Only now evaluate multiple model choices on a locked split.**
Qwen3-0.6B/1.7B and any approved free candidates may be compared on equal
candidate catalogs, actual published local CPU hardware, tool schema budget,
maximum turns, host authorization and final-task rubric. Report supported
false refusals, unsupported false accepts, unauthorized attempt/exec,
needed clarification, premature final, complete task success, resident memory,
latency and source/license provenance. Prior exposed 3-case tests may remain
smoke checks only, not model/threshold selection.

## 4. Research decision

1. **Keep existing integrations.** Already implemented Pydantic AI/Agents SDK
   adapters are relevant contract tests. Do not recreate their orchestration.
2. **Reuse Qwen-Agent for protocol specification, not for privileged execution.**
   Its agent loop may be used only outside the SchemaRouter trust boundary.
3. **Borrow evaluation structure from BFCL, ToolSandbox and tau-bench.**
   The evaluation *contracts and scoring rules* should be reused or
   directly compared; do not automatically package foreign public cases as E2.
4. **No new hand-authored prompt tuning, cosine threshold or default-model
   promotion** based on the existing published DEV failures.
5. **Record implementation in separate issues and guarded PRs** before
   starting any further model-size or reminder iterations. Preserve all
   frozen B1/B2/0.14, Qwen3-0.6B E0, Qwen3-1.7B E0 and held 19-gate evidence.

**Next implementation candidate:** a *read-only Qwen-Agent canonical
function-call protocol conformance adapter* (no provider invocation) plus a
BFCL/ToolSandbox-derived host trace scoring contract, behind opt-in E0.
No change to production defaults. Dependent integration then composes with
an existing LangGraph/PydanticAI consumer to show the complete host boundary.

## 5. Review checklist (NOT a qualification pass)

- [ ] Confirm official upstream version SHA/tag, license and runtime support
- [ ] Confirm no overlap with existing prior-art registry and terminal experiments
- [ ] Protect and test hidden tool existence and source-field masking
- [ ] Confirm permission/missing/ambiguous states are not leaked to model
- [ ] Confirm original provider execution remains solely SchemaRouter host-controlled
- [ ] Add independent E2 input, reviewer and locked native trace provenance
- [ ] Preserve 0/19 E2, #1356 release HOLD, default model promotion HOLD

No paper leaderboard score, outside README claim or green CI check turns
any row QUALIFIED.

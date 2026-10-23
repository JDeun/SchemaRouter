# CodeGraph-style selective schema E1: genuine pinned Qwen local four-arm negative

**2026-10-23 · #1711 · Draft PR #1722 · E1_LOCAL_SOURCE_CONTROL · not E2**

## Research question and result

Can graph-scoped *selective model-driven schema disclosure* improve real
LLM-native 2-hop task completion or total prompt cost while retaining the
original SchemaRouter authorization/executor and strict K5?

**No demonstrated improvement in this experiment.** Search/index CPU savings
previously demonstrated in #1560/#1721 do **not** imply Agent task utility.
Both real pinned model checkpoints completed **zero** 2-hop tasks in EN, KO or
JA under the controlled **four registered read-only native route** fixture.
The surgical arm cost *more* total input+output model tokens in all tested
first-failure trajectories and did not generate a final accepted answer.

This is a limited local synthetic experiment, not publisher-independent,
query-disjoint E2. Each language is one translated owner-declared case; there
are only 1 task × 4 arms × 3 languages per model, not a representative
accuracy sample. The source reads are original local registry callbacks, **not**
live external provider calls.

## Paired source and frozen evaluation boundary

- One exact registered 4-route source in each arm: input-free
  `contacts.read`; typed dependent `cases.read`; two unrelated read-only
  `inventory_00.read` and `inventory_01.read`. All four exposed FULL tool
  definitions fit K5 without changing host disclosure or rebatching twelve
  routes. Each arm separately binds fresh equivalent registered original
  callbacks and uses the same original trusted executor, source fingerprint,
  principal, task and strict final scorer.
- A distinct **12-route** fixture remains the separate scaling negative:
  FULL is `BLOCKED_MENU_CAP` under K5, and the four-way denominator is
  `null`/`INCOMPARABLE_FULL_MENU_CAP`. Do not mislabel this as 0% FULL
  success or infer a 12-route four-arm cost comparison.
- The two model checkpoints are **independent experiment conditions**,
  *not* interchangeable samples or a causal estimate of graph context:
  Qwen3-0.6B at `c1899de289a04d12100db370d81485cdf75e47ca`,
  and Qwen3-1.7B at `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
  Same inherited Qwen generation interface, max 5 model turns; the
  1.7B model is a checkpoint intervention, not a graph-context treatment.

## Actual model task and context-path observations

| Model | Language | FULL native calls | Lexical native calls | G5 native calls | Surgical schema requests | Surgical native calls | Successful two-hop tasks (four arms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-0.6B | EN | 0 | 0 | 0 | 0 | 0 | 0/4 |
| Qwen3-0.6B | KO | 0 | 0 | 0 | 0 | 0 | 0/4 |
| Qwen3-0.6B | JA | 0 | 0 | 0 | 0 | 0 | 0/4 |
| Qwen3-1.7B | EN | 0 | 0 | 0 | 0 | 0 | 0/4 |
| Qwen3-1.7B | KO | 1 | 1 | 0 | 1 | 0 | 0/4 |
| Qwen3-1.7B | JA | 0 | 0 | 0 | 1 | 0 | 0/4 |

Both 1.7B KO and JA surgical arms requested and received a **schema
materialization** but then returned an invalid subsequent model action,
so there was no native source execution. In 1.7B KO, FULL and lexical each
called the original source **once**, then prematurely finalized before the
second dependent read. No model succeeded at the genuine two-hop task.

### Complete-model-turn input + output token receipts

All values are original pinned Qwen-generated **input_tokens + output_tokens**
for the observed trajectory, including the entire surgical schema-request
exchange when present. These are not measured monetary prices.

| Model | Language | FULL | Lexical K5 | Typed G5 | Surgical G5 |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B | EN | 563 | 563 | 388 | 815 |
| Qwen3-0.6B | KO | 560 | 560 | 389 | 814 |
| Qwen3-0.6B | JA | 544 | 544 | 389 | 816 |
| Qwen3-1.7B | EN | 579 | 579 | 393 | 833 |
| Qwen3-1.7B | KO | 1152 | 1152 | 394 | 2170 |
| Qwen3-1.7B | JA | 580 | 580 | 394 | 2056 |

The G5 arm consumed fewer tokens on these **failed first-turn** paths,
but this does not demonstrate lower **cost per successful task**: there were
no successes in any arm. Surgical selective materialization is **not free**:
the initial meta-action prompt and extra generation turn must be included.

## Reproduction and evidence

- Qwen3-0.6B [six-job source-local workflow](https://github.com/JDeun/SchemaRouter/actions/runs/39922466111),
  EN/KO/JA × four-route comparable + twelve-route negative, all jobs
  succeeded. GitHub Actions per-language JSON artifact name:
  `codegraph-qwen-local-e1-<language>-4-39922466111`.
- Qwen3-1.7B [three-job four-route CPU workflow](https://github.com/JDeun/SchemaRouter/actions/runs/39923618201),
  all model jobs succeeded; JSON artifact name:
  `codegraph-qwen17-local-e1-<language>-39923618201`.
- Source scripts:
  `scripts/research_codegraph_local_multiroute_e1.py`,
  `scripts/research_codegraph_surgical_agent_e1.py`,
  `scripts/research_codegraph_qwen17_local_e1.py`. The E1 output
  stores categories, counted model/provider interactions, token receipts,
  model/source revisions and aggregate task flags, **not** raw model
  generations, original arguments, private principal or provider data.

## Open follow-ups / no promotion

1. Diagnose the original Qwen tool-call **grammar vs strict host parser**
   and the failure to continue after an authorized first native observation.
   Log privacy-safe structural action categories only; do not use gold-aware
   retries, relaxed arbitrary JSON calls or fake synthetic successful answers.
2. For the surgical arm, measure whether an improved model/host protocol
   can actually produce a *schema request followed by verified original
   native calls and a strict final answer*; preserve the existing negatives.
3. Benchmark task-complete cost/success on a preregistered, source-disjoint
   independently authored held-out E2 set (#1346) before claiming real
   CodeGraph utility or promoting #1560/#1711 into product defaults.

`#1356` v0.18 remains HARD HOLD. No release, commercial access licence, model
accuracy superiority or production SLO is justified.

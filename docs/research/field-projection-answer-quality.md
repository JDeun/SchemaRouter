# 0.14 output-field projection and final-answer quality

Tracking issue: #506

## The question

> Holding the query, the candidate exposure, the selected route and the raw tool
> response fixed, does returning **only the planned declared output fields**
> change the final answer's factual quality, and how much agent context does it
> remove?

## Why this is a separate experiment

SchemaRouter validates a raw tool response and then hands the agent only the
declared fields the plan asked for. That step is implemented, shipped, and stated
as a core principle in [Field-first execution](../concepts/field-first-execution.md):

> The goal is not merely to choose a tool. The goal is to identify the smallest
> declared data surface that can answer the user's question.

No existing experiment measures it.

| Experiment | What it varies |
| --- | --- |
| [B1 (#420)](agent-utility-b1-result.md) | how many tools the agent can see |
| [#434](typed-capability-retrieval-ablation.md) | how a capability is represented for retrieval |
| [#424](final-answer-quality.md) | answer quality under catalog-level context reduction |
| #506 | what an executed tool hands back |

Choosing fewer tools is a commoditized idea. Descending to the field level is
the part of this design that is not shared with an ordinary Top-K tool router,
and until now the claim for it rested on argument rather than evidence.

## Isolation

Every condition receives the same query, the same candidate exposure (`SR-5`),
the same route, and the same frozen raw record. Only the observation handed back
to the agent differs.

| Condition | Observation given to the agent |
| --- | --- |
| `RAW-FULL` | the entire validated raw response record |
| `PROJECTED` | the declared planned output fields only |
| `PROJECTED+CONTRACT` | planned fields plus their declared `semantic_id` / unit / qualifiers |
| `ORACLE-MINIMAL` | only the fields the gold answer requires |

The transform applies to the agent's context only. The executor's own record,
the task state and every completion check keep seeing the untransformed
observation, so presentation cannot move ground truth. That property is pinned by
test rather than asserted here.

`ORACLE-MINIMAL` earns its place: B1 found that `ORACLE` did **not** dominate
`SR-5`, so over-minimizing is a live hypothesis, not a strawman.

## Corpus

144 semantic tasks: 6 projection strata × 6 languages × 4 independent tasks.
Catalog sizes 100 and 250 are repeated measures nested inside the task.

| Stratum | Competing content placed in the raw record |
| --- | --- |
| `qualifier_sibling` | the same quantity at other declared temperatures |
| `unit_variant` | the same quantity in MPa and psi alongside GPa |
| `superseded_duplicate` | legacy and draft revisions of the current value |
| `nested_record` | a computed value nested under an audit record |
| `cross_provider_name_collision` | generic `value` / `result` keys and a second provider's copy |
| `multi_step_provenance` | staging, cache, temp and mirror URIs across two steps |

Corpus validation **fails closed** when a raw record carries nothing beyond its
declared plan. Without competing content, `RAW-FULL` and `PROJECTED` would be the
same observation and the comparison would measure nothing. Validation also
rejects a task whose required fact is unreachable after projection, which would
otherwise score `PROJECTED` against evidence it was never shown.

## Metrics

Reported separately and never collapsed into one score, following #424's rule:

- required-fact recall;
- numeric value accuracy;
- unit accuracy;
- provenance accuracy;
- unsupported-fact rate;
- contradiction count;
- exact mandatory-field completion;
- observation characters and total input tokens;
- turns, wall latency;
- unauthorized destructive executions.

The statistical unit is the semantic task. Catalog repeats are averaged within a
task before resampling, so they cannot inflate the sample. Deltas against
`RAW-FULL` are paired within task and reported with a 10,000-iteration cluster
bootstrap at 95%.

## Promotion gate

Non-inferiority on quality **and** a strict reduction in observation context:

| Requirement | Threshold vs `RAW-FULL` |
| --- | ---: |
| required-fact recall | ≥ −2pp |
| numeric value accuracy | ≥ −2pp |
| unit accuracy | ≥ −2pp |
| provenance accuracy | ≥ −2pp |
| unsupported-fact rate | ≤ +1pp |
| contradiction count | no greater |
| unauthorized destructive executions | 0 |
| observation characters | strictly lower |

A quality *gain* is reportable but is not required. A context reduction alone
does not pass.

## Staging

Both arms are driven by the 0.14 conveyor; neither needs a manual dispatch.

1. **Development screen** — the frozen B1 small agent
   (`Qwen/Qwen3-0.6B` @ `c1899de2`). Reusing the exact published B1 runtime keeps
   context measurements comparable instead of introducing a fourth
   uncharacterised model.

    It consumes no upstream artifact, so the conveyor advances it **before the
    B2 gate**: queuing it behind the frozen chain would delay development
    evidence for no scientific reason, and advancing it first keeps every early
    return in the controller from starving it.

2. **Confirmation** — the canonical strong agent
   (`HuggingFaceTB/SmolLM3-3B` @ `a07cc9a0`), **appended after the conveyor's
   terminal-evidence stage** and keyed on the terminal digest.

    Appending rather than inserting matters here. The conveyor DAG was
    preregistered before downstream corpus generation and is already in flight;
    inserting a stage would move an existing stage's inputs or ordering, while
    appending after terminal evidence cannot. The amendment, and the list of what
    it explicitly did not change, is recorded in
    `benchmarks/agent-utility-0.14-conveyor-preregistration.json`.

    The workflow still verifies that the canonical B2 run succeeded without
    reading B2 outcomes.

### Source freeze

#506 has **its own** frozen implementation revision. It is resolved on first
dispatch, checked to actually contain the experiment's scripts, and then reused
verbatim by both arms.

It is never `DOWNSTREAM_IMPLEMENTATION_SHA`. That SHA belongs to the already
frozen #431/#432/#424 chain and predates every projection script, so a stage
dispatched against it would check out a tree that cannot run the experiment —
while unit tests, which use stubs rather than a real checkout, stayed green. Both
workflows now also refuse such a checkout in a preflight step, and the controller
refuses to dispatch a revision missing those files.

### Development vs confirmation

Both arms run the **same** frozen corpus, generator, conditions and scorer, so
the development screen is **diagnostic only**. Once its scoring starts, its
results may not change:

- conditions;
- task wording or content;
- distractor strata;
- thresholds and promotion gates;
- the scorer;
- prompt or harness semantics;
- row inclusion;
- the frozen projection source.

Confirmation may differ in exactly one preregistered respect: the runtime. This
is the same relationship B1 has to B2: one frozen protocol, a stronger agent.

Wanting a design change out of the screen's results means closing this
experiment as consumed and preregistering a successor with its own
query-disjoint surface, not amending this one.

The development screen returned a null result on run 36682589574: the frozen B1
agent never called a tool, so there was nothing for projection to affect. It is
consumed. Its replacement, with an instrument chosen by a frozen capability gate
and its own query-disjoint surface, is the
[successor screen](successor-screen.md). The confirmation arm is unaffected.

## Independence

- fresh disjoint task surface;
- B1 rows are not tuning data;
- #432 held-out rows are not tuning data;
- the sealed #424 corpus is not used, and results here may not tune it;
- no retrofit into B1.

## Claim boundary

If the gate passes, the permitted claim is scoped to the frozen surface:

> On the evaluated surface, returning only the planned declared fields preserved
> final-answer factual quality while reducing agent observation context.

This does not establish population-level generalization. That remains
[#432](large-heldout-agent-utility.md)'s role.

## Reproduction

```bash
python scripts/generate_agent_utility_v7_projection_corpus.py \
  --source-revision "$(git rev-parse HEAD)" \
  --out artifacts/projection/projection-corpus.json

python scripts/validate_agent_utility_v7_projection_corpus.py \
  --corpus artifacts/projection/projection-corpus.json
```

Preregistration: `benchmarks/agent-utility-v7-field-projection-preregistration.json`.

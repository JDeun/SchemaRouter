# Qwen CodeGraph E1: one-action-per-turn prompt intervention

**2026-10-23 · #1723 · opt-in four-route local original-source E1 · not E2**

## Specific competing hypothesis

Actual pinned Qwen3-1.7B generated **multiple native tool-call blocks in a
single model turn** on EN/JA and after surgical schema materialization on
KO/JA. The existing strict host appropriately rejects ambiguous batches.
Qwen3-0.6B KO sometimes generated a single native JSON object which the
separate strict bare-JSON E1 adapter could parse, but the original source
host rejected its route order or availability. Neither the original
CodeGraph-style surgical disclosure nor the separate JSON grammar experiment
completed a verified two-hop task.

This preregistration tests whether a **prompt-only, single-step generation
protocol** makes a larger pinned local model emit one authorized, properly
sequenced action per turn rather than simultaneous speculative actions.
There is no claim this will work; failure must be retained.

## Controlled treatment and protected invariants

The new explicitly requested flag `--experimental-single-step-prompt`
adds one fixed generic instruction to the existing **system message**
for all four original registered source arms: FULL, lexical K5,
typed G5, and surgical G5. It says: emit exactly ONE valid tool-call
object per turn, choose only among already offered tool names, wait for
a genuine host observation before the next dependent action, and
give a final answer only after verified native operations.

- **No change** to model weight SHA, tokenizer, deterministic decoding,
  4-route original local source, language/task, principal, registered
  schema, source fingerprint, read-only executor, route selection, K5,
  strict `parse_one_model_action` and surgical `_parse_action`,
  host argument binding, MAX_TURNS, token accounting or strict final scorer.
- The prompt contains **no route-specific gold, task answer, invented
  observations or private schema**. It is generic tool-call formatting
  guidance only; the model still chooses each original tool and arguments.
- No JSON grammar normalization is enabled here: the experiment refuses
  simultaneous activation with `--experimental-bare-native-json`. This
  is a distinct MODEL-PROMPT intervention, not a result of a CodeGraph
  index improvement nor a treatment that can be pooled with #1727.
- Only genuine four-route cohorts are comparable across FULL and the three
  other arms. Twelve-route FULL remains K5-blocked and is explicitly
  prohibited for the new treatment. Negative denied/no-fit/over-K tests
  and original provider tests remain unchanged.
- Optional privacy-safe `action_structure_labels` only record fixed
  shape names, never raw model outputs, tool arguments, source data,
  model thoughts or credentials.

## Evidence and acceptance

Dedicated GitHub Actions Linux Python 3.12 **six-cell matrix** of genuine
immutable public Qwen3-0.6B and separately pinned Qwen3-1.7B in EN/KO/JA.
Each cell reports all four strict original arms, at most five model turns,
schema request count, native source attempts and successful source calls,
full-task final success (one owner-declared local task per arm and language),
and total model input/output tokens inclusive of additional turns.

Evaluate primarily **fully completed strict native two-hop tasks**, not
merely better JSON formatting or parser acceptance. Any improvement is at
most due to this independently registered prompt condition under these
synthetic author-prepared tasks, not evidence of external E2. Never weaken
the original registered source path ordering or validate a guessed second
call. If all tasks remain unsuccessful, preserve that negative and do
not extrapolate cost per completed task.

Comparators: baseline [Qwen0.6B #39922466111](https://github.com/JDeun/SchemaRouter/actions/runs/39922466111),
[Qwen1.7B #39923618201](https://github.com/JDeun/SchemaRouter/actions/runs/39923618201),
[action-shape diagnostic #39926238349](https://github.com/JDeun/SchemaRouter/actions/runs/39926238349),
and separate strict parser [#39928522628](https://github.com/JDeun/SchemaRouter/actions/runs/39928522628).
The last one is **not a simultaneous variant**.

Independent publisher E2 (#1346) remains externally blocked; v0.18
release (#1356) remains HARD HOLD. No product default or commercial
provider execution is modified.

## Actual six-cell pinned Linux E1 results (2026-10-23)

[Exact source/model run #39930411562](https://github.com/JDeun/SchemaRouter/actions/runs/39930411562):
all **six** matrix cells SUCCESS, with separately preserved numeric/label-only
JSON artifacts `codegraph-single-step-e1-<qwen06|qwen17>-<en|ko|ja>-39930411562`.
These are the original four source callbacks and the genuine model's
selected actions, never forced tool calls or injected oracle observations.

| Model checkpoint | Language | FULL full-task | Lexical full-task | G5 full-task | Surgical full-task | Original native calls (FULL / lexical / G5 / surgical) |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3-0.6B | EN | 0/1 | 0/1 | 0/1 | 0/1 | 0 / 0 / 1 / 0 |
| Qwen3-0.6B | KO | 0/1 | 0/1 | 0/1 | 0/1 | 0 / 0 / 1 / 0 |
| Qwen3-0.6B | JA | 0/1 | 0/1 | 0/1 | 0/1 | 0 / 0 / 1 / 0 |
| Qwen3-1.7B | EN | **1/1** | **1/1** | 0/1 | 0/1 | 2 / 2 / 1 / 0 |
| Qwen3-1.7B | KO | **1/1** | **1/1** | 0/1 | 0/1 | 2 / 2 / 1 / 0 |
| Qwen3-1.7B | JA | 0/1 | 0/1 | 0/1 | 0/1 | 2 / 2 / 1 / 0 |

### Verification and interpretation

In 1.7B EN and KO the FULL and lexical arms each independently invoked
the two registered original **read-only** sources in dependency order,
used the host's actual observations, then generated a final JSON accepted
by the unchanged strict scorer (`completed_final`, `full_task_complete=true`).
Their respective original Qwen turns were three and complete model
input+output token receipts **EN 2,142 / KO 2,145 per successful arm**.
In 1.7B JA both original native source calls occurred in FULL/lexical,
but the model's final JSON failed the strict answer oracle despite
`completed_final`: **native execution alone is not task success**.

For both pinned checkpoints, all three G5 language arms made one
registered native call and then prematurely finalized; none completed
the second dependent read. The surgical arm made **zero** original
source calls in all six model/language cells. The initial surgical
model action was a non-executable bare JSON-shaped response or final;
the strict host did not fake a schema request or grant source authority.
Each 0.6B language cell therefore remained **0/4** completed tasks.

**Scope of the result:** This is a positive, narrowly scoped
*model-prompt interoperability* observation in a public fixed model,
not an improvement due to graph indexing or CodeGraph's disclosure.
There is exactly **one owner-authored synthetic local task per arm
per language**, and translated tasks are not independent held-out E2
cases. A meaningful generalization, task success-rate confidence
interval or production SLO is impossible from this fixture. More
tokens were generated with the longer prompt and extra turns; it
would be misleading to compare cost *per successful task* to prior
zero-success baselines. The larger model checkpoint is a different
cohort, never pooled with Qwen0.6B. No default or release promotion.

### Follow-up gate

The decisive new blocker for surgical/G5 is **continuation after an
actual authorized source observation**, not raw graph-index retrieval
latency. Future protocol experiments should improve proper second
source call selection and exact final output without injecting
task gold, changing the original executor or relaxing the existing
one-tool-per-turn/parser/authorized-input contract. A 12-route FULL
control remains over the unchanged K5 cap and is not part of this
four-arm success comparison.

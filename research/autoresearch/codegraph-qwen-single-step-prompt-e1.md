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

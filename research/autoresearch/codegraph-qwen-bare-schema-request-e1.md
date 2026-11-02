# Surgical G5: strict offered-only bare schema request E1

**2026-10-23 · #1723 / #1711 · preregistered after the shape-only #1730 diagnostic · research opt-in only**

## Actual-model trigger, before any treatment

On the unchanged one-action-per-turn Qwen3-0.6B KO E1 matrix in
[#1730, run #39944766303](https://github.com/JDeun/SchemaRouter/actions/runs/39944766303),
the surgical first turn was classified as
`bare_json_offered_schema_request_shape`: exactly one bare JSON tool-like
object naming the *currently host-offered reserved schema request*, with
one to five unique string route IDs. The **original strict parser**
produced `schema_requests=0`, `actual_source_calls=0`, full task **0/1**.
That structural diagnostic does **not** prove that the requested IDs are
authorized or that the model will continue correctly after definitions.
Qwen0.6B KO is one author-created development case, not independent E2.

The completed **six-cell** shape-only one-action prompt control from that
same run #39944766303 further classified the surgical first turn as the
*host-offered bare schema request shape* for Qwen0.6B **KO/JA** and
Qwen1.7B **EN/KO/JA** (**5/6**). Qwen0.6B **EN** emitted
`bare_final_json` instead; the new normalization must do nothing in that
cell. All six original surgical arms had zero schema requests, zero
native calls and zero full-task successes. These are fixed public shape
labels, not raw prompts/arguments or authorization evidence.

## Hypothesis and separate experimental cohort

A complete currently offered **reserved non-executing schema request** may
fail only because Qwen emits the canonical `{name,arguments}` object
without `<tool_call>` wrappers. A one-time strict normalization could permit
host-validated schema materialization and subsequent original source calls.
The null result is also informative: if the model fails to call the two
registered original routes or to produce a correct final answer, grammar
normalization alone did not fix surgical task utility.

Explicit opt-in `--experimental-bare-schema-request` requires the same
**four registered read-only local routes**, `--experimental-single-step-prompt`,
strict K=5 and the `joined` source condition. It refuses coactivation with
the separate original native bare-JSON grammar experiment or G5 verified
continuation cue. The treatment applies **only** to `surgical_g5_e1`;
FULL, lexical K5 and typed G5 receive the identical preexisting
one-action system prompt and original parser/scorer/source.

- Call the unchanged surgical `_parse_action` **first**. Only if it gives
  `final`, the host has not materialized definitions, and the fixed
  structural classifier reports a complete *currently offered reserved*
  schema request, enclose the same bounded text in one canonical
  `<tool_call>` block and re-run that **same** `_parse_action`.
- No textual repair, extra model turn, synthetic schema/tool observation,
  missing argument synthesis, role/route inference, duplicate JSON keys,
  nonfinite values, recursive arguments, multi-call batch or arbitrary
  provider action is admitted. The model must have supplied all route IDs;
  the host does **not** select them.
- The original materializer independently checks each requested route ID,
  G5 selection, principal, policy, live source fingerprint, field scope,
  route availability and K5 before exposing any definitions. A successful
  schema request is **not** original provider execution. Every later native
  call must pass unchanged strict parser and original read-only invoker with
  observed-source bound parameters and a separate final oracle.
- The model turn, every token and schema materialization cost are included
  in the existing receipt. The sanitized count
  `bare_schema_request_normalizations` (0 or 1) appears only in the surgical
  opt-in outcome; no model output/route identifiers/arguments/credentials
  are persisted. Original controls and frozen #432 evidence remain intact.

## Measured experiment and decision gate

Run an independent named GitHub Linux CPU matrix with immutable
Qwen3-0.6B (`c1899de289a04d12100db370d81485cdf75e47ca`) and Qwen3-1.7B
(`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`), EN/KO/JA, each
over the same owner-authored four-route local source, principal, task,
seed, one-step prompt, 5-turn budget and **four** arms. Use the existing
strict final gold, record all model input/output tokens, schema requests,
native call attempts/successes and structure-only action labels. Original
one-step run #39944766303 remains the *matched control*, distinct from
the new treatment. No re-scoring old negative runs.

The primary endpoint is **complete two-hop original native execution and
correct final answer**, not merely a recognized schema request. A useful
positive path needs actual independent registered source callbacks in
correct dependency order and host-observed argument binding. Even a positive
result is only a grammar protocol effect in these correlated local E1
translations, **not** CodeGraph index utility, external publisher-authored
E2 (#1346), a commercial API entitlement, or evidence for v0.18 promotion
(#1356 HARD HOLD). Preserve any zero-success or worse token-cost outcome.

## Actual pinned-model result — recorded before follow-up diagnosis

The **six-cell** GitHub Linux run
[#39946110637](https://github.com/JDeun/SchemaRouter/actions/runs/39946110637)
completed successfully at [draft PR #1731](https://github.com/JDeun/SchemaRouter/pull/1731),
commit `46d983d5e2c99903e68e3189d76265e4ed775473`. All six cells have
denominator **one author-created local E1 task**, not six independent cases.

| Pinned model | Lang | Surgical normalized reserved requests | Materialized schemas | Executed original calls | Surgical full-task success | Surgical stop |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Qwen3-0.6B | EN | 0 | 0 | 0 | false | premature_final |
| Qwen3-0.6B | KO | 1 | 1 | 0 | false | premature_final |
| Qwen3-0.6B | JA | 1 | 1 | 0 | false | premature_final |
| Qwen3-1.7B | EN | 1 | 1 | 0 | false | unbound_source_arguments |
| Qwen3-1.7B | KO | 1 | 1 | 0 | false | unbound_source_arguments |
| Qwen3-1.7B | JA | 1 | 1 | 0 | false | unbound_source_arguments |

This is a **negative strict task result**: surgical 0/6. The 1.7B model
produced `valid_native_tool_call_shape` after schema materialization in
all three languages, but the original host refused the arguments as
unbound, correctly making **zero** source calls. The current strict
native argument check **must not** be relaxed. In the unchanged FULL and
lexical K5 controls, 1.7B executed two source calls per language, and
passed EN/KO full final correctness (2/3 each), with JA final wrong;
0.6B FULL/lexical passed 0/3. Graph-only G5 passed 0/6. No claim of
CodeGraph-caused savings or task success is supported by these results.

### Preregistered next diagnostic, no intervention to scored behavior

For the **next** head/run, record only a fixed, non-sensitive category
when the existing host check `arguments != expected` refuses a surgical
native call: `unexpected_argument_keys`, `missing_argument_keys`,
`unexpected_and_missing_argument_keys`, `argument_value_mismatch`, or
`unsupported_bound_path`. Never expose the differing names or values,
gold, route IDs, model text or source response. Absence of mismatch gives
an empty label list. Diagnostics are off by default; they do not affect
accepted calls, the model prompt, original parser/executor, authority,
K5, source, task oracle or scoring. Preserve this run #39946110637 as
the unchanged scored baseline. **Do not propose model prompting or
automatic argument repair before locating the actual mismatch class.**

# Graph Frontier E1 — preregistered pinned local Qwen study

Date: 2026-10-23. Parent #1723; implementation PR #1734. This section was
recorded before examining any **Graph Frontier** real-model outputs.

## Fixed conditions and interventions

Six owner-authored local language/checkpoint cells: Qwen3-0.6B (revision
c1899de289a04d12100db370d81485cdf75e47ca) and Qwen3-1.7B (revision
70d244cc86ccca08cf5af4e1e306ecf908b1ad5e), each in EN, KO and JA,
on GitHub Actions Linux CPU. Original joined four-route read-only source,
strict K=5, five turns, one local task per cell and immutable original host
callbacks/source principal. Unchanged full, lexical, typed G5 and surgical
#1733 prompt-cue arms; the fifth opt-in arm is graph_frontier_g5_e1.

No new model-selected native tool grammar, route/argument auto-completion,
source grant, privilege or scorer gold. The frontier treatment intentionally
bundles stage-specific native menus, omission of a schema-request turn, and
host-only original graph reference; no isolated claim for one factor is valid.

## Registered outcomes

Primary success: two actual original producer/consumer read-only callbacks in
authorized path order AND correct independently scored final answer.
Secondary: input+output model tokens, model turns, frontier tool count per turn,
schema requests, native-call attempts, context/permission refusals and latency.
Never add tool_schema_tokens twice. Report zeros and failed cells.

Prior pinned #1733 Qwen3-1.7B surgical path-order control: 3/3 correct,
5,359–5,363 model tokens, while contemporary FULL: 2/3 correct,
2,142–2,151 model tokens. Qwen3-0.6B surgical: 0/3. These numbers are
descriptive historical controls only, not thresholds or external validation.

A saving versus the #1733 surgical arm is not automatically a saving versus
FULL. E1 is synthetic owner-reviewed local evidence, NOT source-disjoint
independent E2. Issue #1346 stays BLOCKED_EXTERNAL; #1356 v0.18 HARD HOLD.

## Post-measurement results (separate from preregistration)

Frozen result source: [GitHub Actions #39963346195](https://github.com/JDeun/SchemaRouter/actions/runs/39963346195).
All six Qwen model/language cells completed their GitHub Actions verification
jobs successfully. The actual model-produced strict full-task outcome is
**Graph Frontier 0/6**, NOT a successful optimization. All six JSON
artifacts report the same checked-out CI merge source revision
`72ede075c4eba8668b78ab43b3a6508deb8d8a5e`;
the PR code head before this documentation update was
`e36535b95022e6ec22cfe96361aebb76f383611f`.
Check artifact receipts rather than treating a green workflow as model success.

| Model | Language | FULL strict | Surgical #1733 strict | Frontier strict | Frontier original calls | Frontier tokens | Frontier stop |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| Qwen3-0.6B | EN | fail | fail | fail | 0 | 402 | premature_final |
| Qwen3-0.6B | KO | fail | fail | fail | 0 | 401 | premature_final |
| Qwen3-0.6B | JA | fail | fail | fail | 0 | 399 | premature_final |
| Qwen3-1.7B | EN | pass | pass | fail | 1 | 882 | premature_final |
| Qwen3-1.7B | KO | pass | pass | fail | 1 | 884 | premature_final |
| Qwen3-1.7B | JA | fail | pass | fail | 1 | 884 | premature_final |

Qwen3-1.7B surgical path-order again obtained 3/3 success at 5,359–5,363
tokens. Contemporary FULL obtained 2/3 at 2,142–2,151 tokens.
The new frontier 1.7B model saw initial producer menu of size 1, called that
original producer once, saw verified consumer menu of size 1, then returned a
premature final without calling the consumer, in **all three languages**.
Qwen3-0.6B returned a premature final before any original native call,
with only the first menu size 1 seen, in all three languages.

Total tokens were smaller only because **the task did not finish**; treating
that as cost efficiency is invalid. Native scoped authorization and argument
validation stayed intact; no source-disjoint E2 or production benefit follows.
The first-stage frontier alone is not a correctness-preserving replacement
for the successful #1733 surgical path-order arm.

**Follow-up hypothesis (new experiment only, not retroactive treatment):**
after a verified original producer callback, add a phase-specific generic
continuation cue in a separate opt-in arm without exposing hidden argument
values or route/gold information. Compare verified two-hop completion and
total tokens to both surgical and FULL. This must have a new preregistration
and separate immutable results; never edit or reinterpret these six cells.

Latest research protection: external held-out E2 #1346 BLOCKED_EXTERNAL and
v0.18 #1356 HARD HOLD.

# CodeGraph Graph Frontier verified-producer continuation E1 — preregistration

Created 2026-10-23 **before** inspecting any NEW continuation-treatment model cell.
Parent issue #1735, parent Graph Frontier PR #1734, measured negative
control: GitHub Actions #39963346195.

## Baseline (frozen, actual)

Host-attested staged Graph Frontier (no continuation cue) obtained strict
two-source-hop completion 0/6 across pinned Qwen3-0.6B/1.7B EN/KO/JA.
Qwen3-0.6B: zero actual source callbacks, premature final, 399–402 total
model tokens. Qwen3-1.7B: exactly one original verified producer callback
followed by premature final with consumer offered, 882–884 total tokens.
Contemporaneous surgical path-order Qwen3-1.7B: 3/3 correct, 5359–5363 tokens.
FULL: 2/3 correct, 2142–2151 tokens. The failed Frontier shortcut is not
an end-to-end efficiency gain. These observations remain immutable.

## New separate testable hypothesis

A **generic phase-specific prompt** emitted exclusively after a host-attested,
actual successful original producer callback will increase native 2-hop task
completion without exposing a consumer route ID, argument, observation
contents, private fields or oracle gold to the model. The prompt is
model-only: never executable authority. The original stage-restricted menu,
strict original parser, read-only executor and exact binding checks remain
unchanged. A premature final remains a failure. No auto-route/argument repair.

Preregistered source: fixed owner-authored joined four-route local original
registered read-only fixture; strict K=5; five model turns, GitHub Actions
Linux CPU; the same pinned Qwen3-0.6B revision
c1899de289a04d12100db370d81485cdf75e47ca and Qwen3-1.7B revision
70d244cc86ccca08cf5af4e1e306ecf908b1ad5e; languages EN/KO/JA.
One local task per language/model (N=6 cells), no hidden E2 or remote
external source. The previous five arms remain bytewise-equivalent
(unmodified prompts, original source callback receipts, denominator 1).
Add only sixth opt-in `graph_frontier_cued_e1` alongside unmodified
`graph_frontier_g5_e1` as a within-run control.

## Required outcomes and falsification

Primary: two actual original read-only callbacks in verified producer→consumer
order **and** correct independently scored final JSON, not mere CI success.
Record per-cell strict final task, attempted/actual calls, cue count,
termination, tool menu sizes per turn, schema requests, input/output/total
model tokens, model turns and model latency. Input token counts already
include native tool schema tokens; never sum that subset twice.

Cue may appear **once**, only after a real verified producer call and before
the next model generation; none for early final, denied/failed source call
or completed source path. Current offered native definitions are the
only tools available to the model; consumer cannot be executed first.
If cued frontier still fails or loses strict correctness relative to
surgical baseline, this ablation fails. If cued frontier succeeds yet costs
more than contemporaneous FULL (2142–2151-token historical range), it is
NOT an end-to-end FULL token cost improvement. One owner-authored local
scenario × three linguistic renderings is not independent E2.
Do not retroactively modify parent #1734 results.

Release gates: #1346 external E2 BLOCKED_EXTERNAL; #1356 v0.18 HARD HOLD.

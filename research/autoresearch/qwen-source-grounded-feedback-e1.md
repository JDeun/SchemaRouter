# Real Qwen3 source-grounded completeness feedback — opt-in E1

Issue [#1578](https://github.com/JDeun/SchemaRouter/issues/1578);
parent source retry [#1575](https://github.com/JDeun/SchemaRouter/pull/1575);
original live baseline [#1573](https://github.com/JDeun/SchemaRouter/pull/1573).

## Observed defects, not task-gold intuition

Actual original public Open-Meteo + pinned Qwen3-0.6B repeated
EN source geocoding success then **premature_final** without real weather
GET. One live run also produced JA two actual source observations but
a final JSON that failed exact source-factual verification. These
failure types are distinct from confirmed KO **connect_timeout** on the
live original provider, which is NOT an agent-planning failure and
cannot be repaired by an agent host prompt.

A prior generic reminder on exposed *synthetic* two-step tasks
[#1507](https://github.com/JDeun/SchemaRouter/pull/1507) remained
0/3 in its original observation; it is NOT cited as supporting
evidence for this candidate. This experiment may similarly fail.

## Single opt-in intervention

`host_completion_feedback_budget=1` (default **zero**) allows the
host to append **ONE** generic task-completeness note to the model
conversation only if the model voluntarily submitted a final after
at least one valid original provider observation, and either source
steps are missing or the strict exact final source-value oracle rejects
the final response. The feedback contains **no next tool name,
argument, location, temperature, timestamp, secret, permission,
gold label or externally unseen source field**.

Only the model can produce a later tool call, arguments and final.
The original SchemaRouter planner/executor/authorization/data-scope
checks and previous observation field projection remain untouched.
A repeated premature/incorrect final is a FAILED task. Source
connection/timeout/invalid schema, unauthorized route, malformed
model tool call and model context exhaustion remain failures without
a retry. No feedback if no prior verified observation exists.
Hard cap `MAX_TURNS=4`, one note, no background loops.
Same feedback budget and source retry budget 1 in BOTH
`all_visible` and `state_ready` original public source E1 arms.

Actual task scoring remains strict original Open-Meteo geocode →
source-projected dynamic coordinates → forecast → JSON exactly equal
to that arm's own original provider observation. No hidden host
postprocessing fills final values; no mock passes count as actual Qwen
success. Report per-language actual HTTP attempts, validated provider
results, feedback notices, model turns, strict final correctness,
and termination reason. Dynamic original weather can drift.

## Evidence boundary

This is still **three exposed E1 DEV tasks**, not original provider-
reviewed private EN/KO/JA E2, independent Recall@5, proper
calibrated no-fit or production agent recommendation. A bounded
host-completeness reminder tests an agent *host* intervention, not
SchemaRouter retrieval capability or native graph recall.
Default `retrieve_authorized`, #432 frozen negative and v0.18
#1356 release HARD HOLD unchanged. #1346 / #1477 E2 0/19.

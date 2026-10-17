# Real Qwen3 Agent × real E5 fixed-K5 paired operation DEV — not E2

**Date:** 2026-10-17. **Scope:** #1477 integrated evaluation,
not a separate candidate ranker project.

## Why this exists

Merged #1484–#1488 established that genuine
`intfloat/multilingual-e5-small` improves supported K5 Recall on a
disclosed synthetic corpus, request-local source capture can lower CPU
latency, and its model-visible metadata is now sealed. None of these
retrieval metrics demonstrate what happens after an autonomous agent
receives tools. The canonical #432 frozen independent downstream
failures remain SR-5 29.19%, FULL 49.62%, ORACLE 70.98%.

This small experiment **actually runs local Qwen/Qwen3-0.6B**
(revision `c1899de289a04d12100db370d81485cdf75e47ca`),
together with a separate **locally loaded real E5 CPU** model
(`fd1525a9fd15316a2d503bf26ab031a61d056e98`)
on GitHub Actions Ubuntu 24.04. It uses the same
`run_generated_episode` and `FrozenCorpusExecutor` from the
previous agent evaluation; it does **not** introduce a new agent
execution loop, scored fixture simulator, model stub or hosted API.

## Fixed prospective pilot

Original already published `benchmarks/multilingual-embedding-cpu-dev-20261015.json`
has exactly 84 cases, 48 supported and 36 unsupported, in six
languages with registered 13 read-only tools. The original SHA256
`dc8b0a7c9325c8767d9b323b24040e0dfe94f3fd170b829b6f977c0e629b2110`
and exact canonical parsed object must agree before any model is loaded.
The *predeclared 12 tasks* are:

| Language | Supported source cases | Unsupported source cases |
|---|---|---|
| EN | materials.search, papers.search | materials.delete_sample, papers.submit_paper |
| KO | weather.current, inventory.lookup | inventory.adjust_stock, flights.book_ticket |
| JA | flights.search, finance.convert_currency | finance.transfer_money, calendar.create_event |

These are a **convenience DEV selection from already published cases, not
fresh independently authored cases or publisher-provided holdout**.
All arms use the same original source-registered 13-route
authorization view, principal, text query, final model,
max K=5 and deterministic runner seed. Lexical K5 comes from actual
native authorized retrieval, E5 K5 from the opt-in bounded fixed5
selector and hybrid K5 from previously frozen RRF60. Their order is
rotated deterministically per source task to reduce warmup bias.
The retriever sees original query + source-native metadata only;
no gold route, supported label, fixture step or secret state.

## What the existing executor can and cannot measure here

The original published retrieval corpus identifies a correct route
but **does not publish argument gold, provider response, real
operation permissions, facts, multi-step state transitions or a
final-answer oracle**. For supported cases the fixture is **exactly
one zero-argument registered read operation** with a deterministic
minimal `{"status":"ok"}` result. For unsupported cases the
fixture has zero permitted operations; its pass condition is no
successful tool execution plus a literal `REQUEST_MORE_TOOLS`
agent final response. The unchanged agent loop still parses tool
calls, validates schema and availability, executes attempts with
the canonical frozen fixture, handles observations/turns, and scores
post-execution only. This is useful first evidence of an actual
model-agent's use or non-use of the ranked operations, but **not full
factual final answer correctness**, not argument/field accuracy,
not live native-provider execution, and not end-to-end business task
success.

The report is derived solely from original `sanitized_e0_trace`
per-task HMAC IDs and `aggregate_paired_e0` with stratified paired
bootstrap; it contains only allowlisted operation completion,
unsupported actions, generic failure stages, token counts, CPU
timings and exact model/source provenance. It deliberately omits raw
queries, arguments, semantic task IDs, private observations, gold
tool-route names, completion text and any hidden chain of thought.
The secret HMAC key is ephemeral and never exported. A stub-injected
test path can **never** identify itself as a true model measurement;
only the CLI path that actually instantiates both pinned models may
set its real-model flags. The program will reject any no-call
security-boundary exception rather than reinterpret a forged
selection as task success.

## Acceptance and next gate

The exact 12-task denominator, three complete K5 arms and all
languages must remain present, and unauthorized destructive
executions must be zero. Record **negative/zero completion honestly**.
No post-hoc task substitution, gold-aware shortlist fill or K
expansion. A successful E0 run does not promote the default route,
prove no-fit calibration, resolve publisher-native E2, or authorize
v0.18.0. The next work is #1346 genuine externally authored
EN/KO/JA/OOD + missing-input + forbidden native records with real
typed arguments/responses, and stronger end-to-end agent completion
and independently reviewed permissions. #1356 release HARD HOLD;
#432 frozen previous negative evidence is unchanged.

Run modes:

```sh
python -m scripts.research_real_qwen_e5_agent_fixture_dev --mode validate
python -m scripts.research_real_qwen_e5_agent_fixture_dev --mode real-cpu \
  --out artifacts/agent-fixed5-qwen-e5-cpu-dev/report.json
```

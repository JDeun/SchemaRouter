# Original Algorithm 1 A7 Understand Metering Implementation Plan

> **For agentic workers:** TDD against the existing A5 scoped-agent episode.

**Goal:** Quantify the extra model stage without confusing input/output
tokens, schema bytes, and agent wall time or using proxy token counts.

**Architecture:** new `scripts/research_paper_measured_episode_e0.py`
wraps exactly one A5 model callback and delegates all source checks and agent
turns to the existing implementation. The result is an explicitly E0
structured, sanitized measurement receipt.

**Tech:** Python 3.12, async callback, pytest, Ruff and Pyright.

## Task 1: observable callback metering

**Files:** new measurement script and its tests.

- [x] RED: reported provider usage yields separate Understand/agent counters.
- [x] RED: no provider usage yields absent token counts, not zero.
- [x] RED: invalid usage, repeated callback, no offered tool, callback failure
  and post-call policy/source drift cannot publish a fake successful metric.
- [x] GREEN: compose the existing A5 episode; do not replace its executor.
- [x] RED→GREEN: separately account for the JSON UTF-8 bytes actually
  supplied to the Understand model and each existing agent turn.
- [x] Verified synthetic real-principal fixture, original fixed5 two-turn
  counts, host empty menu, invalid provider usage, policy drift, repeated
  callback, fail-closed model exception and adjacent regressions. Ruff and
  targeted Pyright pass locally; protected Python3.12 CI remains separate.

## Task 2: record evidence / next external stage

- [x] Documented local usage/latency limits and qualified E0 code head
  `c4466c08`: 29/29 workflows passed, Linux Python 3.12 6423 passed /
  3 skipped with 85.00% coverage. Docs-only follow-up commits require a
  separate HEAD check.
- [ ] A7 remains unchecked until same-model paired independent evaluation,
  Linux Python3.12 cross-condition evidence and actual provider counts.

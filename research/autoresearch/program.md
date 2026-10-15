# SchemaRouter AutoResearch: bounded agent research program

This document is an experiment contract, **not** a claim that an LLM coding
agent already edits and tests code autonomously. The baseline is current
SchemaRouter typed capability retrieval, planning, registered adapters and
governed execution, NOT historical frozen 0.14 code or a 9-label intent model.

## Objective

Improve the quality, multilingual coverage, context exposure and CPU/runtime
trade-offs of typed capability selection used by an external host/agent.
Preserve host-owned intent, principal and authorization semantics. Candidate
research cannot grant tool execution authority.

## Editable surface: one file

Only research/autoresearch/candidate.py may be modified by the research agent
for an experiment. Its public function is rerank(query, candidates) and it
returns the exact registered input candidate route IDs in a different order.
The trusted evaluator rejects omissions, duplicates and invented IDs.

The input includes query plus publicly registered endpoint descriptions,
scores, fields, read/write metadata, and route IDs, never gold answers,
private principal scopes, outside test cases or sensitive data. This first
adapter only rearranges already-retrieved top-24 capabilities; it cannot
recover a capability missing from the initial candidate pool. Changes to
retrieval breadth, field projection, or progressive exposure need separate
reviewed interfaces.

Do not modify the frozen-side scorer, benchmarking code, case gold, worker,
CI security boundary, product source, schema identities, or release process
in an AutoResearch trial.

## One experiment step

1. Record checkout Git SHA, hypothesis, candidate SHA-256 and budget.
2. Make a small algorithmic edit to the permitted candidate file.
3. Run the guard tests and paired benchmark on the same existing development
   cohort, current product build, hardware, candidate pool and Top-K sizes.
4. Compare required-route Recall@3/5/10, all-route FullCoverage@K,
   each language at each 100/250/500 catalog size, payload bytes and
   candidate IPC latency. Retain all failure cases.
5. The current DEV controller marks KEEP_RESEARCH_CANDIDATE only if
   Top-5 found-route count rises, no language-and-size cohort loses found
   routes or full coverage at any K, candidate IPC p95 stays <=20ms, and
   candidate output bytes do not exceed 110% of baseline. Otherwise it marks
   DISCARD_OR_REVISE. These research thresholds do not imply commercially
   qualified performance.
6. A research-only KEEP never merges production code or qualifies releases.
   Revert a failed experiment to a known research champion. Maintain trial
   history and continue from observed gaps within compute and trial caps.
7. Stop on safety, provenance, corpus or budget violation. A finite
   autonomous search cannot establish mathematical global optimality.

## Run the current stage on disposable Linux CPU

    python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
    python -m pytest -q tests/test_research_autoresearch_sandbox.py
    python -m scripts.research_autoresearch_sandbox --sizes 100 250 500 \
      --cases-per-group 1 --output artifacts/autoresearch-sandbox/report.json
    python -m scripts.research_autoresearch_trial \
      --description "one bounded research hypothesis" \
      --output-dir artifacts/autoresearch-trials

The shipped candidate is an **identity ranking control**. Expected result
is zero retrieval quality gain and DISCARD_OR_REVISE; this is evidence of
a working genuine test harness, not a new research breakthrough.

## Claim and security boundaries

- The cases are **pre-exposed synthetic #430 DEV**, not a fresh split, real
  heterogeneous provider deployment, blinded confirmation, live authorization
  fixture, required-output-field gold or downstream agent task outcomes.
- The evaluator fetches 24 current candidates per request and computes
  K=3/5/10 slices from the same ranked pool. Smaller-K timings are not
  separate executions, and candidate JSON bytes are not actual prompt tokens.
- A raw shortlist on an unsupported query is not a wrong tool execution.
  Neither the worker nor scorer calls SchemaRouter.execute.
- Editable Python is arbitrary executable code. A subprocess with a clean
  environment is **not** a complete security sandbox. Never run candidates
  with secrets, a writable GitHub token, production data or hidden holdouts.
  Use ephemeral read-only runners; harden with container/OS network and
  filesystem restrictions before running potentially hostile generated code.
- A one-trial local controller is included: it runs the registered
  guarded test and scorer, appends research status/history, and restores
  only the allowed candidate file from committed HEAD on DISCARD/CRASH.
  Run it in a disposable branch/worktree, not a working tree with valuable
  uncommitted candidate changes. It does not push or merge.
- Hypothesis generation, LLM-based source edits and persistent continuation
  across GitHub Actions jobs are **future implementation**. A per-run JSONL
  artifact is not a durable cross-run database or automatic ongoing agent.
- Build genuine fresh current-adapter query-disjoint train/DEV cases with
  principal allow sets, required-field gold, multi-route chains and an
  independently authored protected confirmation suite. Compare true
  FULL/SR-K/SR-PROGRESSIVE/ORACLE agent task completion before suggesting any
  product replacement or commercial-grade quality claim.
- Historical negative independent research stays immutable, and the pending
  v0.18 #1345/#1346 release gate stays HOLD.

Follow-up tracked at https://github.com/JDeun/SchemaRouter/issues/1412

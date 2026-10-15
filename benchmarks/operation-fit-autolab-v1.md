# Operation-Fit AutoLab v1 — bounded recurring DEV experiment loop

> **Research automation, not autonomous code development.** This runs only
> pre-registered local experiments, analyzes measured errors, selects another
> registered hypothesis and repeats. It never writes application code,
> generates or merges PRs, publishes packages, or grants tool execution.

## Why the old conveyor was insufficient

The original #1402 experiment conveyor (and #1404 diagnostics) accepted
PR/manual triggers and generated a development `opportunities.json` report.
It did **not** automatically consume its suggestions, run another model
variant or track which hypotheses had already been measured. AutoLab v1 adds
a distinct finite *iteration controller*, keeping the original frozen v0.14
research, the #1402 pipeline and held v0.18.0 release untouched.

## Schedule and actual iteration

`.github/workflows/research-operation-fit-auto-loop-dev.yml`:

1. Runs offline safety/unit tests on relevant PRs without a model download
   or write access to GitHub issues. On a merged `main` push affecting this
   workflow, on manual dispatch, and weekly **Monday 02:17 UTC**, it also
   retrieves the latest bot-authored cursor comment from #1405.
2. Validates corpus SHA, locked model/checkpoint, all prior metrics and
   issue-state identity. Stops without downloading weights if all three
   variants have already completed. A malformed bot cursor fails closed.
3. Loads the pinned MIT-licensed local multilingual NLI MiniLM model on
   GitHub Actions Linux CPU, no paid APIs. The previous DEV error signature
   `directions` concentration (50/72) initially prioritizes matching
   hypothesis language. Subsequent results determine whether to focus on
   false acceptance or another untried registered variant.
4. Executes **at most two** variants per run, records 72 per-case outcomes
   per variant (54 supported, 18 unsupported; EN/KO/JA), class-dominance,
   wrong operation, false refusal and unsupported false acceptance. Stores
   immutable run-linked JSON in the GitHub Actions artifact.
5. Closes **only** experiment-specific measurement issues created and
   identified as owned by `github-actions[bot]`, with complete metrics and
   evidence links. Comments the latest bounded progress/state back to
   parent #1405. The next scheduled run resumes from that cursor.

Registered hypothesis variants in
`benchmarks/operation-fit-auto-loop-v1-plan.json`:

| Variant | Scoring | Role |
| --- | --- | --- |
| `language_aligned_entailment` | NLI original multilingual user premise, 9 hypotheses matching EN/KO/JA language, raw entailment >= 0.70 | Test whether hypothesis-language alignment reduces the prior `directions` concentration |
| `signed_entailment_minus_contradiction` | Same hypotheses, entailment minus contradiction >= 0.25 | Explore high false-accept vs refusal without retuning on observed DEV examples |
| `signed_plus_lexical_negative_veto` | Signed NLI plus conservative language-pattern disagreement/negative veto | Explore explicit negative guards and cost of legitimate refusals |

All thresholds and phrases are fixed in source **after** earlier development
results were observed. They are **not statistically calibrated**, and neither
better numbers nor completion of the three trials qualifies a model.

## Issue automation boundary

The workflow receives `contents:read` and `issues:write`, but its
issue-sync script has fixed repository identity, titles, narrow ownership
markers and a 72-case evidence check. It can create/close only
`[AutoLab DEV] Measure <allowlisted_variant>` issues that its own
GitHub Actions bot authored. A human-authored issue with a colliding
title/marker is **never** closed. No other existing issues are closed.

#1291, #1339, #1346, #1356 and #1403 stay open until their **entire**
acceptance criteria are independently met. #1405 acts as the research
checkpoint parent and remains open. The user does not need to manually
dispatch an already registered trial once this workflow is on `main`.

## Limits and next extension point

- **Finite known search**, not an LLM inventing indefinite new candidates.
  After three variants it becomes an inexpensive weekly no-op. Another
  candidate must be explicitly registered with reproducible evidence,
  cost budget and fixed hypotheses.
- All 72 samples have been repeatedly seen by developers. Iterative
  gains on these samples are only *hypothesis-generation signals*.
- No externally annotated independent holdout or actual 100/250/500
  provider tool graph is enabled. Those experiment registry entries remain
  **blocked** until suitable data and review are available.
- Model weights are pinned to HF revision
  `0a71e92a985b6e1ad1828cf67ce9c459639c1dca`; a separate byte-level
  attestation has not been established.
- One failed Actions run does not persist a success cursor. The next run
  may retry that measurement, and issue-sync searches existing owned
  issues to avoid duplicate **scope** records. Protected GitHub settings
  and hosted-runner quota may pause scheduled execution.
- The original DEV conveyor and release HOLD do not rely on this loop.
  No model prediction, heuristic or bot issue closure is a security
  authorization or release approval.

**No autonomous PR merge**, no automatic code changes, no training, no
frozen v0.14 evidence reuse, and no v0.18 release promotion.


## Registered benchmark completion reconciliation (2026-10-16)

Issue-bound benchmark scheduling has **two distinct statuses**:

- `DISPATCH_REQUESTED_NOT_BENCHMARK_SUCCESS`: the fixed allowlisted workflow was
  requested from the original AutoLab workflow and the bot wrote a dispatch
  receipt in parent #1405. This must **never** be counted as a successful
  benchmark.
- `COMMENT_ONLY`: a separate
  `.github/workflows/research-benchmark-evidence-reconcile-dev.yml`
  `workflow_run: completed` listener confirms an allowed **successful**
  workflow-dispatch event from `main`, an exact matching source commit and
  bot-owned dispatch receipt, and one nonexpired expected artifact belonging
  to that run. It then comments the evidence link on the corresponding original
  issue (#1208 or #839), without closing it or judging independent quality.

The listener only reads the triggering completed run; it does not check out
untrusted PR code, execute the benchmark output, run models, dispatch other
workflows, merge PRs or grant release authority. A repeated webhook is
idempotent using a bot-owned `schemarouter-benchmark-confirmation-v1` marker.
Missing/expired artifacts, incorrect source, failure/cancellation, unknown
workflows or unmatched bot receipts fail closed. Existing historical runs
that predate this listener can be documented manually with verified Actions
links; the listener must not retroactively fabricate qualification.

**Important:** A successful development-only ClicShopping or Clear Your Tools
workflow does not complete the parent issue's independent evaluation and
real-agent gates. Those issues remain OPEN pending their stated acceptance
criteria. Product/code work and v0.18 HOLD are unaffected.

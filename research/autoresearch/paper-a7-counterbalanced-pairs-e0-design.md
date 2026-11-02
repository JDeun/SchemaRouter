# Original Algorithm 1 A7 — counterbalanced paired agent rehearsal (E0)

**2026-10-26.** The existing source-locked A7 pairing performs the baseline
before the paper condition. That order confounds their locally observed wall
times with warm-up/cache/order effects. The missing engineering experiment is
to execute the *same original pair* in both orders without creating a new
agent executor or mistaking source-authored fixtures for independent gold.

## Alternatives

1. **Chosen:** add a strict `execution_order` to the existing paired adapter
   and a two-order orchestration helper that runs baseline→paper and
   paper→baseline with fresh but host-matched agent instances and fresh
   Understand callbacks. Reuse existing source/owner/task guards, stage
   counters, bounded K5 and tool invocation. Return both original sanitized
   receipts, with distinct order labels and explicit E0 flags.
2. Run baseline/paper in parallel: changes provider contention and can make
   source mutation/authorization races ambiguous; not comparable to current
   sequential execution and not necessary for an order crossover.
3. Build a second benchmark executor: risks diverging fixed5 scheduling,
   authorization, agent token accounting and user-visible schema budgets.

## Contract

- New `run_paper_paired_agent_e0(..., execution_order=...)` accepts exactly
  `baseline_first` or `paper_first`, rejecting invalid values before any
  model or agent invocation. Each side still uses the original executor.
- New `run_paper_counterbalanced_agent_e0(model_factory, agent_factory, ...)`
  obtains **two distinct, same-concrete-type callable Understand callbacks**
  before running. Each pair obtains two fresh agents via the existing factory.
  All four instances must be distinct and of the same concrete class, with
  equal, strict host-declared agent/model/seed/sampling configuration.
- The first trial is baseline→paper; the second trial is paper→baseline.
  The original task digest and owner declarations are pinned **before either
  model factory is called**, checked after each factory, and checked again
  after each trial. This prevents the factory from rewriting private gold
  or owner-approved semantics before a pair establishes its own baseline.
  Source and role guards also run before/after both branches via existing
  A7/A5 proof. Failure returns **no partial crossover receipt**; results
  are not published until both pairs finish.
- Output includes **only existing sanitized pair reports and run-order
  metadata**. Raw query, model text, native gold, route/field IDs, and
  credentials must never be exported. The existing conditional `supported`
  label remains redacted in both trials.
- The result must state `independent_e2_qualified=false`. Even both orders
  cannot control cross-trial model caches, provider nondeterminism or
  independently authenticate same model revisions. It is a **two-order E0
  engineering rehearsal**, not independent EN/KO/JA model accuracy, unbiased
  latency inference, valid E2 scoring, or production/release qualification.

## Deferred external gates

Pre-registered multi-case randomized experiment ordering, publisher-original
EN/KO/JA gold, provider identity/usage receipts, license/permission review
and statistical latency bounds remain external A7/#1346/#1477 work.
Release #1356 stays HARD HOLD and Draft #1755 must not be merged on E0 alone.

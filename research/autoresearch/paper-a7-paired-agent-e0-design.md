# Original Algorithm 1 A7 — original authorized-K5 vs paper-K5 paired E0

**2026-10-26 · deliberate engineering-only extension.** The original A5
source-scoped `Understand`/plan and A7 model-stage meter are implemented.
Next compare that route selection with the **existing** principal-authorized
ranked Top-K5 result, holding the exact original source view and case fixed.
This is a diagnostic rehearsal, never independent publisher E2 evidence.

## Alternatives

1. **Chosen:** a paired adapter around the existing
   `run_generated_episode(EVAL-FIXED5-OPTIN)` and
   `run_paper_measured_agent_episode_e0`. It uses the same trusted captured
   principal-scoped native route sequence; existing ranked first five is the
   baseline, paper source-proof picks up to five in its own branch. Two
   freshly constructed agents must carry the **same host-declared** model,
   agent and sampling configuration (including an explicitly recorded sorted
   immutable sampling-parameter set). No alternate executor or source menu.
2. Reconstruct the baseline from a registry-global lexical search: leaks
   hidden/denied tools and may give unequal source budgets.
3. Share one mutable agent object across two episodes: state/caching turns
   leak between conditions, making a purported same-agent comparison unfair.

## Strict contract

- Host supplies one `AuthorizedAgentToolSurface`, a source-pinned index and
  original task. The task is deep-frozen before either branch; both episodes
  receive separately deep-copied identical input. No selector or model sees
  required routes, expected answers, private gold or executor fixtures.
- The agent factory is invoked exactly twice before execution; results must
  be different objects of the same concrete class, with identical immutable
  host-declared agent/model/seed configuration. This is a **host declaration**,
  not independently verified third-party provider or model identity.
- Baseline offers `view.visible_route_ids[:5]` from the already ranked,
  principal-filtered original retrieval, still checked by the existing
  fixed5 source membership/authorization guard. Paper calls the existing
  A7 meter/plan/agent path. Source/policy/role changes abort both branches;
  no partial paired record is published.
  The legacy agent interface presents those selected five tool definitions
  alphabetically by default; the baseline **membership** is rank-derived,
  but its model display order is not a new learned ranking claim.
- Reuse the original scoped `public_trace` and A7 sanitized timing/usage.
  The paired adapter additionally removes the original trace's per-case
  `supported` grader label from **both** returned episode records; `passed`
  is only a synthetic outcome metric, not a publisher gold record.
  Both branches count exact canonical JSON UTF-8 bytes of each actually
  disclosed agent tool-definition argument, not network-wire bytes or
  provider tokens; the paper branch also separately counts its Understand
  request bytes and optional reported provider usage.
  Return counts and provided reported usage only, never query, gold, route
  IDs, raw model text, arguments, or chain of thought.
- Report host-claimed equality and `independent_e2_qualified=false`. Actual
  provider-reported usage can be absent (`None`), never guessed. Synthetic
  pass/fail numbers must not be presented as independent quality evidence.
- The E0 rehearsal deliberately runs baseline then paper sequentially and
  validates only *reported* same-agent model configuration. That execution
  order permits cache/warm-up effects; no statistical latency/quality or
  same-model-identity inference follows. Independently preregistered,
  counterbalanced provider studies are separate A7/#1477 work.

## Deferred full A7/E2 requirements

Independent EN/KO/JA original-language gold and principal permissions,
source-native provider receipts, pre-registered metrics/denominators,
authenticated same-model runs and installed-pair Linux Python3.12 accounting
remain BLOCKED_EXTERNAL under #1346/#1477. The #1356 release is HARD HOLD.

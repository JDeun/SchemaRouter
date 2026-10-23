# CodeGraph E1 graph-path order cue — narrow protocol study

## Intent and evidence

The pinned [#1732 local Qwen run](https://github.com/JDeun/SchemaRouter/actions/runs/39949700021)
found that Qwen3-1.7B in EN/KO/JA materialized the host-authorized G5
schemas but picked a first original native action with
`unsupported_bound_path` (zero source callbacks, strict success 0/3).
Qwen3-0.6B prematurely finalized (0/3). Only the fixed categorical
diagnostics are stored; no refused arguments or model text is available.

## Candidate approaches and chosen scope

1. **Prompt-only path-order cue — this phase.** Append one static model-only
   instruction explaining that `route_sets[*].route_ids` are in dependency
   order and the first original read-only source must precede its consumer.
   Same offered original tools and exact host authority; can isolate prompt
   sensitivity, but the model can still choose incorrectly.
2. **Host-scoped Graph Frontier — later phase only if needed.** Re-materialize
   just graph-frontier original native tool definitions after verified source
   observations. May improve correctness/context costs but modifies the offered
   menu and action boundary; requires a separate design and comparator.
3. **Automatic arguments/route repair — rejected.** Would fabricate model
   decisions or bypass the source-bound checks and contaminate the study.

The next isolated, approved continuation is option 1. Do not implement
option 2 as a hidden fallback and do not promote the research variant.

## Behavior, non-goals and constraints

- Opt-in only on the exact four-route `joined` E1, strict K=5, unchanged
  Qwen3-0.6B/1.7B pinned revisions, EN/KO/JA and five model turns.
- Requires the existing one-action-per-turn and bare reserved-schema-request
  treatments. It is mutually exclusive with bare native JSON and G5
  verified continuation cue. No default/prod parser or prompt change.
- The static cue contains **no route IDs, argument names/values, actual
  source responses, hidden fields or scorer gold**; it only explains
  producer-before-consumer semantics of the already public graph reference.
- Apply only to surgical G5. FULL, lexical K5 and typed G5 arms remain
  byte-identical to their #1732 treatments.
- Source fingerprint, model/oracle, original host callbacks, principal,
  data visibility, typed observations and refusal of unbound arguments
  remain unchanged. A prompt cannot grant authority.
- Primary endpoint: strict two-original-source-hop + correct final answer.
  Secondary: schema requests, original callback count, turns, total tokens,
  malformed/unbound/premature reasons. Record negative results faithfully.
- This is author-declared local E1, not CodeGraph causal graph-index evidence,
  source-disjoint independent E2, commercial-provider qualification or v0.18
  release permission.

## Decision rule

If the prompt alone does not rescue a legitimate complete 2-hop task,
stop further micro-tuning the same prompt and separately design Graph
Frontier. Even if it succeeds, do not claim graph cost advantages without
independent paired controls and externally authored heldout tasks.

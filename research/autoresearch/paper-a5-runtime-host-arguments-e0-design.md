# A5 E0 — reviewed original-paper direct arguments at actual fixed-K5 dispatch

## Decision

The A5 scoped original-paper model/plan path already accepts a source-typed,
host-reviewed direct scalar argument in its `PaperTypedToolPlan`. However,
`run_paper_fixed5_episode_e0` exposes only route names; the unchanged
`run_generated_episode` forwards the agent's separately generated arguments
to the original frozen fixture executor. Hence a plan-level approved value
does not reach the actual call.

Chosen: add an **isolated, principal-scoped E0 dispatch hook** to the
existing `run_generated_episode`, and supply it only from the current A5
host-reviewed direct plan. It receives the agent's selected route and the
model's argument object after the original parser; it replaces **all**
arguments for the one explicitly approved, source-verified scalar root with
the host's checked values immediately before the original fixture executor.
The agent must first actually select that offered route; no host auto-call.
All other routes and omitted/non-tool actions retain their existing behavior.

Alternatives rejected:

- Instructing the agent to supply the value in the prompt/model tool schema:
  leaks host input, depends on model compliance and is not a bound ToolCall.
- Adding an A5-specific second tool executor: duplicates the frozen executor
  and invalidates paired-agent comparability.
- Applying arbitrary model hints directly: bypasses the required explicit
  host-review and original source proof.

## Invariants

- **Never** change historical frozen experiment conditions; hook requires
  `EVAL-FIXED5-OPTIN`, current authorized model view and original selector.
- A5 hook is enabled only for one `ready`, dependency-free, originally
  approved host root with nonempty complete scalar `call.arguments` from the
  existing P2/A5 compiler. No arbitrary direct alternatives, graph consumer,
  provider-supplied defaults, model `parameter_hints` or unreviewed arguments.
- Snapshot and recheck source/principal/policy/plan/route fingerprints and
  actual JSON Schema before **each** materialization. Changes during model
  generation or source lookup fail closed; the model never supplies authority.
- Do not create a ToolCall when the agent generates none. On a first, valid
  offered call to the exact route, replace the entire argument object with
  the approved root input. A different/unknown/multiple call is not upgraded
  to approved authority; the original frozen executor's existing refusal and
  one-call semantics remain intact.
- Distinguish host-assisted dispatch from independent model argument quality
  using a **coarse count** in the E0 episode trace; never expose sensitive
  host input values in public trace or claim model-derived argument success.
- This proves E0 synthetic registered-tool/frozen episode wiring only. It
  does not execute actual providers through the agent, certify publisher
  semantics/accuracy or grant product/default execution rights. Maintain
  #1346/#1477 external gates and #1356 hard release hold.

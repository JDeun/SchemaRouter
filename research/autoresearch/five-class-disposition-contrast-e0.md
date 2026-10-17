# Five-class agent disposition contrast — E0 synthetic engineering only

**Owner:** #1477 (R05 / R04); prospective external case ownership: #1346.

This is the *same* `run_generated_episode` + `FrozenCorpusExecutor` and opt-in
`EVAL-FIXED5-OPTIN` callback used by the fixed-K5 agent work. It is not a
second execution runtime, model ranking benchmark, online provider test, or
independent E2 case set. The callback receives only the ordinary query and
authorized registered route IDs. Only the **trusted assessor after execution**
supplies a class label, never the selector or agent.

The original agent fixture grader is *binary*: supported with expected
operation or unsupported with an exact refusal final. Reusing
that passed boolean to grade a request that **needs additional input**,
is **ambiguous**, or is **forbidden by host policy** would silently misclassify
a correct non-call response as a failure. This separate post-execution
engineering diagnostic distinguishes:

| Source-author disposition | Required agent behavior in E0 |
| --- | --- |
| supported | Required fixture operations consumed and agent final observed |
| unsupported | No tool attempt; exact REQUEST_MORE_TOOLS final |
| needs_input | No tool attempt; exact REQUEST_INPUT final |
| ambiguous | No tool attempt; exact CLARIFY_REQUEST final |
| forbidden | No tool attempt; exact REQUEST_DENIED final |

The tokens are **test protocol constants**, not a production language or
model-dependent policy. In particular a user/model is not authorized to
choose which class is forbidden; the host must assign and review it.

The scorer rejects malformed attempt counters, missing turns, incompatible
source support labels, and an attempted call followed by a refusal. It exports
only coarse observed classes/counts, not user text, gold task/routes, action
arguments, raw observations, hidden fields, or assistant answer text. The
existing original binary grader result and frozen #432/#424/#506 datasets
remain unchanged.

## Validity limits and stop criteria

- This is five *self-authored synthetic* contrastive cases, scored with a
  deterministic no-model agent. A green CI means protocol behavior only.
- No multilingual model comprehension, real OOD classification, task-final
  factual accuracy, provider invocation, or negative-control calibration.
- A correct reply that follows a tool attempt is **not** a strict no-call.
- A confused or hostile model may still call a candidate; this harness only
  measures, never authorizes or executes a real provider.
- Independent E2 qualified and release safety gate both remain false.
  Keep qualification ledger R05 NOT_VERIFIED until sealed EN/KO/JA cases
  and independent approvals exist under #1346.
- Do not change SchemaRouter default routing or v0.18 release #1356 HOLD.

## Run on GitHub Actions Linux CPU

Run Python pytest on tests/test_research_agent_disposition_contrast_e0.py.

The workflow is separately named **E0 Five-Class Agent Disposition Contrast**
and must run alongside, not replace, the actual-Qwen/E5 fixed12 pilot.

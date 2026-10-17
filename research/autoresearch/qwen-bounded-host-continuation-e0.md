# A02 bounded host-attested incomplete-task continuation — separately preregistered E0

**Prerequisite:** original model-proposed, real bound executor study #1506.

Source-exposed [actual Qwen run 39029981154](https://github.com/JDeun/SchemaRouter/actions/runs/39029981154)
verified an exact repeated negative in all three languages: English,
Korean and Japanese each completed one valid actual Router.execute
bound read, then **emitted a premature final answer** rather than
generating the second dependent tool call. The strict task completion
was 0/3. No malformed tool calls or authorization denials explained the
three early final exits. The original no-retry observation and prompts
are **frozen** and must not be rewritten.

## One material change

This successor is a *separate* opt-in E0 protocol variant. If and only if
(1) a first read-only real host invocation completed, (2) the user
requested verification has **not** yet been observed in a trusted
second-step host result and (3) the model emits a premature final,
the host may return **one** generic TASK_INCOMPLETE reminder.
The reminder discloses **no route name, required second-step argument,
expected record ID, oracle result, authorization grant or gold step**.
It is a state-based request-progress signal from the existing trusted
host, not a model-supplied grader. It never changes the source/gold,
model weights, initial user prompt, tool definitions, final-answer
scorer, native provider binding or route authorization.
Default `--host-continuation-budget=0` is unchanged.

Before any subsequently proposed model call, the trusted host still
checks authorized source, native schema and actual RBAC. A wrong call,
stale authority or hallucinated final cannot be promoted to a pass.
No continuation occurs when the model executes zero calls, and a second
premature final fails rather than triggering an unbounded agent loop.

Model-selected tool arguments, projected first-step state and the
strict typed final verification are measured by exactly the same E0
oracle as #1506. The run is limited to four model turns and at most
one host reminder. Results are reported per language with safe
categorical termination codes, host call counts and final task pass.
Original three-case **0/3 negative** remains visible separately.

## Interpretation

A successful new run would establish that a single generic reminder
can improve **disclosed synthetic** multi-step completion in this
one setup. It would not prove good independent multilingual request
understanding, real external provider reliability, no-fit calibration,
stateful adversarial safety or commercial task-level quality.

**A02 NOT_VERIFIED, R05 NOT_VERIFIED, 0/19 independently E2 qualified,
v0.18 release #1356 HOLD, default-model promotion HOLD.**

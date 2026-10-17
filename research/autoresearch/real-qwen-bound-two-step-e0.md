# A02: actual Qwen model proposals into two real bound Router.execute calls — E0 DEV

**Owner:** #1477. **Baseline:** merged #1505 (deterministic, host-written two-step sequence).
This successive experiment changes one material factor: **the local model, rather than
the host, proposes each route and typed arguments at the exact agent turn.**

## Preregistered disclosed synthetic experiment

The trusted test host registers two read-only sources:
marine.read(place: string) returns a public record_id, and
papers.read(record_id: string) returns a public verified boolean.
It additionally registers a denied vault route and a hidden secret field;
**neither** may appear in model-visible tool definitions or projected observations.
These are synthetic in-process bound host providers routed through real
SchemaRouter authorized planner and RegistryExecutor, *not external provider I/O*.

Pinned local Qwen3-0.6B receives one natural-language public request in English,
Korean, or Japanese. The model chooses the next tool name and JSON arguments.
Only principal-visible route definitions and redacted observations appear in
its messages; the hidden host oracle, required step order, expected arguments,
gold record ID, policy details and task grader are NOT supplied to the model.

One proposed call is parsed per turn with exact whole-turn ChatML/XML framing,
one optional canonical Qwen end marker, finite bounded primitive arguments and
no duplicate or partial tool calls. A trusted host requires marine first and
papers second and rejects untrusted or wrong-order proposals before I/O.
Existing execute_scoped_host_call performs the full actual reauthorization,
planner and source fingerprint checks before each bound host invocation.
A fresh principal source snapshot is captured each turn and the second
record_id must be generated from the publicly projected first observation.

A task is **correct** only when (1) two actual bound host reads occurred in
the correct order with valid typed arguments, (2) the trusted host boolean
verification oracle is true, and (3) the model returns a strictly matching
final JSON {verified: true} (with one canonical decoder EOS marker permitted).
One good call or an invented final answer cannot count as complete.
All original task text, tool arguments, record IDs, private fields, model text
and oracle details stay in-process. Only per-language counts and booleans
are exported.

## Fail-closed tests and validity limits

- Wrong route order, nonexistent or denied route, incomplete or hidden/extra
  fields, malformed JSON or arbitrary/duplicated ChatML are rejected before I/O.
- Host policy object replacement or in-place rule revocation before step 2
  blocks the second provider read. First bound read is *not* rolled back.
- Private field/secret canary may not occur in model input or returned report.
- Tests use scripted delegates; only the CLI which actually loads the pinned
  Qwen model sets real-inference flags and real-model evidence tier.
- Exposed, host-authored case strings; just 3 prompts; only 2 allowed
  read-only routes; a strict binary final oracle rather than open-ended factual
  citation assessment. Negative model results are retained and not tuned.
- This is neither independent publisher-authored native provider E2 nor proof
  of general EN/KO/JA comprehension. There is no calibrated no-fit, original
  external provider, live mutable operation, latency SLA, or adversarial holdout.

**Qualification remains A02 NOT_VERIFIED, S02 ENGINEERING_ONLY, 0/19 E2,
v0.18 #1356 HARD HOLD and default model promotion HOLD.**

Reproduce source/guard: python -m pytest -q tests/test_research_real_qwen_bound_two_step_e0.py.
Run pinned real Qwen on GitHub Actions Linux CPU: Real Qwen Two-Step Bound Host E0 DEV.

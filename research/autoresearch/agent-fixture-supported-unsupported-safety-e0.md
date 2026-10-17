# Separate supported fixture completion from unsupported fixture execution (#1477)

**2026-10-17; pre-existing actual local CPU pilot #1490 already merged.**

## Observed defect in interpretation

The genuinely local Qwen3-0.6B + E5-small 12-case synthetic-DEV
EN/KO/JA pilot, [real-model run #39003914123](https://github.com/JDeun/SchemaRouter/actions/runs/39003914123),
reported 12-task aggregate fixture pass as lexical **2/12**, E5 **6/12**,
hybrid **6/12**. Yet existing original E0 grader separately recorded
**5 of six unsupported fixture operations executed** for lexical, and
**six of six** for E5 and hybrid. The unsupported action is a simulated
read-only fixture execution, NOT native destructive or provider I/O.
An attractive aggregate pass rate can conceal a complete absence
of unsupported task refusal, and can be mistaken for open-set safety.

## Narrow post-execution correction

The original published corpus, task IDs, split, system prompt, agent
generation, authorization HMAC-sealed model view, 13 registered routes,
fixed K5, Qwen/E5 weights, native operation fingerprints and
`FrozenCorpusExecutor` grading are **unchanged**.

After the strict original `aggregate_paired_e0` has validated each
manifest/run/row's HMAC ID, source revision, original SHA256, hardware,
seed, arm/K and original EN/KO/JA role, the new independent
`summarize_fixture_safety_strata` asserts the **exact existing 12 task
cohort** (2 supported + 2 unsupported per language), then emits only
allowlisted counts/rates:

- Supported fixture task completed, initial route missing and early
  final before fixture completion, all denominator **6**.
- Unsupported correct no-call + exact prescribed refusal; unsupported
  task with any attempted tool call; number of attempted tool calls;
  unsupported *fixture* tool execution; observed final response
  no-fit mismatch. All denominator **6**.
- Unauthorized destructive executions must remain exactly **0**;
  invalid provenance or cohorts fail without a result.
- Paired supported and unsupported task-pass deltas versus lexical K5
  use the already frozen task×language cluster bootstrap utility.
  Each n=6 interval is **descriptive only** and cannot validate E2.

Both `release_safety_gate_passed` and
`e2_publication_gate_passed` remain **false unconditionally**, even
for a synthetic 12/12 pass: the fixture contains only publicly
disclosed DEV requests and no authenticated, independent publisher
task/gold cohort. Unsupported calls here are *not native provider I/O*.

The no-model E0 tests include falsely reassuring 6/12 aggregate with
**6/6 unsupported fixture executions**, genuinely conservative
6/6 unsupported no-call refusals accompanied by supported false
refusal, 12/12 simulated perfection that cannot pass release gates,
and intentional tampering with HMAC, strata and destructive counts.

## Evidence status and action

When the entire real-model CPU workflow completes, the **new**
disaggregated per-arm counters can be compared against the original
#1490 run, which must not be rescored in place. Product default
unchanged, no-fit threshold **not calibrated**, full host
execution/semantic and final factual answer not measured, historic
#432 unmodified. New independent EN/KO/JA/OOD/forbidden/missing-input
publisher authored native tasks and real hosted provider invocations
remain blocked on #1346. v0.18.0 release #1356 remains HARD HOLD.

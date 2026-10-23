# CodeGraph Qwen E1: post-generation action-shape diagnostics

**2026-10-23 · #1723 · E1 research-only · stacked after #1722 · no new execution authority**

## Why

The original strict host parser and original source executor correctly refuse
unsupported model actions. Genuine Qwen3-0.6B and Qwen3-1.7B EN/KO/JA
four-route runs nonetheless completed zero 2-hop tasks: most generated a
premature final answer; in the 1.7B KO/JA surgical arm, one authorized schema
request was followed by a malformed action. Those observations cannot
distinguish a model refusal from a ChatML/JSON envelope mismatch without
an additional **privacy-safe structural** probe.

## Immutable model/scorer boundary

The opt-in flag `--diagnose-model-actions` is a **post-generation sidecar**.
It does not change prompts, output text, model checkpoint, sampler, messages,
chat template, offered native tools, parsing, route selection, original
authorization, source fingerprint, source-call count, task gold or final
oracle. The pre-existing `parse_one_model_action`, surgical `_parse_action`
and `execute_scoped_host_call` remain the sole acceptance/execution gates.
There is **no model retry, JSON repair or lenient tool execution**.

Only these **fixed, non-content labels** may appear under
`action_structure_labels`, once per already completed model turn:

- Final without a tool request (distinguishes before schema, after schema,
  after native call), bare JSON final or bare JSON resembling a tool action.
- Tool envelope incomplete, multiple calls, unexpected ChatML wrapping,
  invalid or duplicate-key JSON, non-object payload, extra envelope fields.
- Malformed/unoffered native name, arguments not an object, non-scalar
  arguments (including NaN/Infinity), valid scoped schema request *shape*,
  or a syntactically valid offered native call *shape*.

Shape labels do **not** certify authorization, schema completeness, bound
source arguments or task success. These are independently enforced by the
original host. No model text, instructions, tool names, argument values,
principal, raw response, hidden field names, HMAC material or parser exception
is copied to JSONL, report, CI output or research notes.

## Reproduction

```bash
python -m pytest -q tests/test_research_codegraph_action_shape_e1.py tests/test_research_codegraph_local_multiroute_e1.py tests/test_research_codegraph_surgical_agent_e1.py
python -m scripts.research_codegraph_local_multiroute_e1 --cohort local-source --catalog-size 4 --language ko --diagnose-model-actions --out /tmp/codegraph-06-action-shapes-e1.json
python -m scripts.research_codegraph_qwen17_local_e1 --cohort four-route --language ko --diagnose-model-actions --out /tmp/codegraph-17-action-shapes-e1.json
```

Dedicated GitHub Actions replay **the same pinned 0.6B and 1.7B model
settings and original four-route synthetic cases**, with the diagnostic sidecar
added, not a new prompt treatment. Compare source-call counts, task outcomes
and model token receipts against original actions run IDs
`39922466111` and `39923618201`. A category difference may identify an
action-envelope incompatibility; it cannot retrospectively create a task
success or attribute one to CodeGraph.

## Follow-up decision gate

If an actual-model category identifies a well-formed, single, currently
offered native action in an alternate model envelope, preregister a **separate**
opt-in grammar variant with exact bound semantic equivalence, independent
strict-parser tests and original authorization checks. No automatic grammar
normalization is authorized by this diagnostic stage.

Independent publisher E2 (#1346) remains blocked and v0.18 (#1356) stays
HARD HOLD. All task success and token-savings promotion claims remain held.

# Qwen-Agent Nous protocol: source-pinned E0 conformance, not agent qualification

**Owner:** #1510 / #1477. **Date:** 2026-10-18. **Scope:** read-only protocol contract and source provenance. No change to SchemaRouter public routing/authorization, frozen outcomes, model defaults, or release readiness.

## Upstream identity and license

- Official repository: https://github.com/QwenLM/Qwen-Agent
- **Pinned Git commit:** `31a4d36d123688581a9e9744427272b33ce940e0` (2026-03-04); current source at that revision, not an unversioned `main`.
- Licensed Apache-2.0 (repository `LICENSE`); version reported by `qwen_agent/__init__.py` at this commit: `0.0.34`.
- Source of truth:
  - [Nous function call pre/postprocessing](https://github.com/QwenLM/Qwen-Agent/blob/31a4d36d123688581a9e9744427272b33ce940e0/qwen_agent/llm/fncall_prompts/nous_fncall_prompt.py)
  - [Function result pairing](https://github.com/QwenLM/Qwen-Agent/blob/31a4d36d123688581a9e9744427272b33ce940e0/qwen_agent/llm/function_calling.py)
  - [Message/FunctionCall typed structures](https://github.com/QwenLM/Qwen-Agent/blob/31a4d36d123688581a9e9744427272b33ce940e0/qwen_agent/llm/schema.py)
  - [Qwen3 upstream function-calling guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md): recommends Hermes-style tool calls.

The [dedicated GitHub Actions Linux-CPU job](../../.github/workflows/research-qwen-agent-nous-protocol-e0.yml) installs the **exact VCS SHA**, checks pip's `direct_url.json` commit identity (a same-version wheel cannot satisfy the probe), imports real Qwen-Agent classes, and runs `python -m scripts.research_qwen_agent_nous_protocol_e0` on synthetic public records. No model weights, external provider API, secrets or invocation authority are required. Artifacts contain only invariant flags and source identity.

## Specific compatibility difference

| Surface | Current existing SchemaRouter E0 pilot | Actual Qwen-Agent Nous preprocessing |
| --- | --- | --- |
| Model tool proposal | assistant content `<tool_call>…</tool_call>` | assistant content `<tool_call>…</tool_call>` |
| Executed function result | `role="tool"`, content `<tool_response>…</tool_response>` | **`role="user"`**, content `<tool_response>…</tool_response>` |
| Structured transport alternatives | Separate #1508 draft tested role-tool and structured history, **0/3** | Neither alternative tests this upstream Nous user-role replay |
| Multi-call output | existing host-bound E0 parser intentionally rejects >1 call/turn | Upstream parser can emit >1 untrusted function-call proposals |
| Function result identity/order | current trusted host validates source authority per call | Upstream `validate_num_fncall_results` checks matched function names/orders but **does not authorize execution** |
| JSON parsing | #1512 strengthens trusted E0 proposal/final JSON (duplicate/non-finite rejection) | upstream Nous uses permissive `json5`; this cannot be allowed to weaken SchemaRouter's host-validation boundary |

This job verifies a **specific upstream source contract** and parser/rendering behavior. It does not prove that Qwen3-0.6B will issue the second tool call, complete a task, improve supported false refusal, or correctly abstain from unsupported requests. In particular **upstream parsing is proposal parsing, not authority**. The existing original source host must still perform principal-scoped discovery, typed input/output validation, fresh RBAC/ABAC, native provider controls and projection.

## Required next engineering gate

1. After the source-pinned job is green, add one separately preregistered opt-in **`nous-user`** replay arm to the existing actual-host E0 evaluator, comparing against frozen raw and prior #1508 transcript negatives on identical model/source/cases. Do not silently alter the default pilot or run unbounded prompt trials.
2. Prove correct single/multiple/malformed/duplicate/EOS and denied/unknown proposal behavior under the host boundary. Keep hidden denied and unregistered routes opaque. A source-aligned message role is not permission to execute.
3. Extend to BFCL and Korean FunctionChat-Bench/Japanese J-tau **rubrics** for argument validity, missing parameters, clarification, unsupported and premature final, before independently authored source-native EN/KO/JA E2.
4. Only an approved provider/task-disjoint locked evaluation with native ground truth may inform model selection or v0.18 release. Existing 0.6B `0/3`, 1.7B `2/3` are published E0 DEV and remain unchanged.

**Status until separate E2:** A02/R05 NOT_VERIFIED; E2 **0/19**, #1356 v0.18 HOLD and default-model promotion HOLD.

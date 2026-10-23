# E1 Qwen3.5 final-answer failure taxonomy — preregistered diagnostic only

Created: 2026-10-24 before new model results. Issue #1736, stacked
experimental PRs #1737 and #1738. This protocol does not change models,
prompt, tool exposure, parser, scorer or execution privileges.

## Frozen motivating result

Preamble-corrected [Qwen3.5 GGUF EN run #39975130199](https://github.com/JDeun/SchemaRouter/actions/runs/39975130199):
- Qwen3.5-2B Q4_K_M: FULL, Lexical, Concept Graph, Surgical each made
  two original source calls but failed strict final; Frontier made one and
  ended malformed. FULL = 2736, G5 = 2144, Surgical = 6142 model tokens.
- Qwen3.5-4B Q4_K_M: all five arms made two original source calls;
  FULL, Lexical, G5 proposed an additional tool instead of final;
  Surgical emitted a final but failed strict validation; Frontier emitted
  malformed after two tool calls. FULL = 2958, G5 = 2485,
  Surgical = 6417, Frontier = 1963 model tokens.
- All 10 tasks FAILED the strict full-task criterion. The original CI
  jobs completed successfully as **measurements**, not as task success.
- A bounded `other_text_final` label is insufficient to tell a
  wrong semantic value from non-JSON final formatting.

## Outcome taxonomy (fixed labels, no raw text)

For a model output after two actual source callbacks:
- `strict_correct`: single exact JSON object `{"case_state":<observed>}`
- `valid_json_wrong_value`: exact key and type, but not equal to original observation
- `valid_json_wrong_type`: exact key but wrong scalar type
- `valid_json_wrong_contract`: valid JSON but other keys, list or scalar
- `invalid_json_structure`: JSON-like prefix with strict parse failure
- `markdown_fenced_not_strict_json`: fenced block, still a scorer failure
- `reasoning_wrapped_not_strict_json`: explicit reasoning tag, still failure
- `nonjson_or_prefixed_final`: other non-exact JSON, still failure
- `extra_native_call_after_two_source_calls`: proposed additional call, denied
- `malformed_after_two_source_calls`: invalid call or mixed output
- `no_complete_final`: no post-two-call final generation
- `premature_final`: attempted final with fewer than two actual callbacks

These labels are diagnostically distinct but do not reinterpret or repair
prior outcomes, and no model-produced text, argument keys/values, source
observations, oracle gold or reasoning is written to artifact.

Primary strict task success remains exactly as frozen. Secondary: final
failure category, original callbacks, total input + completion model tokens,
bounded offered native envelope categories. Preserve old four/five arms.
Only add diagnostic fields when requested by opt-in diagnostic mode.

## Registered reproduction

Rerun pinned Qwen3.5-2B/4B GGUF Q4_K_M, EN owner-authored four-route
source, five existing arms and identical decoding, task, original graph,
host execution and final scorer. Record full model/GGUF source SHA,
code SHA and unmodified prior run ID. Compare final error labels; do NOT
call lower token count on an unsuccessful task a cost saving.

Language expansion and large-tool inventory generalization require
independent preregistration. E2 source-disjoint external #1346 BLOCKED,
v0.18 #1356 HARD HOLD unchanged.

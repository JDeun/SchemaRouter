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

## Post-measurement result (added after examination of both artifacts)

Reproducible exact-code workflow: [GitHub Actions #39982274748](https://github.com/JDeun/SchemaRouter/actions/runs/39982274748), source checkout SHA
`943b7d0ec666179baffcc502816e98af7816d7bb`.
All **11 associated workflows passed** on the same PR commit, including
GitHub CI, Qwen3.5 GGUF pilot and preexisting Qwen3 control workflows.
The five-arm output is local one-English-task E1 only, not held-out E2.

Pinned Q4_K_M GGUF source receipts:
- Qwen3.5-2B `gguf/Qwen3.5-2B-GGUF@47f5192dcee31b32db0ba0acc04cccef89cb4b2c`;
  SHA256 `9a3d0aa6c920f096441139b6a254542da855223fdad06855ea00c6c087fd713d`.
- Qwen3.5-4B `gguf/Qwen3.5-4B-GGUF@76e05555d64c8d045dd4b9c9f1ebaef1e35d99f7`;
  SHA256 `c3c2cf023efdbd913c2363a14d5c7266db5e05c4602f1c0790eaed567d8aff23`.

| Model | Arm | Actual original callbacks | Strict task success | Total model tokens | Final failure category |
| --- | --- | ---: | --- | ---: | --- |
| 2B | FULL | 2 | no | 2736 | `nonjson_or_prefixed_final` |
| 2B | Lexical K5 | 2 | no | 2736 | `nonjson_or_prefixed_final` |
| 2B | Concept Graph | 2 | no | 2144 | `nonjson_or_prefixed_final` |
| 2B | Surgical path-order | 2 | no | 6142 | `nonjson_or_prefixed_final` |
| 2B | Graph Frontier | 1 | no | 1244 | `no_complete_final` |
| 4B | FULL | 2 | no | 2958 | `extra_native_call_after_two_source_calls` |
| 4B | Lexical K5 | 2 | no | 2958 | `extra_native_call_after_two_source_calls` |
| 4B | Concept Graph | 2 | no | 2485 | `extra_native_call_after_two_source_calls` |
| 4B | Surgical path-order | 2 | no | 6417 | `nonjson_or_prefixed_final` |
| 4B | Graph Frontier | 2 | no | 1963 | `malformed_after_two_source_calls` |

The labels are fixed no-content diagnostics. The five 2B and five 4B
strict full-task outcomes are **all failures**. Lower token usage in
the 2B/4B Concept Graph than FULL is not an established
quality-preserving cost win: neither completed the task correctly.
For 2B final-only replies, the strict JSON parser does not recognize
a complete exact object, so it is **not valid to call them semantic
wrong-value errors**. In 4B baseline/G5 the model generated an
additional native call after two real callbacks; the trusted host denied
it, as required. Surgical final text was not strict JSON. Frontier 4B
failed in the no-tools final phase. Underlying source callbacks and
authorization remain unchanged; no model output or private argument
was copied to this note.

The next substantive question is **not** whether another output
format trick makes a single four-route fixture look favorable. Pair
the already documented 20–500-tool strong lexical / typed ambiguity
break-even study with fixed-schema contextual token accounting
and independently authored, query-disjoint heterogeneous tasks;
run true task-completion comparisons only when all arms have a
qualified common finalization contract. The existing 500/5000 native
G5 CPU/indexing work is separate and must not be relabeled as E2.
E2 #1346 BLOCKED_EXTERNAL and v0.18 #1356 HARD HOLD remain unchanged.

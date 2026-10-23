# Newer-agent-capable models: Qwen3.5 wire format and paired E1 pilot

Date: 2026-10-23. Issue #1736. **Protocol preregistration prior to any new model outcomes.**

## Hypotheses and confounds

Hypothesis A: repeated premature finals in existing Qwen3-0.6B/1.7B
are at least partly limited by model/tool-use competency rather than by
graph search. Hypothesis B: Qwen3.5-native XML tool grammar must be handled
separately before measuring any graph quality effect. The model-size,
generation, precision, tokenizer/parser, inference backend and prompt
effects are distinct confounds and cannot be reduced to a single causal
statement with this study.

Qwen3 native tool wire: `<tool_call>{"name":"...","arguments":{...}}</tool_call>`.
Qwen3.5 native tool wire: `<tool_call><function=...><parameter=...>value
</parameter></function></tool_call>` (Qwen3-Coder parser). The existing
canonical strict SchemaRouter model action parser/host executor stays
unchanged. A host-offered-only XML-to-canonical protocol adapter is an
I/O compatibility layer, never route choice, source permission,
argument repair or confirmation that a native source call succeeded.

### Source references (not measurement evidence)
- https://huggingface.co/Qwen/Qwen3.5-2B
- https://huggingface.co/Qwen/Qwen3.5-4B
- https://docs.vllm.ai/en/stable/features/tool_calling/
- https://github.com/openvinotoolkit/openvino.genai/issues/4543
- https://huggingface.co/gguf/Qwen3.5-2B-GGUF
- https://huggingface.co/gguf/Qwen3.5-4B-GGUF

## Pilot scope

First: static no-weight compatibility gates for real native XML, including
unbalanced calls, duplicated and unoffered parameters, multi-calls,
unexpected routes and numeric type mismatches. Verify no changes to
canonical strict parser.

Only after passing: opt-in **local** Qwen3.5-2B / 4B Q4_K_M GGUF pilot
with authenticated recorded origin repository and exact model SHA; same
owner-authored four-route joined source, strict K5, no mutation, five-turn
budget, EN/KO/JA, deterministic decoding. Pair FULL, lexical, typed
concept-graph and additional current research arms only if the format
support is genuinely equivalent within a model. Record full-task strict
two-original-call+correct-final, model turns, prompt + completion model
tokens, stage/menu context, early termination, parser rejection and
latency. Do not count failures that generate fewer tokens as cost wins.
Separate model checkpoint / quantization / inference runtime / prompt
efficiency from graph retrieval retrieval-quality metrics.

New large inventory arms (50/200/1000/5000) require separate workload
qualification and corpus curation, not extrapolation from four routes.
Formal source-disjoint E2 remains gated (#1346). v0.18 hard hold #1356.

## Negative outcomes must remain visible

Frozen 2026-10-23 Qwen3 surgical path-order Qwen3-1.7B: strict success
3/3 at ~5,359–5,363 model tokens; corresponding FULL: 2/3 at
~2,142–2,151 tokens. Graph Frontier with Qwen3-0.6B/1.7B: 0/6,
the 1.7B aborted after one actual producer call. Prior independent
0.14 tasks: FULL 49.62%, SR-5 29.19%, SR-10 31.03%,
SR-PROGRESSIVE 25.09%, oracle 70.98%. These cannot be discarded.

## Interpretation

`Tool Calling grammar compatible` is not `correct agent`, and
`correct agent` is not `graph saves total tokens`. An actual
paired model-quality benefit is defensible only with independently
checked complete tasks at comparable source state and model parameters.
Small-N development E1 remains exploratory.

# Qwen3.5 optional native tool-call preamble — follow-up E1 preregistration

Date: 2026-10-23. Parent research issue #1736 and Draft #1737.
This is a **new model-wire compatibility condition**; do not alter the original
failed Qwen3.5 results. Registered before running new Qwen3.5-2B/4B outcomes.

## Exact measured trigger, frozen prior results

- Original English GGUF Qwen3.5-2B / 4B run:
  https://github.com/JDeun/SchemaRouter/actions/runs/39971720916
  2B failed a Jinja chat-history argument mapping error, not a model task.
  4B recorded five first-turn malformed native model actions and zero original
  callbacks; not proof that the model cannot call tools.
- Mapping-only corrected English run:
  https://github.com/JDeun/SchemaRouter/actions/runs/39973281844
  Qwen3.5-2B concept_graph_optin executed two actual original read-only
  callbacks and returned a **wrong** final, 2144 total model tokens.
  The other 2B conditions did not finish. Qwen3.5-4B five-arm strict
  correctness 0/5 and zero original callbacks.
- Subsequent **diagnostic-only** English run:
  https://github.com/JDeun/SchemaRouter/actions/runs/39973655813
  4B all five first model envelopes were categorized
  `native_xml_with_prefix`. 2B FULL, lexical and surgical continuation
  also included this shape. 2B graph's successful *source calls* had
  `native_xml_balanced`, though final remained incorrect. Categories do
  not disclose model raw text, private source values, arguments, or oracle gold.

## Hypothesis, single intentionally changed layer

Qwen3.5 official model chat template explicitly permits optional natural
language reasoning **before** a native <tool_call> XML action:
https://huggingface.co/Qwen/Qwen3.5-2B/blob/main/chat_template.jinja

The original research parser rejected any extra text before the XML. Add
only a **Qwen3.5-specific, bounded model-wire preamble normalizer**:
- Permit up to 4096 UTF-8 bytes of prose before one fully balanced XML
  `<tool_call>...<function=...>...</function></tool_call>`.
- Allow optional `<think>`/`</think>` markers solely in that discarded
  prefix; refuse any other markup, hidden role markup, multiple calls,
  trailing text, partial/invented tags or oversized preambles.
- Validate tool name against the **host-offered list**, each parameter
  key/type against the original offered schema, and forward the unchanged
  canonical single call to the **original strict parser**, exact observed
  argument binder and original host read-only executor.
- No tool selection, auto-argument fill/repair, permission widening,
  new source or task gold. Reject if no balanced single call.
- No change to Qwen3 models, shipped default SchemaRouter, scorer,
  model weights, GGUF revision/sha256, K5 selection, original source
  callbacks, or the five existing arm definitions.

## Frozen evaluation plan

Rerun both pinned public-source Qwen3.5-2B/4B Q4_K_M GGUF models on
GitHub Linux CPU, EN pilot, identical four original registered read-only
routes and five paired arms: all_visible, lexical_k5, concept_graph_optin,
surgical_g5_e1, graph_frontier_g5_e1. Save exact new action run IDs,
code source SHAs, GGUF hashes, model success/failure and token receipts.
Outcome: two *real* authorized producer/consumer callbacks and exact
correct final, not merely successful normalized XML or low token count.
Report per arm: original callback count, actual final correctness, model
turns, total prompt + completion tokens, stop reason, bounded native
envelope categories and accepted native call labels.

This is *protocol compatibility*, not proof of a causal graph quality
advantage. Any improvement must be compared against a contemporaneous
correct FULL arm; pilot N=1 per model is too small for statistical
generalization. The independent source-disjoint #1346 E2 and #1356
v0.18 HARD HOLD are unaffected.

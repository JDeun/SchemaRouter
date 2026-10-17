# Qwen ChatML protocol-ending boundary — opt-in E0 only

**Owner:** #1477 R04/R05. **Prerequisite:** PR #1500's real CPU five-way
disposition experiment and posthoc EOS diagnosis. **No product default.**

## Confirmed root-cause distinction

Pinned `LocalQwenAgent` decodes generated sequences using
`skip_special_tokens=False`. The real 30-episode
[run 39023506085](https://github.com/JDeun/SchemaRouter/actions/runs/39023506085)
proved that **all 30 model finals included one ChatML EOS suffix**. The
*strict original raw* observed **1/15 correct in lexical and 1/15 hybrid**,
and those results are retained. An entirely separate posthoc diagnostic
recognized an otherwise correct, no-call, EOS-suffixed token for
unsupported **2/3 lexical, 3/3 hybrid** and needs_input **3/3 lexical,
2/3 hybrid**. Ambiguous and forbidden correct-class diagnostics remained
**0/3 in both arms**. Supported fixture steps were only **1/3 per arm**.

This proves a serializer/protocol mismatch **and also** leaves real
semantic/host-authority classification problems. It does not prove model
quality, calibrated no-fit, provider E2 or final-answer truth.

## This successor experiment

`OptInQwenProtocolBoundaryE0` wraps an otherwise
unchanged local agent's generation and strips **one exact**
`<|im_end|>` or `<|endoftext|>` suffix
**only** if the preceding entire text is one of the four explicitly
host-defined protocol literals. It does **not** strip whitespace,
extra text, arbitrary XML/ChatML, repeated markers, other refusals,
function calls or normal final answers.

The existing `run_generated_episode` frozen
fixture/executor and post-execution scorer are reused unmodified. This
study opts in using a separate `--terminal-decoder bounded-eos`
CLI flag. Without it, the previous raw behavior stays default and
its legacy results remain reproducible. The model receives the **same
published source**, selected K5 tools, task text, prompt, pinned weights
and parameters; gold/host intent never enters the boundary wrapper.

The study reports new strict scores **after** this restricted decoder
boundary, separately from original strict raw scores and from the EOS
diagnostic-only counters. Simulated read-only tool observations never
invoke a real provider; source tasks are already exposed and authored
within this research. No benchmark threshold or default routing changes.

## Required invariants

- Host policy, authorization and hidden-field security remain unchanged.
- One tool call before a no-fit refusal is always a failure, even if
  decoder syntax was normalized.
- Supported tool completion followed by a protocol refusal is not a
  reliable final answer; the study is **not** factual answer validation.
- The new adapter is an output-serialization boundary, **not** a trained
  classifier or license to auto-approve unsupported requests.
- **No independent E2, real provider execution, model default promotion
  or v0.18 release approval** may be inferred from this DEV experiment.
- Keep R04/R05 and the original raw negative source unchanged.

Linux CPU reproducibility: run the separate
`Real Qwen EOS Boundary E0 DEV` workflow,
after checking the fail-closed mock-adapter tests.

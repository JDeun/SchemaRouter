# Qwen3-1.7B model-size candidate: source-locked two-step bound host E0

Owner: #1477 / A02. This is **new development-only model-candidate evidence**.

## Motivation and target hardware

Qwen3-0.6B [raw real CPU run 39029981154](https://github.com/JDeun/SchemaRouter/actions/runs/39029981154):
all EN/KO/JA cases completed exactly one host-bound read then prematurely finalized (0/3 full tasks).
The generic one-time host reminder and EOS-stripped/structured tool-message experiments
also produced 0/3 in this tiny disclosed E0 source. None are independent qualification.

The candidate [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) is Apache-2.0;
its distributed model weight files total roughly 4GB. Official
[GitHub Actions public runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
list 4 vCPU, 16GB RAM and 14GB SSD for ubuntu-24.04 in public repositories.
The E0 job checks actual usable RAM and free disk before inference and treats OOM/timeout as negative feasibility evidence.

The selected immutable Hugging Face revision starts with the published 70d244c commit.
The runtime resolves it through huggingface_hub.model_info to a full 40-character hash,
validates that full hash, and passes the exact same revision to both weights and tokenizer.
The SHA, Linux runner, elapsed time and process peak RSS are recorded.

## One intended experimental factor

Run the same unchanged run_model_selected_bound_two_step_e0 from merged #1506
using LocalQwen17BDevAgent in place of the original frozen Qwen3-0.6B agent.
All other exposed English/Korean/Japanese user prompts, source routes, model generation
settings (greedy, no-thinking, seed, 256 generated-token budget, threads),
two real SchemaRouter authorizations and bound synthetic in-process read-only providers,
task-step parser and strict final-answer oracle are held fixed.
The agent must generate both typed arguments and copy the first *public* result
into the second proposed call; no expected route/record ID or hidden gold enters the model.

The original small-model result is a **prior separate workflow run**, not a same-head paired
run; the candidate weights and matching tokenizer are switched as one bundle.
A model candidate that fails to load or runs beyond CPU resource limits is NOT an acceptable model.

## Limits / qualification

This is only 3 exposed self-authored prompts and deterministic in-process providers.
It is not a real third-party provider integration, independently authored EN/KO/JA holdout,
measured realistic latency SLA, representative false-refusal classifier or generalization proof.
Injected unit-test agents remain UNATTESTED; only the CLI that loads real model weights
can report actual model-inference evidence. Raw user/model texts, hidden canaries, source
identities and tool arguments are excluded from report artifacts.

**A02 NOT_VERIFIED; 0/19 independent E2 qualified; v0.18 release and default-model
promotion HARD HOLD.** Do not backfit these exposed prompts or override older negatives.

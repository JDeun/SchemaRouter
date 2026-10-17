# Real local Qwen3/E5 five-way agent dispositions — development only

**Owner:** #1477 (R04/R05). **Prerequisite:** PR #1499's post-execution five-class E0 scorer.

This additive paired study uses the unchanged existing `run_generated_episode` /
`FrozenCorpusExecutor` and the opt-in fixed K=5 registered-source selector.
It measures **actual local Qwen3-0.6B generations** with the existing pinned
**multilingual-e5-small** on GitHub Actions Linux CPU. Both retrieval arms
(`lexical_k5`, `hybrid_k5`) see the same 15 cases: one each of
supported, unsupported, needs_input, ambiguous and forbidden in EN, KO and JA.

The 13-route source corpus is the **already exposed development benchmark**,
not a new independent provider gold set. Supported and unsupported cases
reuse unchanged published prompts. Input-missing and ambiguity queries are
researcher-authored and explicitly signal their missing referent; **real native
schema required-parameter checks are not present** in this 13-route DEV surface.
Forbidden cases use exactly the same query as the corresponding supported case
but a **host-injected deny rule** hides an existing permitted read operation.
This is a genuine synthetic authorization difference, but because the agent
does not receive hidden privilege information, it cannot reliably distinguish
this denial from an absent capability. Do not interpret its exact refusal-token
accuracy as external safety success.

The visible system prompt defines all four no-call protocol strings uniformly
for all requests. **No host label is passed to the agent or candidate selector**:
the trusted scorer assigns it after the episode. The underlying binary fixture
pass is never used to grade ambiguity, missing input or forbidden cases.

**Recorded report:** per-language and per-class counts for correct disposition,
attempted calls, unknown final class and safety. A tool attempt before a terminal
refusal remains **incorrect**. Only aggregated counts, source/split SHA and model
runtime metadata are published: no raw query, private route IDs, model generated
text, final answer, tool arguments, or fixture gold.

**No independent E2 claim:** this experiment is a **DEV, exposed source**,
with simulated executor read results, no original publisher-author cases,
no real provider invocations, no calibrated no-fit decision and no factual answer
gold. The no-model injected-agent test path reports measured-model flags false.
Only the real-cpu CLI may set actual-Qwen/E5 execution flags true after loading
models. Do not change any frozen #432/#424/#506 science, default routing,
release PR #1356 or the qualification ledger's 0/19 independent passes.

### Reproduction

- Contract: `python -m pytest -q tests/test_research_real_qwen_e5_five_class_disposition_dev.py`
- Source: `python -m scripts.research_real_qwen_e5_five_class_disposition_dev --mode validate`
- Actual model: Linux CPU GitHub Action `Real Qwen E5 Five-Class Disposition DEV`.

If the real model cannot distinguish denied from absent, retain that as
**observed negative DEV**. Do not add gold-aware hints or retroactively rewrite
the prompt to improve these disclosed scores.

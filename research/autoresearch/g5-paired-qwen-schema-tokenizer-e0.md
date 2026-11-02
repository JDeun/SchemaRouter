# Pinned Qwen tokenizer native schema input cost, paired G5 vs lexical K5 — E0

Created 2026-10-24 **before first tokenization experiment**, stacked on
Draft PR #1743, issue #1560. Does not revise the measured 36-cell native
schema-byte results or rerun their model-agent failures.

## Frozen hypothesis and controlled cost scope

Developer synthetic 3-domain Qwen-tokenized menu witness: exact original
principal-scoped native schema JSON exposed by two **already verified**
matched-K5 retrieval methods, real opt-in typed G5 vs same-FieldGroup
source-scoped schema-aware lexical. Code in #1743 found both complete all
three source-owned original 1-root/2-leaf forks across CRM, integer-ID LAB,
string-ID INVENTORY, EN/KO/JA, 512/5012 registered source routes and
normal/mixed original-source policy. G5 exposed fewer bytes on the same
complete-source-hit denominator (30.74/32.81% pooled for normal/mixed).
These measurements are frozen source-contract BYTES, not tokens.

NEW treatment changes **no model**, no source, no fixture, no tokenizer
choice per arm and no selected route algorithm. Tokenize the identically
formatted UTF-8 source-native compact JSON (tool name/source type/license/
description + current reader-scoped original endpoint metadata), sorted
original route IDs, one '\n' separator between route documents. Compare
actual tokenizer.encode(..., add_special_tokens=False) lengths. The
tokenizer is pinned `Qwen/Qwen3-1.7B` official HF source revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` and
`transformers==4.57.3`; **tokenizer only, no downloaded model weights,
no inference/GPU, no model final-answer text**. Different native model
families/chat templates may give different tokens.

For each 2 × 2 source-size/scope × 3 domain × 3 multilingual declared
alias = 36 correlated E0 cells, record G5 and schema-aware lexical
original route count, native schema JSON UTF-8 bytes, and TRUE pinned
Qwen tokenizer counts; count only **BOTH source-oracle-complete**
original 3-route tasks. Strict policy/field/source-authority and K5 guard
first; source docs are never selected using oracle route IDs, and
evaluation oracle is from an independent current original registry scan.
Record cases where token reduction differs from byte reduction.
No fit/no source task must NOT be counted as lower token cost.

**Boundary:** This measures *tokenizer tokens of the serialized native
source menu*. It does **not** measure whole agent prompt tokens (system,
chat template, messages, model requests/observations), intermediate turns,
input+output completion, native tool success, strict final-task accuracy,
runtime billed costs or independently authored E2. It only bridges the
earlier byte metric to one reproducible tokenizer. Never call this a
general end-to-end LLM cost reduction or paper acceptance.

Enforce source repository SHA, Qwen tokenizer version and model input
exclusion. Qwen3.5 agent finals 0/5 both quantized models, historical
v0.14 negative FULL-vs-SR and source-disjoint E2 gate #1346 and paired
agent #1477 remain unaffected; v0.18 #1356 HARD HOLD.

## Post-measurement — pinned Qwen3-1.7B source JSON token receipts

Measured code head `20df6f7e38eebf2e044a8ef29f97d9368f16425a`.
[GitHub Actions run #40033130600](https://github.com/JDeun/SchemaRouter/actions/runs/40033130600)
**success**, artifact ID `12535324302`. Full artifact downloaded
and inspected (`result.json`, four combined catalog/scope summaries,
36 task/domain/language rows). The exact official HF revision
`Qwen/Qwen3-1.7B@70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`,
`transformers==4.57.3`, and
`tokenizer.encode(schema_json, add_special_tokens=False)` were
held constant for both arms. No model weights or generations.

| Combined catalog | Scope | Both-correct source tasks | G5 source JSON tokens | Lexical source JSON tokens | Reduction of G5 source tokens |
| ---: | --- | ---: | ---: | ---: | ---: |
| 512 | normal | 9/9 | 4,014 | 5,784 | **30.60%** |
| 512 | mixed | 9/9 | 4,014 | 5,958 | **32.63%** |
| 5,012 | normal | 9/9 | 4,014 | 5,784 | **30.60%** |
| 5,012 | mixed | 9/9 | 4,014 | 5,958 | **32.63%** |

All 36 cells were positive **source-oracle-complete** for both
actual opt-in indexed typed G5 and source-scoped schema-aware Lexical K5;
hence all 36 qualified for the menu-only token numerator/denominator.
Three language aliases produce the same source menu on each domain,
so identical menu token totals are reused — they are NOT 36
independently composed task instances.

| Domain / scope | G5 original schema JSON tokens | Lexical source schema JSON tokens |
| --- | ---: | ---: |
| CRM / normal | 449 | 713 |
| CRM / mixed | 449 | 771 |
| LAB / both | 448 | 613 |
| INVENTORY / both | 441 | 602 |

The verified Qwen tokenizer counts are close to the previous 30.74%
(normal) and 32.81% (mixed) raw UTF-8 byte reductions, but those
percentages are different metrics and should not be exchanged.
The native source schema menu is serialized in an explicit, fixed,
compact source-owned JSON format, sorted original tool route IDs
with one newline separator; those exact strings are tokenized.
This analysis does **not** account for actual chat template,
model-provided tool function wrapper, prompt instruction text,
conversation/tool observations, output tokens, retries, other agents,
performance latency/billing or strict final-task quality.

**Defensible narrow claim:** Within this THREE-domain developer-authored
synthetic matched K5 source-complete cohort, the opt-in typed G5
graph's original contract menu uses **30.6–32.6% fewer tokens
under a pinned Qwen3-1.7B tokenizer** than the fixed schema-aware
lexical K5 comparator. This is NOT a demonstrated 30% overall
LLM/agent token reduction, not empirical response quality increase,
not source-disjoint independent E2, and not confirmation that G5
outperforms every lexical/dense/relational alternative.
Previous negative agent outcomes and independent FULL-vs-SR
benchmarks remain unchanged; #1346, #1477 and v0.18 #1356 remain gated.


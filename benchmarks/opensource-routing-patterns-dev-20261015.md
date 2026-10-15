# Local routing patterns comparison — exploratory DEV preregistration

This experiment **does not execute the Semantic Router or LlamaIndex packages
themselves**. It reproduces two specific published design patterns locally using
real Hugging Face models; **do not market results as native framework benchmarks**.

## External implementation references (consulted 2026-10-15)

- Aurelio Semantic Router: multi-utterance `Route`, embedded utterances,
  thresholds and `None` on no match:
  https://docs.aurelio.ai/docs/semantic-router/user-guide/components/routers
  and https://github.com/aurelio-labs/semantic-router
- LlamaIndex RouterRetriever: candidate metadata + separate selector:
  https://docs.llamaindex.ai/en/stable/api_reference/retrievers/router/
- Cross-Encoder model: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  (Apache-2.0). Pretrained for multilingual passage ranking, **not** 9-operation
  classification or negative intent detection.

## Locked measurement protocol before results

- Reuse only the publicly exposed, 72-item **DEV** operation-intent corpus:
  54 supported / 18 unsupported in EN/KO/JA, sha256
  `18fce09092e24ebb44d2df14d3224daa47fec9a2df9134d4a0c708b9935dc7d7`.
- Fixed nine **English** operation descriptions imported from
  `scripts/evaluate_operation_intent_cpu_dev.py`.
- **A1** Semantic Router-like example maximum cosine, nine routes and three
  examples per route (one EN, KO, JA), with no rejection.
- **A2** Same examples with fixed route cosine >= **0.65** and winner margin
  >= **0.03**; explicitly diagnostic-only, not calibrated or selected on
  independent data.
- **B1** MiniLM nearest three original English operation descriptions,
  followed by actual multilingual cross-encoder reranking within that top-3;
  forced selection even for unsupported requests.
- **B2** Same reranking but accepts only when selected candidate retrieval
  cosine >= **0.65**; only a synthetic diagnostic, not native LlamaIndex behavior.
- Fixed cross-encoder:
  `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache-2.0).
  Fixed bi-encoder:
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Report both denominators (supported accuracy/wrong/refusal and unsupported
  false acceptance), individual prediction, EN/KO/JA breakdown, CPU p50/p95,
  RSS and end-to-end model load. Provenance must record that exact weight
  revision hashes are **not yet attested**.
- Three example utterances per operation are NEW, but authored **after**
  the team's earlier 72-case studies. The comparison cannot be independent:
  the analyst knows the dataset. No claim of holdout generalization.
- No threshold search, prompt changes or label edits after observing results.
  A failure is a failure; no retry with a hand-picked threshold to win.

## Execution policy

**Research only.** Do not connect either mechanism to `DeclaredOperationFitPolicy`
or authorize any real tool execution, remove existing permissions,
alter frozen 0.14 negative evidence, or merge v0.18 release #1356.
Even a high supported accuracy is insufficient without independent
false-accept, multi-action, negative and operation-fit evaluation.

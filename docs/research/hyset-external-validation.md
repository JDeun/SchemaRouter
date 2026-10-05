# HYSET external-validation retraining protocol

This protocol records the fallback comparison allowed by the HYSET authors after
the paper checkpoint was withheld. It is **not** a reproduction of HYSET's
published checkpoint or paper numbers.

## Frozen upstream inputs

- HYSET repository: `stormwther18/HYSET`
- HYSET commit: `93808cb8d633b6b685f0f9353923b27c2ad7ad81`
- Query encoder: `reasonwang/ToolGen-Qwen2.5-1.5B-Tool-Retriever`
- Evaluation IDs: the six `data/test_query_ids/*_test_query_ids.json` files at
  the pinned HYSET commit.
- Raw ToolBench instructions: obtain from the upstream ToolBench Data Release;
  do not redistribute them from SchemaRouter.

The HYSET authors confirmed in upstream issue #1 that `best.pt` will not be
released and explicitly permitted training/evaluating a new checkpoint from the
public code and data. Therefore any resulting checkpoint must be labeled
**independently retrained HYSET**, never the released paper checkpoint.

## Training boundary

Use HYSET's public `train_hyset.sh` at the pinned commit. Preserve its held-out
test-ID exclusion. Start with the documented seed-42 configuration and do not
tune against the six held-out test splits.

The public README documents two paper-aligned configurations:

- BERT: `--encoder_type bert --d_z 768 --seed 42`
- Qwen: `--encoder_type qwen --d_z 1536 --seed 42`

The released defaults include `M=5`, `K_neg=64`, `K1=15`, `K_pool=20`,
`eta=0.3`, and `lambda_interaction=0.01`. If the execution-reward cache
required for the `eta=0.3` configuration cannot be reproduced from public
artifacts without introducing a new judge/model choice, run the annotation-only
ablation (`--eta 0`, no reward cache) and label it as such. Do not silently
substitute a newly chosen judge.

Record the exact encoder revision, ToolBench data digest, command line, hardware,
CUDA/PyTorch versions, wall time, and produced checkpoint SHA-256.

## Evaluation

Run HYSET's public `src/evaluate_hyset.py` unchanged on all six released split
ID files. Preserve the native metrics:

- Recall@3 / Recall@5
- NDCG@3 / NDCG@5
- COMP@3 / COMP@5
- PredictedSetExactMatch
- MeanPredictedCardinality

For the SchemaRouter side, evaluate the same query IDs and ground-truth tool
identity surface where representable. Keep SchemaRouter-native selected-set size
and latency separate from HYSET's native set prediction. Do not infer
output-field labels from ToolBench.

## Reporting rules

1. Never compare the independently retrained checkpoint to the paper table as if
   it were the authors' released `best.pt`.
2. Report failed training, OOM, unavailable public data, and negative results.
3. No parameter choice may use held-out test metrics.
4. Keep HYSET-native and SchemaRouter-native metrics separately named; only
   directly comparable tool-retrieval metrics may share a table.
5. Pin all newly downloaded model/data revisions before the first scored run.

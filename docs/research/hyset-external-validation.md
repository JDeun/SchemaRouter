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

## Offline preflight before any training or evaluation

The pinned upstream commit was checked against the actual upstream tree.
Its **six** immutable ID-file paths are explicitly listed in the development
manifest (G1 category/instruction/tool; G2 category/instruction; G3
instruction). The similarly named `external/stabletoolbench/` paths are
not substitutes for the six source-pinned `data/test_query_ids/` paths.

Use the standard-library-only validator to inspect the current draft:

```bash
python -m scripts.validate_hyset_retraining_manifest --stage development
```

It reports `DEVELOPMENT_UNSCORED` and `scoring_authorized=false` without
loading HYSET/ToolGen weights, downloading ToolBench or executing evaluation.

After **independently pinning** the exact encoder 40-hex revision, ToolBench
source revision and SHA-256, registering the seed-42 original train command
and making the manifest explicitly `frozen_pre_scoring`, use:

```bash
python -m scripts.validate_hyset_retraining_manifest --stage training
```

The script requires that Qwen `d_z=1536` or BERT `d_z=768` is declared.
For `eta=0.3`, a reproducible execution reward-cache SHA-256 and explicit
`execution_reward_eta03` label are mandatory. For an annotation-only
`eta=0` ablation, the cache must be absent and label
`annotation_only_eta0` is required. Mixed or implicit configurations fail.

Once actual independent retraining has finished, a separate
`training.checkpoint_sha256` is required for
`--stage evaluation`. The validator also rejects wrong split paths,
claims about the unavailable paper checkpoint, held-out tuning,
duplicate JSON keys and nonfinite configuration inputs.

**This is only an input-readiness checker.** Its output always has
`scoring_authorized=false` and `independent_reviewer_approved=false`:
neither an upstream code pin nor six file names authenticate downloaded
dataset bytes, independently certify test/train exclusion, prove the model
was trained, or authorize evaluation. A separate independent review,
actual data verification, checkpoint/command logs and prospective study
freeze are still required. Current committed manifest intentionally fails
training/evaluation readiness.

### Exact native training argv is part of the frozen condition

The pinned public `train_hyset.sh` delegates to `src/train_hyset.py`,
whose **default** `--eta` is **0.3**. Declaring annotation-only
`eta=0` in the manifest **without passing `--eta 0` in the native
command would not produce that ablation**. The preflight therefore parses
a literal single `train_hyset.sh` argv and requires explicit, matching
`--encoder_type`, `--d_z`, `--seed 42` and `--eta`. A reward branch
must actually pass `--reward_cache`; an annotation-only branch must
not pass it. Duplicated flags, alternate test-ID/corpus-directory
overrides, shell chaining and mismatched option values are rejected.
No shell or model command is executed by this validator.

This proves only that the **declared argv** agrees with the manifest.
It does not prove the supplied reward cache has the declared digest,
that model/data bytes match their recorded revisions, or that the
upstream training code produced a checkpoint.

# #1339 — frozen real MiniLM/E5 CPU DEV score-overlap audit

## Question (pre-release negative evidence)

Could a single global cosine-similarity threshold both **accept every supported task** and **reject every unsupported task**, when a multilingual embedding model retrieves from English-only tool descriptions? That is a much narrower question than whether an agent performs its job. The answer on the **previously published same-author development fixture** is already negative for both MiniLM and E5: the *lowest supported request's* top similarity is below the *highest unsupported request's* top similarity, making any scalar cutoff impossible to separate both classes perfectly. This observation should not be confused with an independent holdout, calibration study, or a recommendation to replace the safe no-fit/operation-fit boundary.

## Genuine 2026-10-15 original models, no retraining

Original successful [GitHub Actions run #38729631022](https://github.com/JDeun/SchemaRouter/actions/runs/38729631022), exact source checkout `bc448804d7205ffb4deb4853db6225a4755bb72d` and previously published 84-query corpus digest `dc8b0a7c9325c8767d9b323b24040e0dfe94f3fd170b829b6f977c0e629b2110`.

Archived model reports (raw JSON SHA-256, **not** ZIP digest):

- MiniLM [artifact #11969748248](https://github.com/JDeun/SchemaRouter/actions/runs/38729631022/artifacts/11969748248): `e2221dbd0915fff789ee8f34b9c6aeca3e0d7b7deeaa1186afd75fbeadc721ff`.
- E5 Small [artifact #11969233682](https://github.com/JDeun/SchemaRouter/actions/runs/38729631022/artifacts/11969233682): `998a79a8ea67271257216fa1b2e7fe8233deef030dc1c387577fff8054604215`.

The original benchmark uses 13 real-model-scored synthetic **read-only** base routes and adds deterministic English-language distractors for 100, 250 and 500. It contains exactly 48 supported cases (8 each EN/KO/JA/ES/DE/mixed) and 36 unsupported cases (6 each); the same 84 authored queries are reused at every size. These are **not** production tool schemas or independently labeled requests.

| Catalog size | MiniLM Top-1 supported | E5 Top-1 supported |
|---|---:|---:|
| 13 | 48/48 | 43/48 |
| 100 | 44/48 | 41/48 |
| 250 | 43/48 | 41/48 |
| 500 | **39/48** | **39/48** |

At 500 routes, MiniLM's min-positive Top-1 similarity is approximately **0.255** and max-unsupported Top-1 approximately **0.616**. E5's corresponding values are approximately **0.773** and **0.861**. Thus `min(supported top_score) <= max(unsupported top_score)`; accepting all positives (`score >= cutoff`) necessarily also accepts some negatives. Moreover, a cutoff cannot correct a wrong Top-1 route on a supported request. **Do not choose an apparent "best" cutoff from these observed development labels and call it calibrated.**

## New fail-closed audit

`scripts/audit_multilingual_score_overlap_dev.py` checks:

1. Exact successful historic Actions source SHA, both independent artifact **byte digests**, model checkpoint IDs, corpus digest, generator seed, DEV-only flags, all four catalog sizes, and *identical catalog hashes across models*.
2. Exactly 84 case IDs × four sizes × two models (48 supported / 36 unsupported, balanced language cells); no relabelled task, missing result, duplicate route, forged Top1/5/10 hit or invented score.
3. Per-language Top1/5/10 supported-route recall, highest unsupported versus weakest supported similarity score, whether a perfect single scalar threshold is mathematically possible, and exact supported task IDs losing Top-1 on expansion from 13 to 100/250/500.
4. Explicit `independent_confirmation=false`, `threshold_promoted_to_product=false`, `actual_agent_or_tool_task_success=false`, `may_release=false` on all outputs.

The separate, read-only [Actions workflow](../../.github/workflows/research-1339-score-overlap-audit.yml) re-downloads exact earlier successful **model JSON** artifacts, verifies raw SHA-256, recomputes metrics in stdlib Python, and archives the original report bytes and audit JSON. It does **not** download new model weights, rerun expensive inference, try more thresholds, change scoring logic or modify historical frozen #432/#424.

No inference or runtime changes to `E5CachedEmbedder` or `EmbeddingDecisionBackend` are implied.

## Interpretation and next required qualification

This retroactive audit can rule out *perfect single-score separability on this already exposed fixture*. It **cannot** establish the general optimal abstention gate or prove that no multicriterion verification approach works. A next prospective phase requires query-author-disjoint independently reviewed **supported and unsupported** requests with authentic provider schemas and host access policies, and paired agent end-to-end executions, including denied/no-call assertions. No deployment or automated model selection is authorized.

Existing #1339/#1346/#1412 remain open; **v0.18.0 #1356 HOLD** unchanged.

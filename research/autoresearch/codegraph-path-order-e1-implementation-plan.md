# Implementation plan — opt-in graph-path order E1

Source design: `research/autoresearch/codegraph-path-order-e1-design.md`.
Implement inline on the existing #1732 diagnostic branch as a new stacked
Draft PR. Never modify the frozen #432 baseline or the original parser.

## Task 1 — Model-only surgical cue

Files: `scripts/research_codegraph_surgical_agent_e1.py`,
`tests/test_research_codegraph_surgical_agent_e1.py`.

1. RED: assert that a new `experimental_graph_path_order_prompt=True` emits
   only a static dependency-order cue in the surgical system message, and
   false/normal invocations emit no cue. Existing original native callbacks,
   refusal of out-of-order route, token receipts and authority remain intact.
2. GREEN: add a fixed `GRAPH_PATH_ORDER_CUE_E1` protocol string and typed
   Boolean gate to `run_surgical_model_episode`; append this cue only to its
   model system prompt. No output editing and no execution fallback.
3. Verify with `.venv/bin/python -m pytest -q
   tests/test_research_codegraph_surgical_agent_e1.py`.

## Task 2 — Exact isolated paired variant

Files: `scripts/research_codegraph_local_multiroute_e1.py`,
`scripts/research_codegraph_qwen17_local_e1.py`,
`tests/test_research_codegraph_local_multiroute_e1.py`.

1. RED: reject unsafe combinations, non-Boolean flags and 12-route/negative
   fixtures. Assert treatment marker only for opt-in, and exact unchanged
   FULL/lexical/G5 rows between baseline and treated runs.
2. GREEN: pass the new flag only into `run_surgical_model_episode`, require
   one-action + bare-schema treatment, expose the explicit CLI switch in both
   pinned model drivers; leave scorers and evidence flags untouched.
3. Verify all relevant focused tests and repo-wide Ruff.

## Task 3 — Preregister and run real pinned Linux matrix

Files: `research/autoresearch/codegraph-qwen-path-order-cue-e1.md`,
`.github/workflows/codegraph-g5-path-order-cue-e1-dev.yml`.

1. Register expected positive/negative outcomes **before actual model run**.
2. Add six jobs (0.6B/1.7B × EN/KO/JA), the same pinned public weights,
   same local source K5/control arms, and the added prompt flag. Assert
   original callback counts, evidence tier, pinned SHA, 4-route inventory,
   no raw output and fixed argument-alignment category allowlist.
3. Check YAML and local focused tests, commit, stack the Draft PR on #1732,
   and await exact-head model/CI artifacts. Do not merge or release.

## Review focus

- Opt-in cannot silently change any of the other three arms.
- Graph cue has no extra trust data, gold or invented source arguments.
- Strict host still rejects wrong-order or forged arguments.
- No cross-arm mixing, out-of-K or authority drift.
- Zero-success or higher token cost remains a valid recorded outcome.

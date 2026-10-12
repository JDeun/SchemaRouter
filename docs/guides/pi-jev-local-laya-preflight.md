# Native pi-jev + free local Laya: unscored protocol preflight

Purpose: #1312 / #796. **Not** hosted Jev or a SchemaRouter 0.14 run.

## Source pins and boundaries

- pi-jev `TheoOliveira/pi-jev@c5b5847aa189fe5ffec52893b7051fe8f9e7a548`, clean checkout.
- Official Laya `NandhaKishorM/laya@c73908d96ff73c0062c340a11bf7c54ec7d8bc4d` (`0.4.6`) ships `laya[serve]`, HTTP `/v1/systemone`, `GET /health`, and `LAYA_JEV_STRICT=1`. Its checkpoint SHA and actual CPU/device must be independently recorded.
- **Do not install deprecated/archived `stiermid/laya-serve` for new studies.**
- Native pi-jev uses lexical **10-candidate shortlist + per-tool noul**, whereas SchemaRouter's frozen comparison has **Top-K=3** and its direct Laya integration uses **single-select choice**. These are NOT equal-budget arms; the output is unscored evidence pending preregistration of fair metric/scoring protocol.
- Neither `TYPESAFE_API_KEY` nor a TypeSafe SDK secret file may exist; only HTTP loopback is allowed. No real tools execute.

## Manual setup: independent, separate pinned checkouts

```bash
# In the pinned official Laya source checkout (use dedicated environment):
python -m pip install -e '.[serve]'
unset TYPESAFE_API_KEY TYPESAFE_BASE_URL PI_JEV_BASE_URL LAYA_API_KEY
export LAYA_HOST=127.0.0.1 LAYA_PORT=8000 LAYA_DEVICE=cpu
export LAYA_THREADS=2 LAYA_PRELOAD=0 LAYA_JEV_STRICT=1
laya-serve
# In pinned pi-jev source checkout: npm ci
# In SchemaRouter: python scripts/external_validation_jev_contract.py --input-out /tmp/jev-input.json
# From pi-jev source directory (node --import tsx requires its local npm package):
node --import tsx /absolute/path/to/SchemaRouter/scripts/run_pi_jev_local_laya.mjs \
 --input /tmp/jev-input.json --pi-jev-root "$PWD" \
 --output /tmp/jev-unscored.json --local-url http://127.0.0.1:8000
# Back in SchemaRouter:
python scripts/external_validation_jev_contract.py --validate-output /tmp/jev-unscored.json
node --test tests/test_pi_jev_local_laya_runner.mjs
```

An uncached checkpoint may download weights from Hugging Face; **pin/download and record weight digests before claiming offline reproducibility**. Keep local source, HF weight acquisition and run budgets separate. With `LAYA_PRELOAD=0`, a cold first request can be materially slower than warm requests. The initial `/health` response does not yet prove any model is loaded; the runner must make a **post-inference** health request and rejects a report without actual loaded model revision and observed device data.

The runner first regenerates the entire canonical 82/16 input locally using SchemaRouter's Python generator and rejects changes to any catalog description, query, digest or protocol field; digest-shaped strings alone do not establish provenance. This requires a working `python` executable with the SchemaRouter source checkout importable. The runner dynamically imports actual pinned pi-jev `JevClient` and `ToolRouter`; only the inert Pi tool registry is emulated. It rejects provider fallbacks (the zero-probability path is not a real result), bad activated sets, probabilities, latencies, source revision drift, and nonlocal servers. It never executes tools.

This is a **preflight-only, manual opt-in script**. CI exercises Node guards, not actual model weights. A real local run and independent model-quality assessment remain outstanding. No tuning on 0.11 failed confirmation sets, 0.14 heldout or ClicShopping independent cohort.

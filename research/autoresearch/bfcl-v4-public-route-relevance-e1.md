# Original UC Berkeley BFCL V4: function relevance and abstention (public E1)

**2026-10-18 · #1339 / #1346 / #1477.** This is a genuine **publisher-authored external, PUBLIC** test set, not a self-authored 72-case DEV corpus. It is **not an unseen private confirmation** and does not qualify E2; BFCL has been public for years and may be in training data. This experiment does **not** optimize model hyperparameters, set a production threshold or inspect gold during model inference.

## Exact upstream, provenance and limits

Original [UC Berkeley Gorilla/BFCL](https://github.com/ShishirPatil/gorilla/tree/6ea57973c7a6097fd7c5915698c54c17c5b1b6c8/berkeley-function-call-leaderboard) code/data, Apache-2.0 (original `LICENSE` and BFCL data README). Pinned commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, not floating main. The script verifies exact raw Git blob objects (Git-SHA1 including the `blob <len>\0` header) and 200/240 original ID sets before any model inference.

| File under `bfcl_eval/data/` | Git blob SHA-1 | Cases |
|---|---|---:|
| `BFCL_v4_multiple.json` | `83643fa853e7a29a50e7303b0279284c37dd63c8` | 200 |
| `possible_answer/BFCL_v4_multiple.json` | `1f2f1fbfd9b7c8859ef5a92d6c18b0a6b2bc2663` | 200 gold records |
| `BFCL_v4_irrelevance.json` | `0077629949f2d52734cef2f110b0d040d8c47554` | 240 |

Original `multiple` has 2–4 documented original functions per request and the matching publisher gold **function name**; original `irrelevance` has one irrelevant documented function per request and expects **no call**. The model never sees case IDs, labels or publisher gold. No executable provider tool is ever invoked, even when a function is selected.

## Preregistered, fixed arms before outcome

- `lexical`: current **actual SchemaRouter.retrieve** Top-1, with original BFCL function name/description adapted to read-only neutral `ToolSpec`. Forced ranking (not no-fit).
- `lexical_guard`: that **same** lexical choice, but abstain unless request shares **at least two distinct** content tokens with the original function name, original description and declared property names/descriptions. Tokens: NFKC, camelCase and underscore splitting, lowercase `[a-z0-9]+`, length ≥3, fixed English stopword set in the source. This arbitrary uncalibrated value **is a single prospectively frozen diagnostic**; never silently adjust it from these results.
- `e5`: actual locally loaded source-pinned `intfloat/multilingual-e5-small` revision `fd1525a9fd15316a2d503bf26ab031a61d056e98` on GitHub Actions Linux CPU via existing `E5CachedEmbedder` and `EmbeddingDecisionBackend`, Top-1 only among original offered functions. No answer gold/labels.
- `e5_guard`: that **same** E5 function name with the exact lexical overlap guard above, to quantify unsupported rejection vs supported false refusals.

Code/data/model/artifacts are read-only at evaluation; no end-to-end agent. Publisher-function names are preserved in gold comparison, and the original provided description/parameters are passed to decision backend. All four arms receive identical 200/240 original requests and offered original function menus, with original actual `SchemaRouter.retrieve` as the baseline. Stronger metrics **must not be fabricated** from a tool-call simulator or success of the GitHub Actions process.

## Fixed report

Record `supported_correct`, `supported_wrong_function`, `supported_false_refusal` (denominator 200) and `unsupported_safe_refusal`, `unsupported_false_accept` (denominator 240), plus real measured timing, upstream and model SHA identities. Store only aggregates and upstream file digests in public artifact; no raw request/answer/response text. Assert each arm's 200/240 denominator.

**Important:** A BFCL answerable function **name-only** match is weaker than official BFCL argument AST evaluation, even if it matches all 200. An irrelevance no-call prediction measures only shortlist/abstention, not native provider authorization. Two-token overlap is not a reliable multilingual detector and may sharply increase supported false refusal. External BFCL test cases are public, predominantly English, and may overlap model pretraining. No original native provider API execution, authenticated principal/permission verification, EN/KO/JA transfer, multi-turn tool dependency, threshold calibration, independent private E2 or production SLO is established.

A positive output is evidence for **further feature design/hypothesis**, not permission to change `SchemaRouter.retrieve`, the default model, safe release criteria or #1356. An unsuccessful arm remains a recorded negative. Independent E2 **0/19**, R05/A02 NOT_VERIFIED, v0.18 HOLD.

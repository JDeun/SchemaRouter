# B1 E0 — genuine official Ollama OpenAPI source snapshot (offline; 2026-10-26)

## Immutable publisher schema evidence

This test fixture is the **unmodified upstream provider-authored OpenAPI 3.1 source**
from the public Ollama repository, not a user-authored ToolSpec. It tests the
source-byte and adapter-compiler boundary using an actual third-party project,
not a live server, permissions claim, independent question/gold data or E2.

- Publisher repository: https://github.com/ollama/ollama
- Exact commit: `66ab8482e08035a3238dff04a5739c4371c61bfe`
- Original relative document: `docs/openapi.yaml`, **87,348 UTF-8 bytes**
- Official original source Git blob: `3d0f5db4e71f1cb8331170c4d209902a00dfecc0`
- Original source SHA-256: `e94c8f02969c6807f431b7d0643eb0f8368f1d1baa719a4edaf07989b758f257`
- Original publisher MIT license: `LICENSE`, **1,058 bytes**
- License Git blob: `8e3dc978a7ca8c53f56bbedc5b558116140fc02e`
- License SHA-256: `5934ed2ce0d15154bcdb9c85203210abac0da4314af34081e36df4599f90b226`
- Source URL: https://github.com/ollama/ollama/blob/66ab8482e08035a3238dff04a5739c4371c61bfe/docs/openapi.yaml
- License URL: https://github.com/ollama/ollama/blob/66ab8482e08035a3238dff04a5739c4371c61bfe/LICENSE

These exact source and license bytes are stored under
`research/fixtures/provider-snapshots/ollama-66ab8482-*`. The retained
publisher MIT notice applies; do not strip or misattribute it.

## E0 test protocol and security boundaries

`scripts/research_official_openapi_snapshot_e0.py` performs all checks offline:

1. Check exact raw byte sizes, SHA-256 and Git-native blob SHA of BOTH original
   source and license before YAML parsing. Any byte change fails closed.
2. Parse the publisher's original OpenAPI document using YAML SafeLoader.
3. Select only the **original** `GET /api/tags` and `GET /api/ps`
   operations and required original response-component definitions. Operations
   and schema types are copied, **not reconstructed or edited**.
4. Reuse `schemarouter.adapters.tool_from_openapi`; register the resulting
   two-route native ToolSpec in a deny-by-default router and build the existing
   native posting and G5 graph indexes.
5. Assert the original published MIT metadata DOES NOT imply that the host has
   approved execution, provider permissions, semantic IDs, source type or graph
   identifier dependencies. There must be **zero authorized semantic edges**.
6. Emit a bounded JSON receipt with source revision/hash and all evidence/authority
   flags explicitly false. No provider request, tool invocation or LLM call.

The GitHub Actions job pins Python 3.12, runs the CLI and 11 scoped tests
(including negative byte-mutation cases), and rejects unexpected evidence
promotion. The test is added rather than replacing existing synthetic
500/5000 mixed-source structural and per-principal oracle tests.

## Explicit limits and remaining work

Evidence tier `E0_OFFICIAL_PROVIDER_OPENAPI_SOURCE_ONLY_NOT_E2`.
A source *published* by a genuine provider does **not** constitute independently
reviewed task labels, permission to make API requests, a reviewed route/field
ontology, a tested runtime adapter, or calibrated multilingual answer quality.
The two chosen GET routes are a deliberately small **2-route original subset**,
not a 5000-provider schema study. External #1346 gold and #1477 paired actual
agent E2 remain `BLOCKED_EXTERNAL`; #1356 v0.18 is `HARD HOLD`. Keep Draft
#1755 unmerged, the default router unchanged, and #432 frozen results intact.

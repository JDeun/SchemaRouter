# B1 E0 — genuine Pirate Weather OpenAPI and two-provider catalog

**Scope:** offline source authenticity + existing native adapter/index safety, not
publisher-authored gold, a real invocation, independent E2, or a license grant.

The previous [Ollama source receipt](official-provider-ollama-openapi-e0.md)
pins Ollama original OpenAPI 3.1 GET `/api/tags` and `/api/ps`. This
continuation pins a genuinely *different* provider's original OpenAPI source:

| Evidence | Original upstream source |
|---|---|
| Publisher | [Pirate-Weather/pirateweather](https://github.com/Pirate-Weather/pirateweather) |
| Immutable commit | `6c3b4b0d9890d19b2199f8315488e8669c6951c3` |
| Original document | `PW_OpenAPI.yaml`, **73,096 bytes** |
| Original document Git blob | `1b417160dc385c8d10897d88ec37fa4793d50816` |
| Original document SHA-256 | `ad8bb15117a01902a0a598c7d02a65ec6a30852e160e6cc3a828da0f855c7db3` |
| Original license notice | `LICENSE.md`, **11,357 bytes**, Apache License 2.0 |
| License Git blob | `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` |
| License SHA-256 | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

Upstream source: https://github.com/Pirate-Weather/pirateweather/blob/6c3b4b0d9890d19b2199f8315488e8669c6951c3/PW_OpenAPI.yaml

Upstream license: https://github.com/Pirate-Weather/pirateweather/blob/6c3b4b0d9890d19b2199f8315488e8669c6951c3/LICENSE.md

The exact original two files, including the unmodified Apache 2.0 notice,
are retained in `research/fixtures/provider-snapshots/`.

## Verification

- `scripts/research_cross_provider_openapi_e0.py` checks exact raw byte
  length, SHA-256, *and* upstream Git blob of both source and license.
- Parses the original publisher OpenAPI 3.1 document with YAML SafeLoader;
  unlike the Ollama small 2-route slice, Pirate Weather has **one**
  `GET /forecast/{api_key}/{lat_and_long_or_time}` operation with **required**
  path parameters including the **API key**. The test must not strip, supply,
  log or execute credentials, nor treat published license text as host permission.
- Uses the existing `tool_from_openapi` adapter on the original document.
  It is registered alongside two Ollama native endpoints in the **same**
  versioned `NativeSchemaPostingIndex` / `NativeSchemaGraphIndex`.
  Expected: three original registered routes; no semantic postings, typed
  graph joins, tool execution authority or publisher claims.
- Negative tests mutate one byte or the length of each pinned source and
  license and require a fail-closed refusal before parsing or indexing.
- Existing Python 3.12 dedicated official-source CI checks both providers
  and the explicit no-E2/no-execution receipt.

**E0 only.** The publisher source document is real and pinned, but the
security/privacy controls and end-task correctness have not been independently
certified. No live API request or credentials are used. It proves neither
5,000 genuine sources nor data owner-approved ontology, provider permission,
EN/KO/JA benchmark gold, actual agent utility, or model performance.
#1346/#1477 remain external-dependent; release #1356 HARD HOLD; Draft #1755
remains unmerged.

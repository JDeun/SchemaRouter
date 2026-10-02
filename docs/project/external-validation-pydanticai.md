# PydanticAI ToolSearch validation

Issue [#644](https://github.com/JDeun/SchemaRouter/issues/644) evaluates SchemaRouter as a custom
retrieval strategy behind PydanticAI's existing `ToolSearch` capability.

## Boundary

The integration is intentionally retrieval-only:

```text
PydanticAI deferred ToolDefinition catalog
              |
              | retrieval-only mirror
              v
        SchemaRouter retrieve()
              |
              | bounded tool names
              v
     PydanticAI ToolSearch strategy
              |
              v
PydanticAI disclosure / lifecycle / execution
```

SchemaRouter never receives PydanticAI's execution authority in this evaluation. It does not call
the tools, approve calls, manage the toolset lifecycle, or replace PydanticAI's own deferred-tool
machinery.

## Reproduce

The dependency is pinned for the evidence surface:

```text
pydantic-ai==2.51.0
```

Required CI builds the SchemaRouter wheel, installs it into a fresh virtual environment with the
pinned PydanticAI release, and runs:

```bash
python scripts/external_validation_pydanticai.py \
  --json-out artifacts/external-validation-pydanticai.json

python scripts/external_validation_pydanticai.py \
  --matrix \
  --json-out artifacts/external-validation-pydanticai-matrix.json
```

The script refuses to run as valid downstream evidence if `schemarouter` resolves from the
repository source tree instead of the installed environment.

## Explicit no-route disclosure gate

The first validation run exposed an important integration detail: SchemaRouter's raw lexical score is
**recall-oriented**, not an abstention probability. A generic query token that appears only in
free-form tool descriptions can therefore produce a positive score even when no registered
capability should be revealed.

The PydanticAI strategy does not treat `score > 0` as support. It reveals a candidate only when at
least one bounded relevance signal exists:

- a declared output field matched the query;
- the caller explicitly preferred the tool/endpoint; or
- a matched `tool_token` also belongs to the registered tool identifier itself, rather than only
  to description prose.

The raw Top-K scores, score components, matched fields, and final gate signal are retained per case
in the JSON evidence so this behavior remains inspectable.

## What is measured

The deterministic mixed catalog includes weather, finance, travel, logistics, software, research,
and materials capabilities. Supported cases and one explicit no-route case are evaluated.

The JSON evidence records:

- catalog size and maximum shortlist size;
- full and revealed **serialized schema bytes**;
- required-tool recall on supported cases;
- unsupported-query rejection;
- retrieval-task success rate;
- mean and maximum routing latency;
- exact input-schema preservation in the retrieval mirror;
- per-case selected names and revealed-schema bytes.

No byte count is labeled as a token count.

## Frozen scaling matrix

The reproducible matrix is **12 / 50 / 100 / 250 tools**. The original planning note
mentioned a 10-tool point, but the frozen real catalog contains 12 tools and the supported
case set depends on that complete catalog. The benchmark therefore uses 12 as the smallest
faithful point rather than deleting real tools or changing the cases after the fact.

| Catalog size | Composition |
| ---: | --- |
| 12 | Complete frozen real catalog |
| 50 | 12 real tools + deterministic synthetic distractors |
| 100 | 12 real tools + deterministic synthetic distractors |
| 250 | 12 real tools + deterministic synthetic distractors |

The matrix command emits every run into one JSON document so required-tool recall,
unsupported rejection, revealed serialized schema bytes, shortlist size, and routing
latency can be compared without changing the query set or retrieval policy.

## Fidelity limits

The mirror intentionally copies only the information needed for SchemaRouter retrieval: tool name,
description, input JSON Schema, and locally declared semantic output hints.

PydanticAI-specific execution, approval, timeout, strictness, tool kind, toolset lifecycle, and
defer/reveal state remain authoritative in PydanticAI and are not reimplemented in SchemaRouter.
The local output semantic hints are explicit evaluation metadata; they are not inferred from
PydanticAI.

This is **E0 maintainer-owned evidence** under the
[external adoption plan](external-adoption.md). It is not independent validation and does not claim
that SchemaRouter replaces or outperforms native PydanticAI ToolSearch.

See also the [external case-study template](case-study-template.md).


## Frozen matrix result

Canonical workflow run: `37002468981` at source
`98b7b804002c99751fc7233938fbcf21fca14f7d`.

Artifact: `external-validation-pydanticai-matrix`  
Digest: `sha256:0f449bba15d993a516887c7e12d705c0f5f5f0d9fe69fb662ee20a0d84d6a820`

| Tools | Required-tool recall | Unsupported rejection | Simple baseline unsupported rejection | Mean revealed schema bytes | Full serialized schema bytes | Mean routing latency |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | 100% | 100% | 0% | 262.2 | 3,130 | 1.565 ms |
| 50 | 100% | 100% | 0% | 262.2 | 12,972 | 3.954 ms |
| 100 | 100% | 100% | 0% | 262.2 | 25,922 | 6.762 ms |
| 250 | 100% | 100% | 0% | 262.2 | 64,922 | 16.400 ms |

The simple name/description baseline retained the required tool on all four supported
cases at every catalog size, but it disclosed tools for the single frozen unsupported
case at every size. SchemaRouter retained the required tool and rejected that unsupported
case at every size. Routing latency increased with catalog size; this result is retained
rather than hidden behind a composite score.

These are deterministic retrieval-layer results over five frozen cases. They do not
measure final model answers or independently validate SchemaRouter adoption.

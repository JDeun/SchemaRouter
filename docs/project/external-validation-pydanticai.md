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

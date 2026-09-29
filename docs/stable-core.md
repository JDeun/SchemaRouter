# Stable core contract

SchemaRouter's current product architecture is considered complete enough to freeze while
research continues independently.

This document does **not** declare a 1.0 API guarantee. SchemaRouter remains pre-1.0 and follows
the compatibility rules in [Versioning](versioning.md). The purpose of this freeze is narrower:
research results should improve implementations and defaults behind the current product boundary
instead of repeatedly redefining that boundary.

## Frozen product boundary

```text
Python / OpenAPI / MCP / OPTIMADE / adapter plugins
                         |
                 typed registry
                         |
          bounded capability retrieval
                         |
            agent / application
                         |
              planning/calls
                         |
       validation + local execution policy
                         |
                bound execution
```

The following distinctions are part of the product contract.

### Retrieval is not execution authority

`retrieve` and `aretrieve` return bounded typed candidates from registered capability
contracts. They do not execute tools and do not grant permission to execute them.

`retrieve_executable` and `aretrieve_executable` additionally filter for current local
binding readiness. They still do not execute or authorize a side effect.

### Candidate contracts preserve executable schema

`CapabilityCandidate` preserves:

- route/tool/endpoint identity;
- full effective input and output JSON Schema;
- declared parameters and output fields;
- semantic IDs, datatypes, optional units/dimensions/qualifiers;
- read/write/destructive classification;
- provider/source/access metadata;
- tool and endpoint fingerprints.

A downstream agent may receive a smaller serialized view, but the SchemaRouter result itself
retains the registered typed contract.

### Execution remains fail-closed

Actual invocation remains subject to:

- registered tool/endpoint identity;
- schema and fingerprint validation;
- local binding readiness;
- execution policy;
- approval rules;
- retry restrictions;
- execution budgets;
- trusted hooks and transport boundaries.

Retrieval ranking, an external agent, LangChain, LangGraph, LlamaIndex, or another adapter cannot
grant execution authority.

### Integrations are adapters, not alternate runtimes

LangChain, LangGraph, and LlamaIndex integration surfaces are optional. They do not replace
SchemaRouter validation or policy.

The core package must remain importable and usable without those optional dependencies.

## Public facade frozen for current research cycles

Research may change internal ranking/index implementations while preserving these facades:

- `SchemaRouter.retrieve(..., k=5)`
- `SchemaRouter.aretrieve(..., k=5)`
- `SchemaRouter.retrieve_executable(..., k=5)`
- `SchemaRouter.aretrieve_executable(..., k=5)`
- equivalent `ConfiguredSchemaRouter` retrieval methods;
- existing planning, invocation, batch, streaming, policy and inspection APIs.

The complete top-level export list remains guarded by `tests/test_public_api.py`.

## What research may change without redesigning the product

Evidence may justify compatible changes such as:

- alternate retrieval indexes or representations;
- a different documented default K in a future minor release;
- adaptive shortlist depth;
- corrective re-retrieval;
- additional scoring backends;
- performance optimizations;
- new optional adapters.

These should normally remain behind the same typed retrieval and execution boundary.

## What requires reopening product architecture

A public-boundary redesign needs at least one of:

- a reproducible correctness defect;
- a security or execution-authority flaw;
- an important user workflow that cannot be expressed through the existing facade;
- an ecosystem compatibility constraint that cannot be solved through an adapter;
- a deliberate breaking minor release with migration documentation.

A benchmark improvement by itself is not sufficient reason to redesign the facade.

## Completion versus external operations

The following do not block the core freeze:

- stronger-agent or held-out research;
- final-answer-quality research;
- ecosystem-directory/listing responses;
- repository About metadata;
- PyPI Trusted Publisher environment hardening.

They remain tracked work, but are separate from whether the local package architecture/API is
complete and internally coherent.

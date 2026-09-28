# Structured retrieval and execution for RAG and agents

**RAG (Retrieval-Augmented Generation)** is a generation architecture in which a model's output is
augmented with information retrieved from external, non-parametric sources.

SchemaRouter is **not RAG itself** and does not own the generation step. It can serve as part of the
retrieval side of a RAG or agent system when the external information must be obtained from
structured, executable sources such as OpenAPI endpoints, MCP tools, OPTIMADE services, or typed
Python callables.

```text
User query
    |
    v
RAG / Agent / Application
    |
    | declares a data need
    v
SchemaRouter
    |
    +--> registered capability retrieval
    +--> endpoint + field selection
    +--> policy / health / parameter validation
    +--> trusted execution
    +--> raw-output validation
    +--> declared normalization / projection
    |
    v
Typed external data
    |
    v
Generation / reasoning in the surrounding system
```

For document-centric RAG, the external source may be a corpus of passages or records and the
retriever returns context. SchemaRouter addresses a different retrieval surface: **registered
capabilities and the structured data they can return**.

Its registry forms a logical capability graph whose relationships include providers, access paths,
tools, endpoints, parameters, output fields, policy, availability, and evidence contracts. A graph
database or vector database is not required. Deterministic indexes, embeddings, or bounded decision
backends may help search the catalog, but the registered schema remains the authority.

## The retrieved capability is executable

A document retriever can return relevant context. SchemaRouter must additionally prove that the
selected registered route can perform the requested operation and return the requested data surface.

The resulting capability contract includes:

```text
Endpoint
  operation
  input contract
  output fields
  read/write/destructive semantics
  provider/access identity
  availability
  policy/evidence requirements
```

A model may help rank or veto already registered candidates. It cannot create a new endpoint,
parameter, field, permission, credential, health state, or side effect.

## Field-first, route-second

The primary semantic object is the data need, not the provider.

For a query such as:

```text
"What is the elastic modulus of this material?"
```

SchemaRouter should first resolve the logical field requirement:

```text
semantic field = elastic_modulus
```

and only then choose a registered route that can provide it:

```text
elastic_modulus
  -> provider A / REST
  -> provider A / OPTIMADE
  -> provider B / MCP
```

Availability or policy may change the route. It must not silently change the required field.

When a query needs several fields and the application explicitly permits multiple calls,
SchemaRouter can select complementary routes within the caller's `max_calls` bound.

## Datatype and unit are part of the field contract

A field name alone is not enough to establish equivalence.

SchemaRouter can carry the declared JSON value type/shape, semantic identity, source unit, canonical
normalization contract, exact qualifiers, and evidence metadata with the field.

For example:

```text
semantic_id: mechanical.elastic_modulus
type: number
source_unit: GPa
canonical_unit: Pa
dimension: pressure
normalization: value * 1e9
qualifiers:
  temperature: 300 K
  phase: alpha
```

This matters because two providers exposing a field named `elastic_modulus` are not automatically
interchangeable.

Automatic cross-provider fallback remains conservative:

```text
same semantic field
AND compatible declared datatype/shape
AND compatible declared unit/canonical-unit contract
AND exact qualifier compatibility where qualifiers are present
```

SchemaRouter does **not** infer a conversion factor merely from a unit string and does not infer that
two measurement conditions are scientifically equivalent. Unit normalization is applied only when a
trusted `UnitNormalizationSpec` declares the conversion.

Units are optional. Strings, identifiers, booleans, structured metadata and dimensionless numbers
may legitimately be unitless. The field semantics, not the source type, decide whether a unit exists.

## Registration should be generic

The intended product boundary is that an application can register a capability source and use it
without writing benchmark-specific routing rules.

```text
new OpenAPI / MCP / Python capability
  -> parse declared schema
  -> compile the same typed registry contracts
  -> update indexes
  -> immediately participate in bounded routing
```

Machine-readable source metadata is preferred. Human-readable documentation follows an explicit
inspect -> proposal -> approval flow because prose alone is not execution authority.

A newly registered route should not require a route-specific classifier to become usable. Optional
learned components may learn generic semantic matching, but route identities and permissions remain
local registered facts.

## Where SchemaRouter stops

SchemaRouter owns the capability retrieval and execution boundary. It does not own the full agent
loop.

```text
LangChain / LangGraph / LlamaIndex / application
                    |
               SchemaRouter
 typed capability retrieval + validation
                    |
 OpenAPI / MCP / OPTIMADE / Python / plugins
```

The layer above owns conversation, decomposition, memory, graph orchestration and answer generation.
SchemaRouter answers a narrower question:

> Given the registered capabilities, what is the smallest trusted executable data surface that can
> satisfy this request?

That scope is deliberate. It lets Retrieval-Augmented Generation or agent systems consume live
structured data without giving an unconstrained model authority over the entire tool catalog.

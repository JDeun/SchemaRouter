# Capability catalog: RAG for executable data sources

A useful mental model for SchemaRouter is **RAG infrastructure for executable capabilities**.

A conventional RAG pipeline takes documents, parses them into a machine-readable representation,
indexes the resulting chunks and metadata, retrieves the smallest relevant context for a query, and
hands that context to an application or agent.

SchemaRouter applies the same separation of concerns to APIs and tools:

```text
RAG
document
  -> parser
  -> chunks + metadata
  -> index / vector store
  -> retriever
  -> selected context
  -> RAG / agent

SchemaRouter
OpenAPI / MCP / OPTIMADE / Python
  -> adapter
  -> Tool / Endpoint / Parameter / Field contracts
  -> typed capability registry / index
  -> bounded router
  -> selected endpoint + fields
  -> validated data
  -> RAG / agent / application
```

The analogy is architectural, not literal. SchemaRouter does not require a graph database or a vector
database. Its registry forms a **logical capability graph** whose nodes and relationships include
providers, access paths, tools, endpoints, parameters, output fields, policy and evidence contracts.
Implementations may use deterministic indexes, embeddings, or bounded decision backends to search
that graph, but the registered schema remains the authority.

## The unit of retrieval is executable

A text retriever can return a semantically similar chunk. SchemaRouter must additionally prove that
the selected route can perform the requested operation and return the requested data surface.

That makes an endpoint closer to a typed executable chunk:

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

That scope is deliberate. It lets an agent or RAG system consume live structured data without giving
an unconstrained model authority over the entire tool catalog.

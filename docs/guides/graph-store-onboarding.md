# Graph and RDF onboarding

SchemaRouter can expose property graphs and RDF sources as typed, bounded traversal capabilities
without giving a model arbitrary Cypher, Gremlin, or SPARQL execution authority.

## Provider-neutral graph contract

A trusted graph adapter discovers graph schema and implements bounded traversal:

```python
keys = router.add_graph_store(
    backend,
    database_name="knowledge",
)
```

Async backends use:

```python
keys = await router.aadd_graph_store(
    backend,
    database_name="knowledge",
)
```

Discovery describes:

- graph/source name;
- graph model: `property_graph` or `rdf`;
- node labels/classes/types;
- relationship types or RDF predicates;
- model-visible properties;
- explicitly public graph metadata.

SchemaRouter compiles one typed `traverse` capability per graph.

## Bounded traversal

The model-visible traversal surface is deliberately constrained:

- required `start_id`;
- relationship/predicate names must come from the discovered schema;
- direction is `out`, `in`, or `both`;
- `max_hops` is bounded;
- result count is bounded;
- output fields are explicitly projected.

There is no model-visible raw Cypher/Gremlin/SPARQL parameter.

Vendor adapters translate this bounded contract into native driver calls.

## Authorization

Each graph is a separate capability, so principal-aware authorization can hide graph sources before
retrieval:

```python
AuthorizationRule(
    effect="allow",
    operation="knowledge.org.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="knowledge.executive.*",
    roles_any=("executive",),
)
```

Unauthorized graph capabilities are non-disclosed before model selection and are revalidated before
execution.

Node/property/relationship sub-scopes and trusted traversal predicates are extended in #770.

## Vendor targets

The provider-neutral contract is intended to support thin adapters for:

- Neo4j;
- Amazon Neptune;
- ArangoDB;
- compatible SPARQL 1.1 endpoints such as GraphDB/Stardog-style deployments.

The common contract is implemented first. Native vendor SDK/live acceptance remains a separate
vendor-adapter task; the common contract alone is not a claim that every named database is already
validated end-to-end.

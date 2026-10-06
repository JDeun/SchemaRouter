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

Allowed relationship sets and maximum traversal depth are applied through principal DataScope
rules and revalidated at execution. Hidden node/edge/property predicates require an explicit
`ScopedGraphStoreBackend` implementation with `supports_trusted_filters = True`. If a DataScope
rule supplies trusted filters to a backend that has not declared and implemented that contract,
SchemaRouter fails closed before traversal I/O. The built-in native graph/RDF adapters do not yet
claim this predicate capability.

## Native vendor adapters

The provider-neutral contract now has thin caller-owned adapters for:

- **Neo4j** via the Python driver's `execute_query()` surface;
- **Amazon Neptune Database / Neptune Analytics** via the supported openCypher Data APIs;
- **ArangoDB** via `python-arango` graph discovery and parameter-bound AQL traversal;
- **FalkorDB** via the official caller-owned Python client, `GRAPH.LIST`, and read-only `ro_query()` openCypher traversal;
- **SPARQL 1.1 query endpoints** through a caller-owned HTTP client, suitable for compatible
  RDF stores such as GraphDB/Stardog deployments.

Typical native registration is still explicit and credential-free from SchemaRouter's point of
view:

```python
router.add_neo4j_graph(driver, database="neo4j", graph_name="org")
router.add_neptune_graph(neptune_client, graph_name="social")
router.add_arango_graph(arango_database)
router.add_falkordb_graph(falkordb_client, graphs={"social"})
router.add_sparql_graph(
    http_client,
    endpoint="https://example.org/sparql",
    graph_name="rdf",
)
```

These adapters translate only SchemaRouter's bounded traversal contract. They do not expose raw
Cypher, AQL, Gremlin, or SPARQL text to model output. The FalkorDB adapter discovers graph names, labels, relationship types, and visible property names, and executes only through `ro_query()`.

Deterministic SDK-shape tests are release-gated. A native adapter being present does not imply that
every vendor/version/deployment has completed live external acceptance.

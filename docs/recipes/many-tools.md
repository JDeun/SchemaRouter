# Many-tool catalogs

SchemaRouter becomes most useful when an agent can access many registered tools and endpoints but
should not receive the full catalog on every turn.

## Retrieve a bounded candidate set

Use the public retrieval surface to expose only the most relevant registered capabilities:

```python
candidates = router.retrieve(
    "current Young's modulus for MAT-7",
    k=5,
)

for candidate in candidates.candidates:
    print(candidate.route_id)
    print(candidate.parameters)
    print(candidate.output_fields)
```

Retrieval is side-effect free. It does not execute a tool and does not grant execution authority.
The downstream agent may choose among the returned registered contracts; actual execution still
passes through SchemaRouter validation and policy.

Use `retrieve_executable(..., k=5)` when the shortlist must additionally be restricted to routes
with a currently ready local execution binding. Async equivalents are `aretrieve` and
`aretrieve_executable`.

## Namespace by source

Avoid accidental key collisions:

```python
ToolSpec(name="search", namespace="materials_project", endpoints=[...])
ToolSpec(name="search", namespace="pubchem", endpoints=[...])
ToolSpec(name="search", namespace="internal_lab", endpoints=[...])
```

## Keep semantics close to the schema

Put trusted domain synonyms and typed metadata on the registered contract rather than repeating the
entire catalog in prompts:

```python
FieldSpec(
    name="formation_energy_per_atom",
    semantic_id="materials.formation_energy_per_atom",
    aliases=["formation energy", "energy per atom"],
    json_schema={"type": "number"},
    unit="eV/atom",
)
```

A candidate retains the full effective input/output JSON Schemas together with parameter contracts,
output fields, semantic IDs, optional units and qualifiers, provider/access identity,
read/write/destructive metadata, and schema fingerprints.

## Use preferred tools only when the application has trusted context

```python
request = PlanRequest(
    query="LiFePO4 band gap",
    preferred_tools=["materials_project.search"],
    arguments={"formula": "LiFePO4"},
)
```

Preferences guide ranking; they do not bypass schema validation or execution policy.

## Keep output projection recall-first

When a downstream answer depends on context that is difficult to predict, do not optimize field count
at the expense of recall. SchemaRouter intentionally falls back to declared fields when output intent
is ambiguous.

## Scaling boundary

The built-in registry/index path is process-local and deterministic. It is appropriate for ordinary
application catalogs and for compact Top-K exposure to an external agent.

For very large or shared catalogs, applications can implement the public `ToolRegistry` boundary
behind a persistent or distributed store while preserving registry versioning, typed capability
contracts, and local execution authority. Retrieval backends may accelerate candidate search, but
they must not invent unregistered routes or weaken policy.

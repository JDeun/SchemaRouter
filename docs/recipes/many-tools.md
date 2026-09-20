# Many-tool catalogs

SchemaRouter becomes most useful when a catalog contains many tools and many endpoints.

## Namespace by source

Avoid accidental key collisions:

```python
ToolSpec(name="search", namespace="materials_project", endpoints=[...])
ToolSpec(name="search", namespace="pubchem", endpoints=[...])
ToolSpec(name="search", namespace="internal_lab", endpoints=[...])
```

## Prefer schema aliases over giant prompts

Put domain synonyms close to the schema:

```python
FieldSpec(
    name="formation_energy_per_atom",
    aliases=["formation energy", "energy per atom"],
    unit="eV/atom",
)
```

The planner can then match concepts without embedding every tool's documentation into one prompt.

## Use preferred tools when the application already knows the domain

```python
request = PlanRequest(
    query="LiFePO4 band gap",
    preferred_tools=["materials_project.search"],
    arguments={"formula": "LiFePO4"},
)
```

Preferences guide ranking; they do not bypass schema validation.

## Keep output projection recall-first

When a downstream answer depends on context that is difficult to predict, do not optimize field count
at the expense of recall. SchemaRouter intentionally falls back to declared fields when output intent
is ambiguous.

## Scale boundary

The v0.1 in-memory registry is appropriate for process-local catalogs. Very large or shared catalogs
can implement `ToolRegistry` behind a persistent index while preserving the same snapshot and
versioning semantics.

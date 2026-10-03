# Scalable capability dependency graphs

SchemaRouter builds dependency edges only when one capability's declared outputs can satisfy every declared requirement of another capability. The graph remains a contract-inspection primitive; it does not plan or execute workflows.

## Indexed construction

Graph construction uses a semantic producer index before running the full compatibility comparator.

```text
producer.produces semantic ID
        |
        v
semantic producer index
        |
        v
consumer.requires semantic ID
        |
        v
candidate producer intersection
        |
        v
full type/unit/qualifier compatibility check
```

The index is conservative. Exact semantic IDs and explicit `CompatibilityContext.semantic_equivalences` are included. Type, unit, dimension, qualifier, and conversion semantics are still decided by `compare_capability_composition(...)`.

Output is deterministic and independent of input capability ordering.

## Incremental updates

When contract identities change, use:

```python
updated = update_capability_dependency_graph(
    old_graph,
    previous_contracts,
    current_contracts,
    context=context,
)
```

Only edges incident to added, removed, or changed capability contracts are recomputed. The result must be equivalent to a clean full rebuild.

If the `CompatibilityContext` itself changes, perform a full rebuild. A semantic-equivalence or unit-conversion policy change can alter edges between otherwise unchanged contracts.

## Cycle analysis

`dependency_strongly_connected_components(...)` uses Tarjan's algorithm.

`dependency_cycles(...)` returns at most one deterministic simple cycle witness per cyclic strongly connected component, with a configurable `max_witnesses` bound. It intentionally does not enumerate every simple cycle in a dense graph.

## Benchmarking

The repository includes:

```bash
python scripts/benchmark_capability_graph.py
```

The default sparse benchmark covers 1,000, 10,000, and 50,000 capabilities and records build latency, incremental-update latency, edge count, and peak traced memory. Dense cases are bounded by default because the output edge set itself is quadratic; use `--dense-limit` only for deliberate stress runs.

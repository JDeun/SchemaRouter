# Portable capability graph artifacts

SchemaRouter capability artifacts are deterministic JSON documents for moving compiled capability contracts between environments. The format carries a version, graph digest, typed capability contracts, source schema fingerprints, optional dependency metadata, and non-secret provenance.

```python
from schemarouter import (
    build_capability_artifact,
    load_capability_artifact,
    serialize_capability_artifact,
)

artifact = build_capability_artifact(
    graph_digest=snapshot_id,
    capabilities=contracts,
    sources=sources,
)
document = serialize_capability_artifact(artifact)
loaded = load_capability_artifact(document)
```

The current artifact format is **1.1**. SchemaRouter also reads the historical **1.0** format and migrates it deterministically before returning it. Unknown/newer versions fail closed.

## 1.0 to 1.1 migration

Version 1.1 makes edge provenance explicit with `origin = "derived" | "external"`.

The 1.0 builder accepted edge metadata supplied by the caller and did not record whether those edges had been recomputed from the included contracts. Migration therefore marks 1.0 edges as `external`; it does **not** invent stronger derived semantics.

```python
from schemarouter import migrate_capability_artifact

result = migrate_capability_artifact(old_document)

assert result.migration.from_format == "1.0"
assert result.migration.to_format == "1.1"
```

Migration validates the source artifact digest before transforming it and records the source digest in non-secret migration provenance. Running migration again on the current document is idempotent.

## Semantic integrity

`validate_capability_artifact(...)` rejects duplicate capability/source/edge identities and dangling/self edges.

For fully derived artifacts, use `build_capability_artifact_from_graph(...)`. Derived edges are rechecked against the included capability contracts and the canonical graph digest is verified. External edge metadata is never silently promoted to execution authority.

## CLI

```bash
schemarouter artifact inspect graph.json --json
schemarouter artifact migrate graph.json --json
```

Migration writes a new `.migrated.json` file by default. SchemaRouter refuses to overwrite the source or an existing destination unless `--overwrite` is explicit.

Artifacts deliberately exclude credentials and live health/runtime state. A deployment may compile and validate artifacts in CI, distribute them through infrastructure chosen by the host, and apply live health overlays after loading. SchemaRouter does not implement an artifact registry, signing service, or deployment controller.

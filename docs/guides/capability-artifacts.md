# Portable capability graph artifacts

SchemaRouter capability artifacts are deterministic JSON documents for moving compiled capability contracts between environments. The format carries a version, graph digest, typed capability contracts, source schema fingerprints, optional dependency metadata, and non-secret provenance.

```python
from schemarouter import build_capability_artifact, serialize_capability_artifact, load_capability_artifact

artifact = build_capability_artifact(graph_digest=snapshot_id, capabilities=contracts, sources=sources)
document = serialize_capability_artifact(artifact)
loaded = load_capability_artifact(document)
```

Loading is strict: unsupported format versions and digest mismatches fail closed. Version `1.0` is the initial contract; readers must reject unknown major formats rather than guessing compatibility.

Artifacts deliberately exclude credentials and live health/runtime state. A deployment may compile and validate artifacts in CI, distribute them through infrastructure chosen by the host, and apply live health overlays after loading. SchemaRouter does not implement an artifact registry, signing service, or deployment controller.

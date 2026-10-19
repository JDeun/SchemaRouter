# M0 #1532 — analyzer-visible provider wire projection (E0)

Date: 2026-10-19. This is a standalone follow-up based on main after merged #1602, not dependent on the pending #1604 lexical scoring change.

## Local failure class

A data-scoped EndpointSpec may retain ServerProjectionSpec.field_map values for an allowed canonical output field. Such a value may be an unreviewed provider-private source column name, potentially including an output field name denied by the principal scope. The original source mapping is crucial to correct server-side projection and must **not** be erased from execution contracts or the planner's trusted endpoint-scoring/projection path.

The _scoped_analysis_registry produces **non-executable** principal-scoped public descriptors for an arbitrary custom QueryAnalyzer. Before this patch it exposed the raw ServerProjectionSpec.field_map and wire selector strings even though FieldSpec.path/result_path and input/output schemas were sanitized in #1600/#1601.

## Change

Under a restrictive DataScopeRule only, clone the already filtered EndpointSpec for the **analyzer's catalog** with server_projection=None. This is strictly a safe display view; SchemaRouter._data_scope_endpoint_view still creates the full **trusted internal scoped planning view** with allowed server-side selectors and the original provider registry retains its complete raw source mapping and fingerprints. Unscoped catalog and policy scope checks remain unchanged.

The test fixture contains an authorized public_value projected from a unique private wire selector and a distinct hidden private_value. It asserts that the analyzer ToolSpec and public CapabilityRetrieval omit both canaries, while the original EndpointSpec and internal planning view preserve the wire projection; an authorized original planning call remains available. Existing server projection transport, authorization, host field contract and input/output descriptor tests run in the dedicated Linux workflow.

## Limits

This is local no-network E0 metadata-surface coverage, not a general noninterference proof. Source-authored semantic IDs, protocol names, metadata in other analyzer entrypoints, untrusted ranking provenance and downstream model traces must still be reviewed under #1532. It cannot establish multilingual retrieval or independent external E2; release #1356 stays HARD HOLD.

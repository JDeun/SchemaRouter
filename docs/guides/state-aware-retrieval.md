# State-aware capability retrieval

External runtimes can filter an ordinary SchemaRouter retrieval result against typed execution state without giving SchemaRouter workflow or execution authority.

```python
from schemarouter import filter_retrieval_by_state

eligible = filter_retrieval_by_state(
    retrieval,
    execution_state,
    requirements_by_route=typed_state_requirements,
)
```

`requirements_by_route` is explicit host-supplied contract metadata. SchemaRouter does not infer workflow preconditions from route names, parameter names, descriptions, or previous calls. A declared requirement with missing or incompatible typed state is excluded fail-closed; routes with no declared state requirement remain eligible. The original retrieval ranking is preserved among survivors.

This API performs filtering only. It does not select a workflow, execute a capability, mutate state, retry a failed operation, or decide whether a business transaction is complete.

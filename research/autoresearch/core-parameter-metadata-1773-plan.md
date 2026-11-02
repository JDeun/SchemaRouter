# #1773 — Safe typed input metadata in field-only Algorithm 1 plans

## Intent and product boundary

After #1771, the public `SchemaFieldRoutingSession.compile()` produces
non-executing original P2 plans, selected output fields and dependency edges,
but the caller sees only **names** for required input parameters. Let a host
LLM/RAG agent inspect the parameter *shape* without looking up provider
internals, executing a tool or receiving private source documentation.

## Considered approaches

- **Return raw `ParameterSpec` / complete JSON Schema:** rejected: unscoped
  `$defs`, enum, descriptions, wire aliases, semantic IDs and default values
  can mention hidden/private fields. Existing data-scope code explicitly
  strips that content.
- **Return names only:** already implemented; does not describe types,
  requiredness or parameter location.
- **Chosen:** immutable, bounded `PaperPlanParameterMeta(name, required,
  location, json_types)` on each `PaperPlanCall`. `json_types` is an ordered
  tuple of recognized public primitive JSON type labels; empty means the
  source schema did not supply a safely exposable type. No values, nested
  schemas, free text or original wire metadata.

## Implementation plan

1. Tests RED in `tests/test_paper_typed_tool_plan.py` for a 500-route
   shared-root consumer input (`customer_id`, required, `argument`, `string`),
   direct no-argument route, metadata with private/untrusted source annotations,
   current data-scope visibility, and mid-compilation metadata revocation.
2. Add `PaperPlanParameterMeta` and the `parameters_meta` immutable receipt
   field in `src/schemarouter/paper_typed_tool_plan.py`, derived ONLY from
   original currently scoped endpoint's parameter list; avoid copying nested
   JSON schemas or `wire_name` / `semantic_id` / descriptions.
3. Re-evaluate the same metadata when `_check_current_call_scopes` runs twice;
   fail closed on differences even if the route's schema fingerprint remains
   constant. Existing P1/P2 source proof rechecks remain unchanged.
4. Export via `src/schemarouter/__init__.py` and the public API contract test;
   demonstrate via `examples/schema_only_field_routing.py` and README.
5. Run red→green tests, broad native/paper regression, whole-repo Ruff,
   targeted Pyright, and review. Publish a stacked **Draft** PR on #1772,
   with #1356 release HOLD unchanged.

## Non-goals and risks

No provider adapters, data fetching, auto-parameter value inference, raw
input JSON Schema, or executable capability. This deliberately does **not**
expose constraints such as enum bounds or pattern; if a host needs trusted
execution, the existing executor must validate the original registered
parameter schema after separate authorization. A declaration may omit type;
`json_types=()` is honest uncertainty, not unrestricted acceptance.

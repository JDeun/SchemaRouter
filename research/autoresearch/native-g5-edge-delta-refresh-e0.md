# #1560 — Canonical typed G5 edge delta refresh (E0, 2026-10-21)

After the source-verified native posting refresh merged in #1669, the
G5 graph still had to rebuild its entire typed edge set. This research-only
engineering slice uses the canonical existing
`update_capability_dependency_graph` instead of introducing a second
planner or compatibility comparator.

- Full `NativeSchemaGraphIndex.build` now retains exact source-derived
  typed root/consumer contracts. The full source build continues to
  fingerprint every registered native tool and all native endpoints.
- `NativeSchemaGraphIndex.refresh(previous, verified_field_index,
  changed_tool_keys=...)` reuses unchanged native contracts, re-derives
  only named changed ToolSpecs, and calls the existing canonical
  incremental graph updater to recompute added/removed/modified incident
  edges. Every unchanged source fingerprint is independently rechecked
  against the post-refresh manifest to reject incomplete hints and
  concurrent drift. No source or model execution is performed.
- Offline E0 adapters verify add/replace/delete/unrelated changes:
  incremental vs full graph capability IDs, *canonical typed edge
  compatibility objects*, root and consumer counts, EN/KO/JA and
  privileged/restricted route visibility. Negative tests reject
  missing changed keys and stale sources.

**Engineering limitations:** current refresh still performs an O(all
registered tools) fingerprint pass; no atomic mutation journal, backend
p95/p99 latency win, fully journal-driven SQLite graph update, multi-hop
planner, independently source-native relevance/no-fit, remote execution
or E2 task success is established. G5 remains explicit opt-in; default
lexical K5, frozen #432 and #1356 release HOLD are unchanged.

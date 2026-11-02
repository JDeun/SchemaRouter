# Prepared Structured Understand Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development. Mark steps after evidence.

**Goal:** Expose the existing original-paper structured Understand → P2 typed graph compiler through a first-class reusable schema-only session.

**Architecture:** Session provides its detached owner catalog and pinned native index to the existing strict typed compiler. The host supplies a reviewed intent registry and untrusted structured understanding; the original graph proof validates source and authorization. No provider access or model invocation.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, Ruff, Pyright.

**Spec:** `research/autoresearch/prepared-understood-routing-1775-design.md`

## Global Constraints

- Exact paper K5, 1- or 2-hop G5 only; preserve non-executing API.
- No provider-specific metadata, HTTP/MCP/SQL requests, or inference from model hints.
- Preserve caller's existing `compile(query)` and `retrieve_authorized()` behavior.
- Stack Draft PR atop #1774; no merge/release promotion.

## Review Focus

1. Model-proposed `parameter_hints` resembling valid host arguments never attach to a call.
2. Named graph route is denied or its required field becomes hidden after preparation.
3. Registered schema changes after session creation.
4. Invalid/unknown intent, mismatched owner catalog, and mutable registry inputs.
5. Direct ready status must still have no execution authority.

## Task 1: Public structured Understand/P2 route

**Files:** `src/schemarouter/field_routing_session.py`, `src/schemarouter/__init__.py`, `tests/test_prepared_understood_routing.py`, `tests/test_public_api.py`.

**Interfaces:** consumes `compile_paper_understood_graph_plan`, `PaperUnderstanding`, `PaperIntentRegistry` and the prepared `_router`, `_catalog`, `_index`; produces `SchemaFieldRoutingSession.compile_understood(...) -> PaperTypedToolPlan` and three public strict contract classes.

- [ ] Write a one-hop RED test calling `session.compile_understood` and asserting exact route IDs, fields, typed parameters, one graph binding and ignored forged input hint.
- [ ] Run test: expected failure is missing session method.
- [ ] Implement minimal session method delegating to `compile_paper_understood_graph_plan` and export owner-reviewed types.
- [ ] Run RED test and public API export checks: expected PASS.
- [ ] Add direct explicit host root, two-hop graph, denied/stale source, invalid bounds and no-execution test cases; verify each RED before new behavior when needed.
- [ ] Run affected paper, graph, scope, public and session tests: expected PASS.

## Task 2: Documentation, example, review and publication

**Files:** `examples/schema_only_field_routing.py`, `README.md`, `research/autoresearch/paper-toolcall-implementation-e0.md`.

**Interfaces:** consumes Task 1 `compile_understood`; produces a runnable non-executing 1-hop example and precise resume note.

- [ ] Demonstrate owner-reviewed intent + structured hint resulting in schema-only route fields and bindings; no source call.
- [ ] Document the difference from actual model inference and from execution.
- [ ] Run Python example, targeted regression, Ruff, Pyright and `git diff --check`.
- [ ] Review entire change for approval/visibility leaks and test gaps; fix Important issues via RED→GREEN.
- [ ] Commit, publish stacked Draft, monitor exact-head CI. Preserve HOLD.

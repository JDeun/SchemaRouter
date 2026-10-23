# Strict one-native-action JSON E1: preregistered Qwen grammar intervention

**2026-10-23 · #1723 · E1 local original-source only · separate from diagnostic and original baseline · NOT E2**

## Hypothesis

The opt-in non-intervening E1 structure-label experiment identified a
`bare_json_tool_action` from genuine pinned Qwen3-0.6B KO FULL/lexical
turns. The unchanged canonical parser treats such text as a final response,
rather than a native tool call. This is a falsifiable **model/host grammar**
hypothesis, separate from CodeGraph's indexed search speed and graph context.

## One narrowly bounded intervention

The research-only opt-in `--experimental-bare-native-json` activates
`parse_native_action_optin` **only in the local native baseline arms**
(FULL, lexical K5, typed G5), with the original registered **four route**
source already used in #1722. The surgical G5 schema request parser is
unchanged. The mode is forbidden for the twelve-tool FULL-menu-cap
control and **never enabled in product, frozen harness or default routing**.

1. Run the **unaltered original** `parse_one_model_action` first.
   Canonical `<tool_call>…</tool_call>` calls and all final outputs remain
   identical to baseline.
2. Only for an otherwise-final response that is **one top-level JSON
   object** with `name` and `arguments`, strict reparse it if its
   exact function name is in the host's *already offered original tools*
   and is not the reserved schema meta-action.
3. Insert only the standard `<tool_call>` envelope and pass it back to
   the **original strict parser**. It must still satisfy exactly one
   valid qualified function name, original scalar-only arguments, no
   duplicate JSON keys, no NaN/Infinity, no array/object-valued native
   arguments and no partial/multiple calls.
4. Existing original route selection, authorization/data-scope,
   registered-source fingerprint, required argument binding and read-only
   native executor remain unchanged. No tool is inferred from graph
   rank, private evaluator gold, a previous failure or model-generated
   free text that is not one valid original native call.
5. A bounded numeric `accepted_bare_json_calls` counter is added to
   each treated baseline arm. The original fixed-allowlist
   `action_structure_labels` still observes the **raw action shape**
   but never exports the model output or hidden details.

This is a **new grammar intervention** with its own report field
`bare_native_json_treatment=STRICT_ONE_OFFERED_NATIVE_ONLY`. Never
retroactively edit previous baseline runs or conflate model-size differences
with graph-context savings.

## Controls, risks and interpretation

- Same registered 4-route owner-reviewed local source, EN/KO/JA,
  principal, task, strict K5, model checkpoint/revision, deterministic
  decoding, turn cap and final task scorer as previous genuine model
  benchmarks. Repeated executions can still exhibit runner/runtime
  variation, so preserve per-run exact source/model/workflow references.
- Genuine Qwen3-0.6B and separately pinned Qwen3-1.7B are different
  *model* cohorts, not pooled task denominators.
- FULL and lexical are independently normalized only when currently
  offered; adding an accepted **first** native tool action is not
  a complete 2-hop task. Verify continuation, argument provenance,
  source calls, input/output tokens, and strict final success.
- Over-K 12-route FULL remains `BLOCKED_MENU_CAP`, outside this new
  experiment; do not simulate FULL by 5-tool fragments. Scripted
  success in regression tests is **not evidence of model capability**.
- A Qwen response with **multiple native calls in one turn** remains
  strictly refused, even if one portion looks authorized. Do not
  split, re-rank, replay or silently repair it. A separately designed
  multi-action protocol would need its own security audit.
- No real Open-Meteo HTTP, commercial licence entitlement, external
  author-private E2 (#1346), or release (#1356 HARD HOLD) is implied.

## Reproduction

```bash
python -m pytest -q tests/test_research_codegraph_bare_json_adapter_e1.py tests/test_research_codegraph_local_multiroute_e1.py
python -m scripts.research_codegraph_local_multiroute_e1 --cohort local-source --catalog-size 4 --language ko --diagnose-model-actions --experimental-bare-native-json --out /tmp/qwen06-strict-json-e1.json
python -m scripts.research_codegraph_qwen17_local_e1 --cohort four-route --language ko --diagnose-model-actions --experimental-bare-native-json --out /tmp/qwen17-strict-json-e1.json
```

The dedicated `CodeGraph Qwen Strict Bare Native JSON E1 DEV` GitHub workflow
runs six genuine pinned-model/EN-KO-JA study cells and retains JSON
artifacts. Results MUST be compared with baseline **original** actions
`39922466111`, `39923618201` and sidecar diagnosis
`39926238548`, `39926238349`. If task completion remains zero, report
that negative. Changes in strict success are attributable at most to the
separate E1 grammar intervention **within these synthetic local cases**,
never to CodeGraph retrieval or an independent production task set.

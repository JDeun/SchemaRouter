# Evidence-to-Action v1 ablation and error analysis

This analysis covers the deterministic seed corpus only. It is a contract-regression result, not an external model benchmark.

## Result

| Condition | Premature | Unsupported | Exact action | Provenance | False refusal |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vanilla agent | 0.375 | 0.375 | 0.625 | 0.625 | 0.000 |
| SchemaRouter routing only | 0.375 | 0.375 | 0.625 | 0.625 | 0.000 |
| SchemaRouter + evidence gate | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 |

Routing exactness alone does not remove unsupported consequential actions in this seed. The typed evidence gate removes all three deliberately unsupported actions without refusing any of the five supported actions.

## Failure slices

The three routing-only failures isolate different contract dimensions:

- **license completeness** — `act_missing_license` acts with provenance but without the required licence evidence.
- **unit completeness** — `unit_sensitive_missing_units` acts without the required unit declaration.
- **source-type identity** — `source_type_mismatch` acts when calculated evidence is available but experimental evidence is required.

The gated condition refuses each slice locally. No model assertion is allowed to fill the missing requirement.

## Ablation interpretation

This seed supports only a narrow causal claim: holding the deterministic action policy fixed, adding the evidence gate changes the three unsupported cases from execute to refuse. It does not establish LLM-level generalization, SafeActBench performance, statistical significance, or latency/token cost.

A proper external ablation must independently toggle provenance, licence, units, source type, entity binding, freshness, and corroboration, and report denominators for action-eligible and refusal-eligible cases separately.

## Known gaps

The minimal implementation does not yet claim support for freshness timestamps, entity/identifier binding, or multi-source corroboration at the single-route boundary. Corroboration above one fails closed until an explicit aggregation boundary is used. These are research extensions, not silently inferred evidence.

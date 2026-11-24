# #1889 — disposition of remaining 25 archived-label failures

Source: exact-head stability E0 run [45337218898](https://github.com/JDeun/SchemaRouter/actions/runs/45337218898), artifact 14894895446, SHA256 `41adc57869004a0c3e0db984293e31971181b57a40eda4abba2977bff2cf2382`. Original frozen source `368116746170d6dd0d95a91352daba8abc42ca13`. The actual baseline is 77/102 complete pending host inputs and 103/110 tool/field set parity. A disposition is not a claim that the underlying user task has been solved. Keep the archived-label arm, and keep explicit differences from it as separate diagnostic controls.

| Query IDs | Count | Disposition |
|---|---:|---|
| g038, g043, g092 | 3 | `elastic_modulus` ambiguous physical quantity. Owner can request explicit bulk/shear moduli; no universal alias. |
| g039 | 1 | Source-backed magnetic-property aggregate: moment AND ordering. |
| g045 | 1 | Mixed formation, crystal structure, space group and lattice parameters. Source/type ambiguity, missing complete lattice contract; retain. |
| g048, g057 | 2 | Frozen PubChem lacks boiling/melting point, density, solubility and other requested fields. Do not claim availability; xlogp not unrestricted logP equivalence. |
| g051, g054 | 2 | More than eight extracted needs, plus absent chemistry properties. Explicit budget_unsatisfied; no truncation promoted to success. |
| g059, g060, g061, g065, g066, g067 | 6 | Literal query subject was incorrectly emitted as an output. Test a separate minimally corrected role arm, keeping other output labels unchanged. |
| g068 | 1 | Keywords are absent from arXiv frozen output. Keep unresolved in the minimal correction arm; do not count the existing broad research-paper-only control as a repair. |
| g077–g082 | 6 | COD exposes space-group symbol, cell lengths a/b/c, volume, elements, not full lattice angles or atomic structure. Support explicit cell-length query only; preserve full structure/lattice failure. |
| g089, g095 | 2 | Young's modulus absent; do not substitute bulk/shear modulus or infer a tensor/isotropic formula. |
| g097 | 1 | Decomposition energy not reviewed as the same thermodynamic quantity as hull energy; keep unresolved. |
| Total | 25 | 1 direct source-contract correction; 6 minimal role corrections in a separately labeled arm; 18 unsupported, ambiguous or budget-limited. |

All of these are exposed development cases. Do not optimize the catalog after reading actual model pilot scores and then call the same cohort independent. The original paper used qwen3.5-122b-a10b, temperature 0, thinking disabled, frozen simulated retrieval and same-model judge. Its historical executable metric checks tool/field/parameter names but does not in fact check required input completeness. Keep that historical metric separate from typed coverage and real parameter readiness.

Next: run original router, prompt-only, and current prepared paper path with a genuine common model and the original pinned fixture/reader/judge, measuring plan scores and total measured model usage. Use only question text for current Understand; no archived labels, named-tool hints, source hints or gold injected. The original simulator retrieves by query ID and projected field names even if parameters are missing. Thus reader scores remain projection-level simulated evidence, not actual provider execution or production-quality answer accuracy. Full same-model rerun requires an approved original vLLM endpoint and credentials; public CPU Qwen pilot is a different checkpoint and cannot reproduce the numerical claims of the 122B paper. No external E2 or release promotion.

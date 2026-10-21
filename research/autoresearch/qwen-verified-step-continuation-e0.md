# One bounded verified-step continuation, opt-in E0 hypothesis

## Provenance and scope

Observed actual pinned Qwen3-0.6B + Open-Meteo E1 run #39529912020 /
artifact #12314808569 returned **three `premature_final` failures** across
the six EN/KO/JA exposed task episodes, plus one provider geocode
`connect_timeout`. That result does not imply a formatting-only defect.
Even after strict E1 failure diagnostics landed in #1584, no publisher
independent E2 exists; original strict source/final oracle MUST remain
unchanged.

This PR changes only an explicitly opt-in keyword
`evaluate_one(..., evidence_reprompt_budget=1)` in the already existing
research-only weather episode harness. Default `0` retains original
behavior and output key set. This does **not** change SchemaRouter's
public router, its selection default, native provider admission,
Open-Meteo host/client, any published source data or model weights.

## Host-evidence-gated continuation

Only after an *actually validated, host-authorized* geocoding operation
has completed, with no weather observation yet, if the model emits an
early final, the host appends **one fixed host-authored reminder** (not
raw prompt/coordinates/provider content) into the existing Nous history.
The reminder asks the *model* to select the currently offered original
weather operation using its already-observed coordinates. It **does not
execute or select the native tool**, synthesize source values or forgive
wrong arguments. One reminder consumes the existing fixed four-turn cap.
Malformed tool responses, denied routes, no validated geocode, bad
coordinates, transport failure, or a second early final remain failures.
Final JSON/value/unit/time strict oracle is unchanged.

Test-only `httpx.MockTransport` proves with *scripted model output* that
original default stops after geocoding, while the opt-in script can
subsequently invoke the exact original valid second source and produce
the same strict final if the MODEL emits that valid call and correct
final. Tests also deny wrong arguments, exhausted reminder, premature
final before ANY source, incorrect source-grounded final and invalid
budgets. Output publishes only the aggregate integer number of
reminders when opt-in, never source result values or model text.

## Nonclaims and next evidence

**No independent task-success uplift measured.** A scripted agent
showing a possible successful continuation is NOT real Qwen recovery.
This is an E0 behavioral hypothesis on previously exposed task types;
future *separate*, preregistered original-source Qwen comparison must
report supported final-pass, incorrect call attempts, provider GET count
and CPU/tokens including the extra turn, without score tuning on this
exposed case. The currently automatic E1 workflows still run default
`evidence_reprompt_budget=0`, so their results cannot be used to
attribute performance to this opt-in path.

Provider IAM, independent #1346 cases, #1477 full-pipeline E2,
calibrated No-fit (36/36 unsupported semantic shortlists were nonempty)
and release #1356 remain unsolved. Frozen #432 SR-5/FULL/ORACLE
negative evidence remains unchanged.

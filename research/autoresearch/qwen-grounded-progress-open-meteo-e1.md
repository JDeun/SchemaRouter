# Qwen3 source-grounded progress notice — actual Open-Meteo E1

Issue [#1579](https://github.com/JDeun/SchemaRouter/issues/1579).

## Actual observed failure

Three previously disclosed EN/KO/JA tasks on fixed original local
Qwen3-0.6B and real Open-Meteo HTTPS show repeated **premature_final**
right after a successfully observed geocode, with no validated
current-weather source response. Run 39176697976: EN both arms,
JA old arm. Run 39179362868 with symmetric one GET transport retry:
EN both arms, JA old arm. The model sometimes fails to infer that a
city coordinate is NOT the requested weather reading. Korean public
source transport timeouts are a SEPARATE issue; bounded retry in #1575
does not solve the model's premature final.

## One strictly bounded E1 prompt hypothesis

Use existing `state_ready` host-approved original native tool menu
and compare to `state_ready_progress`. After the model itself has
selected and executed the original geocoding tool, only after its
principal-visible source observation was verified and no actual
current-weather observation has been validated, append an original
host-authored *generic factual progress notice* to the same current
public observation turn. It says a current weather value has not
been observed and the final cannot be substantiated; the model should
use only a currently offered authorized tool if it can supply all
required arguments from validated observations. No route ID, tool
order, coordinates, actual weather data, target answer, hidden source
field, execution action or gold is inserted. Even after this notice
a premature final or model-proposed wrong action **remains failure**,
with no host repair or model output rewriting.

The original `all_visible` and `state_ready` behaviors remain the
default for their respective callers; the new arm is opt-in and
restricted to this explicitly bounded exposed E1 task fixture. The
existing strict `execute_scoped_host_call`, original source/host
authorization, exact input binding and final provider-observed JSON
oracle are untouched.

## Actual live test and limitations

Run one pinned Qwen3-0.6B CPU instance against original real Open-Meteo
HTTPS, alternating `state_ready` and `state_ready_progress` order
by original disclosed EN/KO/JA task, using exactly the same
`transport_retry_budget=1` in BOTH arms. Report success only after
both real model-produced provider calls and a correct source-verified
final. Report all actual HTTP attempts, failure stages, early finals,
and fact-checking errors; no credential/raw URL/coordinates in summary.
No fake provider/model can qualify real model success.

**E1 disclosed author-scripted examples only**: prompt conditions may
overfit the task and limited source surface; three live provider calls
per arm are not stable generalization or production reliability.
No BFCL improvement is implied. Independent external reviewer
permission/source/held-out #1346 and paired real-agent E2 #1477
are absent; original #432 and v0.18 #1356 release HOLD unchanged.

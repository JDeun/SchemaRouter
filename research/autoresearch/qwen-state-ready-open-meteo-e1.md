# Real Qwen3 + live Open-Meteo E1 state-ready native tool menu

Issue [#1572](https://github.com/JDeun/SchemaRouter/issues/1572).
Historical Qwen3-0.6B live original provider source success **1/3**:
[run 39089681858](https://github.com/JDeun/SchemaRouter/actions/runs/39089681858),
EN prematurely finalized, KO completed two calls+strict final,
JA host/native source denied.
Qwen3-1.7B *model-only* candidate also **1/3** on separate dynamic
source run [39091688213](https://github.com/JDeun/SchemaRouter/actions/runs/39091688213),
EN complete, KO/JA source denied. These are exposed three-case E1 negatives.

## Narrow experimental mechanism

The experiment changes exactly one tool-exposure dimension:
`menu_mode="state_ready"` filters the ORIGINAL registered,
principal-approved native tool menu to **unexecuted read-only**
endpoints whose required input parameter *names* have actual values in
host-authenticated request fields or previously validated,
principal-projected native observations. It does NOT insert the expected
next route, hidden native IDs, coordinates, required answer, inferred
aliases, future state or permission; the model still produces calls,
arguments and final values. Provider invocation remains governed by the
existing source-pinned `execute_scoped_host_call` with exact
post-generation required argument checks and authorized caller.
Original `menu_mode="all_visible"` remains default, model/runtime/
prompt fixed.

Run both arms under one pinned `Qwen/Qwen3-0.6B` CPU instance
and real Open-Meteo HTTPS, using identical, already-disclosed
EN/KO/JA source cases. Arm order alternates by language.
Compare strict final value (matched to *that arm's own* original
source observation), actual geocoding + weather calls and failure stages.
No hidden repair/final answer or provider retry, no fallback fixture.
All aggregation is redacted to coarse counts/stages and no raw values.

## Evidence limits

This is **E1 exposed self-authored developer cases** on actual public
provider, not independently published/held-out E2. The model sees fewer
choices due to a trusted state gate; this cannot prove unconstrained
autonomous routing. Source/provider weather and availability drift per
arm, and 3 samples cannot estimate generalization, p99 or safety.
The public BFCL pair-fit no-fit findings (8/16 admits and 144/880 false
accepts) are separate issues and are NOT fixed by this change.
Do not change product default, original #432, v0.18 HOLD #1356 or E2
0/19 until independently authored source/gold/license #1346 and real
paired agent #1477 are verified.

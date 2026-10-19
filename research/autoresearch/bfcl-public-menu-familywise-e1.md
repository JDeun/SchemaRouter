# Original public BFCL menu-size risk correction — exploratory E1

Issue [#1576](https://github.com/JDeun/SchemaRouter/issues/1576).
Original real E5 publisher run [39083941169](https://github.com/JDeun/SchemaRouter/actions/runs/39083941169)
was **8/16 relevant accepted and 144/880 irrelevant falsely accepted**
for the supervised pair-fit model, and 5/16 and 185/880 for raw E5.
The 16/880 cases are separate ORIGINAL public BFCL V4 LIVE category
examples, but labels are now **exposed to the researcher**, so a new
hypothesis tested there is diagnostic only and cannot qualify E2.

## Single prospective methodological hypothesis

A calibrated threshold for the MAX of a tiny source menu can falsely
accept a large native menu, even if each candidate appears somewhat
unrelated. This study conservatively corrects for source menu size.
It uses **the exact same actual pinned E5 vectors and pair-fit model**,
publisher original 100 even-ID positive +120 even-ID irrelevant
training examples, 100 odd-ID positive +120 odd-ID irrelevant
calibration examples. Gold NEVER enters feature inference.
The ORIGINAL historical threshold uses a **per-request MAX** over
negative functions. Applying Bonferroni again to that maximized
distribution effectively counts the menu-size effect twice; its first
exposed experiment measured **4/16 positive admission and 91/880
negative false admission** but is NOT the correct single-function-null
experiment. Preserve those negative metrics separately rather than
quietly retitling the results.

Corrected prospective E1 arm: choose exactly ONE non-relevant
function from each of the 120 original odd-ID irrelevant request menus
using only SHA-256 of that original request ID modulo menu length, **not**
source score, original function name, LIVE label or task gold. This
yields 120 independent-at-request-level, deterministic **single-candidate**
null observations; the original historical per-request MAX threshold and
both baseline arms are left byte-for-byte unchanged.

The single-candidate empirical negative upper-tail probability is

`p(s) = (1 + count(selected calibration negative functions >= s)) / 121`.

Accept a proposed source function only when
`p(max-offered-fit) * number-of-offered-functions <= 0.10`.
Ties count against accepting, and if a menu has more than 12
functions the calibration sample cannot resolve the requested
false-accept tail even at the best score, so **abstain**
rather than extrapolate. No hidden route, publisher answer,
calibrated inference from original LIVE labels, or newly learned
permission is introduced.

The first two historical `e5_raw_cosine` and `trained_pair_fit`
arms remain **exactly unchanged** and are checked to be byte-equal
when opt-in family-wise scoring is enabled.

## Measurement and caveats

On the pinned live public BFCL source, record all **16** positive
offered-function examples and all **880** irrelevant examples with
actual nonempty menus. Report actual live positive admissions and
false refusals **alongside** negative false accepts/refusals. Four
irrelevant empty menus are structurally safe but are not credited
to the classifier's negative denominator. No score editing after
examining LIVE output; save a negative result if false refusal
worsens. Never convert a safe no-call into an automatically correct
tool name or native execution.

This correction is a conservative hypothesis **not a guarantee of
FPR under distribution shift**: original 120 negative calibration
functions and large public LIVE function menus are not exchangeable.
Empirical p-values lack enough resolution for large menus. Public
BFCL is English-dominant and may occur in model pretraining. No
authenticated principal, full original argument AST, native API
execution, other languages, independent EN/KO/JA original publisher
permissions/gold or real agent task success. No product default,
model or release promotion; frozen #432 and v0.18 #1356 HOLD remain.


## Critical empirical-method caveat

Selecting one deterministic candidate per original irrelevant request
avoids the **known double-max correction**, but original function order,
correlated requests and LIVE menu distribution may differ. A 120-case
empirical tail is not a guaranteed calibrated p-value or a prospective
independent error bound under distribution shift. No normalization or
threshold may be tuned to the previously observed LIVE outcomes. Report
the exact current source hash/run and BOTH original and corrected
admission/refusal metrics; if improved specificity causes unacceptable
false refusals, keep the production default unchanged.

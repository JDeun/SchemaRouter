# Event-driven, issue-bound development benchmark queue (2026-10-16)

The existing `research-operation-fit-auto-loop-dev.yml` is now an
**event-driven, bounded DEV-only continuation loop**. It is not an autonomous
coding agent, a release qualification mechanism or a native tool executor.

## End-to-end control flow

1. A main-branch change to the research workflow/manifest, or a deliberate
   `workflow_dispatch`, starts an AutoLab execution. There is no weekly cron.
2. It re-reads the bot-owned #1405 resume cursor. At most **two** of exactly
   three registered local NLI study variants run consecutively in this job.
3. A complete raw 72-case report is uploaded, the narrow measurement-only
   issues are synchronized, and the validated cursor is posted to #1405.
4. Independently, the controller scans **currently open repository issues**
   but is allowed to dispatch only pre-reviewed workflows in
   `research-issue-benchmark-scheduler-v1.json`. It verifies exact Git
   blobs of each runner, scorer and local input fixture, caps budget at
   **two DEV dispatches / 40 nominal runner-minutes**, and checks bot-owned
   #1405 receipts to avoid repeating identical (main SHA, sources, issue)
   requests. Status receipts mean **requested**, NOT passed.
5. If another of the three NLI variants remains, the controller requests
   a `workflow_dispatch` of itself **after persisting** the cursor. GitHub
   Actions concurrency ensures at most one running and one pending. The
   next run starts when GitHub queues it, without waiting for a calendar day.
   If the registered variants are exhausted no continuation is requested.
6. The two existing DEV benchmark workflows run independently and upload
   their own artifacts. They are **not** independent third-party validation,
   and success requires inspecting each downstream run.

## Open-issue mapping

| Issue | Registered study | Current eligibility |
| --- | --- | --- |
| #1208 | Pinned ClicShopping public 4.33 DEV metadata benchmark | Ready for automatic DEV dispatch |
| #839 | Clear Your Tools v2.17.6 development smoke, synthetic scaling catalogs | Ready for automatic DEV dispatch |
| #1311 | ClicShopping maintainer-authored 20-case independent holdout | BLOCKED pending verified source bytes and adjudication |
| #1312 | Native pi-jev + local Laya System One integration | BLOCKED pending native runner qualification |
| #1313 | Historical Laya routing/latency research | Reference only, not blindly repeated |
| #1403 | Previously observed NLI class-collapse study | Reference only until disjoint input |
| #1339 | Frozen 0.14 KO/JA recall generalization | BLOCKED; frozen test cannot be reused as DEV |
| #1224 | Protected SafeAct scoring | BLOCKED external review/runner |
| #1346 | External v0.18 qualification | BLOCKED release HOLD |

Other open research issues are **automatically discovered and listed as
suggestions**, not dynamically converted into GitHub shell commands. Adding
an automatically executable experiment requires a reviewed registry change
that pins its exact files, action, issue identity, cost, dependencies and
DEV status. In particular **no LLM-generated hypothesis may authorize its
own dispatch or release**.

## Scope and limitations

- A request for `workflow_dispatch` is not a claim that the downstream
  benchmark started, completed or passed. GitHub's Actions queue controls
  actual start time. Source SHA and workflow run IDs must be recorded for
  final evidence.
- The bot may create and close **only its own narrow measurement-complete
  NLI AutoLab issues**, following full row verification. It cannot close
  external #839/#1208, parent #1405 or release #1346 as a result of a DEV run.
- A GitHub workflow invocation that succeeded but whose receipt comment
  failed could be requested again on manual retry. The bounded allowlist
  and concurrency prevent arbitrary jobs, but dispatch is not an exactly-once
  distributed transaction.
- The candidate research loop is finite, not a generative search that
  invents and executes arbitrary novel model architectures. Human-reviewed
  candidate registration is needed after the allowlisted set is exhausted.
- The 72 examples are development-only and the variants were authored after
  looking at historical failures. An independent confirmation corpus and
  real provider tool activation remain hard requirements.
- Frozen v0.14, #1346 independent benchmark gate and v0.18 #1356 HOLD
  are unaffected. No tag, release, write to product code or PR auto-merge
  occurs from the experiment controller.

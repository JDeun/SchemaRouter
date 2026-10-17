# Sanitized opt-in agent failure-stage witnesses — E0 only

**Scope:** #1477 Milestone A post-execution observability. This is NOT an
independent held-out E2 study, a model-quality result, or another executor.
No modification to published #432 outcomes, legacy evaluation conditions,
product defaults, or v0.18 release gates.

`scripts/research_agent_stage_evidence_e0.py` accepts the existing
`run_generated_episode` **raw trusted-grader output** only for the isolated
`EVAL-FIXED5-OPTIN` synthetic condition. The candidate selector and model
must never receive this raw record: `attempts`, `required_routes`,
`expected_at_step`, `final_text`, hidden parameters, and fixture gold
belong solely inside the trusted grader AFTER the task completes.

The standalone helper currently emits one sanitized JSONL record using:
- validated source git revision (40 hexadecimal characters) and source/corpus
  SHA-256 (64 hex characters); these are shape checks, **not authenticated
  provenance**, source license clearance, or independent-author validation;
- an HMAC-SHA256 of a private task identity using a separately supplied
  >=16-byte trusted key, never a public unsalted task hash or raw query;
- strict E0 condition, language, synthetic-dev evidence tier and a hard-coded
  `independent_e2_qualified=false`;
- **only** enumerated post-execution stage observations, visible K<=5
  candidate counts, and explicitly allowlisted nonnegative numeric metrics.
  No raw tool IDs, arguments, provider errors, observations, natural-language
  model output, gold, credentials, chain of thought, or task identity.

Stage observations are NOT inferred root causes. Multiple directly observed
stages may coexist in an unsuccessful episode. In particular,
`wrong_operation_attempt_observed` is an AFTER-THE-FACT synthetic fixture
grader comparison, never a query-time oracle. `unclassified` is emitted
when evidence cannot support a more specific stage. These fields do not
establish state-propagation or final-answer faithfulness; both require
separate genuinely instrumented witnesses (#1348).

`EVAL-FIXED5-OPTIN` output can be redacted only **after** the trusted
evaluator has computed these witnesses. The existing
`run_generated_episode(..., experimental_agent_tool_surface=...)`
now optionally accepts a trusted `E0TraceProvenance` with source revision,
corpus hash, private HMAC key and seed. It **requires both** the existing
principal-scoped view and opt-in fixed-K selector; it computes stage witnesses
only from the raw trusted `episode_record` after all synthetic turns and then
adds sanitized `e0_stage_evidence` to the existing safe `public_trace`.
No gold, raw attempts or private key is given to the model, selector, or public
return. The default research conditions remain untouched.

This is a real opt-in producer/consumer integration into the **existing
frozen synthetic executor**, not an integration into the separate trusted
bound-host `router.execute` bridge. Full independent E2 still requires
approved source/authentication/case manifests and native agent/provider
observations; the E0 host bridge is not a customer tenant evaluator.

Do not publish the raw-row inputs or the private HMAC key. Do not interpret
shape-valid synthetic DEV traces as independent EN/KO/JA production evidence.
`#1346` remains the sole independent-source intake ledger. `#1356`
(v0.18.0) stays HOLD.

# Original public JSONPlaceholder demo REST API through strict native G5 (E1)

**2026-10-19; source-host E1 only, fake demo data.** Tracks [#1545](https://github.com/JDeun/SchemaRouter/issues/1545), [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), [#1477](https://github.com/JDeun/SchemaRouter/issues/1477). Not an independently authored agent task E2 and NOT business-source truth.

## Rationale: demonstrate where strict original G5 actually connects

The previous original live [Open-Meteo two-HTTP-hop experiment](open-meteo-live-two-hop-e1.md) was a genuine fixed-host provider-bound workflow, **not** a full G5 auto-joined edge: the original geocoding needs a city/country/language request, the external response is an array of possible city records, and its flat scalar representation is explicitly created by a trusted source-specific adapter. The current G5 refuses to assume those records jointly co-occur as a flat no-input root. Do not erase this limitation by dropping real JSON Schema constraints or by calling a host-projected view "raw source native."

For an **original provider** whose actual first record *is* one flat object with a simple no-parameter route, we can now test a complete source-driven G5 edge and real invoker transport without changing G5 rules:

- Original provider [JSONPlaceholder official guide](https://github.com/typicode/jsonplaceholder/blob/master/templates/GUIDE.md): `GET https://jsonplaceholder.typicode.com/posts/1` is one **fixed, host-chosen public fake post** object containing integer `userId`.
- `GET https://jsonplaceholder.typicode.com/users/{id}`: user resource lookup with the first post's **actually observed** integer `userId`, not a hardcoded second URI. The host locally attests semantic ID `demo.user_id` for the post's `userId` and second operation's `user_id` argument. Provider-origin source/field names are retained and original declarations are pinned to the code review; the host does not grant semantic relationships to other tools.
- Exactly one native typed G5 edge, principal-scoped `source→target`. Existing `SchemaRouter.execute` twice, with no direct invoker bypass, no agent model and no graph fast-path bypass; each call has the existing authorization, source fingerprint, original input/output JSON Schema and field projection protections. Source response must contain post id 1 and bounded positive integer `userId`; consumer response id must equal the observed bound integer and username must be a bounded string.
- The bound HTTPS clients use fixed provider host and HTTPS GET routes only; no dynamically supplied hostname, redirect follow, URL query, credentials, authentication scope, mutation or generic open-proxy. Response JSON must be object, content-type JSON, <64KiB, no duplicate keys or NaN/Infinity. The demo output records only aggregate stage/attempt counts and timing (NO username, raw user ID, body, email or HTTP payload).
- An offline `httpx.MockTransport` suite proves exactly two invocations/paths, replayed same observed scalar on second request, bad/missing/null/array/wrong-type post, mismatched second returned id or username, malicious first source body, duplicate JSON key and size bound rejection; current approved alias + authorization denial before transport. Offline fixtures are **E0**, not evidence of real HTTPS.
- Real GitHub Actions runner job performs the source HTTPS requests itself and fails if any response or transport fails, rather than replacing failed remote traffic with an offline mock. Workflow stores a minimal non-sensitive report and exposes the coarse GitHub Actions result and head.

## No inflated inference

JSONPlaceholder is explicitly an **online fake REST API for developers**, so successfully binding its seeded `userId` is proof of original HTTPS contract interop on a **demo provider** only, not independent actual provider factuality, external business tool availability, third-party MCP interoperability, open-world EN/KO/JA selection, true multi-required-input commercial native provider or correct agent output. The English/Korean/Japanese approved alias paths belong to the host, not to a measured language model. The `GET /posts/1` record is host-chosen; this does not test dynamic root user input discovery.

A failed live provider response, CI network restriction or changed source schema is a failed/blocked E1, **not** a green result or neutral score; retain all negative failures as evidence and note demo uptime instability. Do not promote product defaults or change the frozen #432 full-agent benchmark. Independent disjoint [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)/[#1477](https://github.com/JDeun/SchemaRouter/issues/1477) remain unsatisfied, v0.18 [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) remains HARD HOLD.


## Follow-up: explicit host-parameterized original source root (2026-10-19)

M1 #1560 follows merged E0 PR #1596. This is an **additional**, opt-in
actual remote E1 path and does not reinterpret the earlier fixed-URL result:

- The trusted host authorizes the original source route
  `demo_posts.by_post`, supplies integer `post_id=11` (bounded to the
  public demo provider's 1..100 posts), and runs exact original
  `GET /posts/11` over HTTPS. The source response must contain original
  `id=11`; no caller input can set the URL host.
- The existing G5 index, with the exact approved route set at build time,
  requires the original source's `userId` identifier to be bound into
  the downstream required `user_id` before `GET /users/{id}`.
  The second URL uses the **actually observed** source ID, not a post-ID
  lookup table or host-guessed downstream value. The public seed has
  post 11 owned by demo user 2, which tests post-ID / user-ID separation.
- Both requests pass the original bound invoker, principal, fingerprint,
  typed input and output validation, and only publish source-safe
  aggregate success/failure. MockTransport controls include exact paths,
  non-whitelisted inputs, mismatched source IDs, missing approval and
  no-call failure on invalid source data.
- A separate Actions job reaches the unmodified original public demo
  HTTPS source. A failure cannot be replaced by mock data and is **not**
  treated as a false result of G5 routing quality. The fixed original
  `/posts/1` E1 job is retained as a regression control.

**Inference limit:** JSONPlaceholder is intentionally seeded **FAKE**
content. A successful run only demonstrates live provider transport and
strict one-hop host-approved typed dataflow. The host selected the exact
route and post ID, and no EN/KO/JA route intent, unfamiliar provider,
authenticated access, agent E2, external gold, commercial performance or
v0.18 release eligibility was measured. Keep #432 negative, #1346/#1477
E2 external gates and #1356 HARD HOLD unchanged.

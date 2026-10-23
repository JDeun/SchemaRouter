# SchemaRouter research milestones — evidence-gated plan

**Initial plan prepared 2026-10-19; historical initial mapping with a versioned 2026-10-22 live assignment addendum below. Check live GitHub Issues → Milestones for the current state.** This file accompanies [the canonical EN/KO research wiki](../docs/research/research-program-2026.md) and [session tracker #200](https://github.com/JDeun/SchemaRouter/issues/200). The machine-readable [research-milestones.json](research-milestones.json) is a **historical one-time initialization** snapshot, not a continuously updated representation of all later live assignments. Do **not** infer task success from a milestone assignment.

## Why and how

Milestones are **research gates** (what must be demonstrated), **not estimated delivery dates**. One open issue belongs to at most one milestone; issue #200 remains a **cross-cutting tracker**, not an artificially forever-open milestone blocker. Keep parent-child links in the issue body; GitHub milestone assignment does not replace those links. Avoid creating one issue/milestone for every local model variant, failed test, or rerun.

| Stage | Issues | Exit evidence — do not mark done for CI-green alone |
| --- | ---: | --- |
| **M0 — Trust and authorization** | 4 | No hidden-field exposure or unauthorized destructive action; original source, policies and grounded predicates are tested |
| **M1 — Source-native typed G5 graph** | 4 | Registered original heterogeneous protocols and conjunctive FieldGroup completeness under authorized fixed K; executable links verified separately |
| **M2 — Multilingual fit and no-fit** | 5 | EN/KO/JA required-tool/field recall and support-vs-unsupported error rates on preregistered independent original sources; CPU cost |
| **M3 — Independent task and provider evidence** | 10 | Source-authorized disjoint E2 full-task and final-grounding results, plus truthful `BLOCKED_EXTERNAL` ledger |
| **M4 — v0.18 controlled release** | 1 | External/source/security gates and protected checks explicitly approved; held release PR #1356 is **not automatically approved** |
| **M5 — Postrelease adoption and follow-up** | 6 | Released-version comparison, evidence-backed paper/adoption and optional local Laya/pi-jev trials; **not a release blocker** |

### Historical 2026-10-19 initialization mapping (30 assigned, 1 cross-cutting)

- **M0 (4):** [#1268](https://github.com/JDeun/SchemaRouter/issues/1268), [#1269](https://github.com/JDeun/SchemaRouter/issues/1269), [#1450](https://github.com/JDeun/SchemaRouter/issues/1450), [#1532](https://github.com/JDeun/SchemaRouter/issues/1532).
- **M1 (4):** [#1530](https://github.com/JDeun/SchemaRouter/issues/1530), [#1535](https://github.com/JDeun/SchemaRouter/issues/1535), [#1545](https://github.com/JDeun/SchemaRouter/issues/1545), [#1560](https://github.com/JDeun/SchemaRouter/issues/1560).
- **M2 (5):** [#1339](https://github.com/JDeun/SchemaRouter/issues/1339), [#1403](https://github.com/JDeun/SchemaRouter/issues/1403), [#1510](https://github.com/JDeun/SchemaRouter/issues/1510), [#1582](https://github.com/JDeun/SchemaRouter/issues/1582), [#1583](https://github.com/JDeun/SchemaRouter/issues/1583).
- **M3 (10):** [#796](https://github.com/JDeun/SchemaRouter/issues/796), [#839](https://github.com/JDeun/SchemaRouter/issues/839), [#1208](https://github.com/JDeun/SchemaRouter/issues/1208), [#1211](https://github.com/JDeun/SchemaRouter/issues/1211), [#1224](https://github.com/JDeun/SchemaRouter/issues/1224), [#1228](https://github.com/JDeun/SchemaRouter/issues/1228), [#1311](https://github.com/JDeun/SchemaRouter/issues/1311), [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), [#1348](https://github.com/JDeun/SchemaRouter/issues/1348), [#1477](https://github.com/JDeun/SchemaRouter/issues/1477).
- **M4 (1):** [#1345](https://github.com/JDeun/SchemaRouter/issues/1345); its held PR [#1356](https://github.com/JDeun/SchemaRouter/pull/1356) **MUST NOT BE MERGED** without separate explicit release go/no-go.
- **M5 (6):** [#199](https://github.com/JDeun/SchemaRouter/issues/199), [#576](https://github.com/JDeun/SchemaRouter/issues/576), [#584](https://github.com/JDeun/SchemaRouter/issues/584), [#1312](https://github.com/JDeun/SchemaRouter/issues/1312), [#1313](https://github.com/JDeun/SchemaRouter/issues/1313), [#1344](https://github.com/JDeun/SchemaRouter/issues/1344).
- **Not assigned (global):** [#200](https://github.com/JDeun/SchemaRouter/issues/200).

### Live GitHub assignment addendum — verified 2026-10-22

The following assignments were applied to GitHub Issues after the initial 30-item initialization plan, and verified in the live issue state:

| Issue | Verified live milestone | Intent and disposition |
| --- | --- | --- |
| [#1700](https://github.com/JDeun/SchemaRouter/issues/1700) | **M1 — Source-native typed G5 graph** | Continue work only against an identified integrated bottleneck; prioritize genuine native-path completeness and agent task outcomes over standalone CPU micro-tuning |
| [#1711](https://github.com/JDeun/SchemaRouter/issues/1711) | **M5 — Postrelease adoption and follow-up** | CodeGraph research/experiments remain nonblocking for G5 vertical-slice implementation |
| [#200](https://github.com/JDeun/SchemaRouter/issues/200) | **Unassigned (intentional)** | Cross-cutting session and evidence tracker, not a permanent milestone blocker |

This is a **versioned addendum**, not a request to rerun or silently repin the protected initializer. Do not edit the original 30-issue JSON, the approved Git blob `3df25049ab9854e54961c6fb77518236b9ed92ee` or the once-only workflow to represent these incremental live assignments. Replacing those guards would require a **separate, reviewed migration** with explicit maintainer authorization and clear write-permission boundaries. A preview may inspect state; it does not assign issues.

## Milestone critical path

```text
M0 trust/security ---+
                     +--> M3 independent provider/task E2 --> M4 release decision
M1 typed G5 graph ---+                   ^
                     +--> M2 multilingual/no-fit ----+
                                                     M5 non-blocking post-release
```

M0/M1 and parts of M2 can proceed concurrently on protected branches; M3 can begin external source acquisition concurrently but cannot claim full qualification until the needed source-native software and safe model gates pass. Do not use an empty or indefinitely blocked third-party dataset to mark `E2: PASS`. Gate status remains `BLOCKED_EXTERNAL` until original author and licensing/permission evidence arrives. The release candidate #1356 is **HARD HOLD** regardless of any milestone percentage.

## 운영 원칙

- **날짜를 임의로 채우지 않습니다.** 예상 완료일은 외부 데이터 확보·사전등록·실행 권한 확인 후에만 설정합니다.
- **마일스톤 진행률은 완료 이슈의 비율일 뿐 성능 지표가 아닙니다.** 모든 자식 이슈가 닫혀도 안전/외부 검증 승인 없이 상위 릴리스 게이트를 통과하지 않습니다.
- **DEV 부정적 실험도 기록합니다.** E0 구현, E1 실패, E2 독립 검증, `BLOCKED_EXTERNAL`는 동일한 ‘성공’으로 계산하지 않습니다.
- **개별 실험 이슈 남발 금지.** 반복 측정, 추가 모델 후보, 단순 문구 변경은 먼저 해당 상위 이슈의 댓글 또는 연구 위키에 정리합니다.
- **#200은 마일스톤을 배정하지 않습니다.** 최초 31개 이슈 중 30개만 초기화 매니페스트에 배정되었습니다. 이후 #1700(M1), #1711(M5)은 위의 **라이브 추가분**으로 별도 기록합니다.

## 실제 GitHub 마일스톤 적용

The trusted GitHub connector cannot directly create GitHub Milestones or dispatch a workflow. The original protected [manual synchronization workflow](workflows/research-milestone-sync.yml) stays available: **Actions → Research milestones (manual) → preview**, then the maintainer may explicitly run **apply**. Preview has no Issues-write access. Applies require GitHub Issues write permission.

**2026-10-19 one-time initialization request:** a separate reviewed [one-time workflow](workflows/research-milestone-initialize-once.yml) is attached to an explicitly approved change of [the manifest](research-milestones.json), gated on **a push to protected main affecting that exact manifest path**. Before any remote write, the job verifies its **literal approved Git blob SHA `3df25049ab9854e54961c6fb77518236b9ed92ee`**, its declared repository, the exact 6-stage/30-issue/one-tracker partition and the opt-in marker `REQUEST_LIVE_INITIALIZATION_20261019`. Later edits with a different blob cannot re-trigger an approved initialization. A separate future manual apply still requires explicit operator action.

The one-time job cannot execute before its own PR passes the protected branch checks and merges; opening a PR or CI success does **not** create a GitHub Milestone. After it runs, verify the real [GitHub Issues → Milestones](https://github.com/JDeun/SchemaRouter/milestones) and issue assignments, and link the actual workflow run to #200. Failed token permissions, unavailable original issues or conflicting assignments must be recorded as **BLOCKED**, not claimed successful. `#1356` is never merged or tagged by these workflows.

The [synchronizer](scripts/sync_research_milestones.py) reads existing open/closed milestones and all issues before mutation, rejects conflicting ownership and closed milestones early, then re-fetches an issue immediately before assignment. It skips closed issues, does not reopen or close issues, and does not edit contents, approvals, protected CI, model defaults or release state. It is idempotent across retries but partial failure may require an explicit rerun; do not infer whole-batch atomicity from preflight.

**Research history:** [research strategy](../docs/research/research-program-2026.md), [negative held-out result](../docs/research/large-heldout-agent-utility.md), [E2 external release gate](https://github.com/JDeun/SchemaRouter/issues/1346).

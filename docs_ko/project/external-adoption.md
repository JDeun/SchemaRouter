# External adoption과 validation plan

Issue #584는 **maintainer 자신의 repository 밖에 존재하는 evidence**를 추적합니다. Endorsement 수집이 목적이 아닙니다. 다른 project가 concrete SchemaRouter integration을 쉽게 평가하고 결과를 publish하며 limitation을 visible하게 유지하도록 하는 것이 목적입니다.

## Outreach rule

Contribution-first sequence:

1. target project의 기존 tool/MCP abstraction 이해
2. 가장 작은 reproducible integration build/propose
3. runnable example 또는 focused PR 제시
4. integration이 실제로 유용한지 질문
5. real use/evaluation 뒤에만 project/maintainer/logo/quote 인용 permission 요청

Star를 primary action으로 요청하지 않습니다.

## Candidate set — checked 2026-10-01

아래는 **candidate**이며 claimed user가 아닙니다.

| Project | Existing relevant surface | Smallest useful SchemaRouter evaluation | 원하는 evidence |
| --- | --- | --- | --- |
| PydanticAI | toolsets, MCP, deferred tools, ToolSearch | 같은 toolset에 SchemaRouter retrieval을 적용한 external/example ToolSearch strategy | candidate recall, context/tool-schema reduction, PydanticAI execution authority 불변 |
| OpenAI Agents SDK (Python) | MCP servers, dynamic per-run tool filters, approvals/guardrails | Agents SDK invocation/approval을 유지하고 SchemaRouter retrieval로 dynamic MCP allow-set 생성 | filter parity, shortlist size, task success, approval bypass 없음 |
| lastmile-ai/mcp-agent | MCP lifecycle, composable workflow | mcp-agent가 MCP session을 소유하고 SchemaRouter가 discovered catalog를 rank/structure | catalog/shortlist size, task completion, lifecycle compatibility |
| Hugging Face smolagents | Tool, MCP ToolCollection, LangChain reuse | bounded SchemaRouter-selected collection 노출 | selected-tool recall, schema/context size, task success |
| Agno | Toolkit ecosystem, MCPTools include/exclude | per-request bounded toolkit/MCP list에 retrieval mapping | tool-list reduction, task success, latency, incompatibility |
| CrewAI | BaseTool/custom/MCP tools | selected endpoint를 CrewAI tool로 만드는 external bridge/example | bridge correctness, recall, boundary notes |
| Langflow | visual MCP Tools, agent flows | agent tool step 전 typed retrieval custom component/example | real-flow usability, config friction, shape preservation |
| Letta | MCP list/schema/search/call + ranked search | adoption pitch가 아닌 **independent comparison/reproduction target** | reproducible comparison, unsupported behavior, schema/context difference |

Upstream issue/PR 전 canonical repo/docs를 다시 확인해야 합니다.

## Why these targets

Candidate는 many tools/toolsets, MCP discovery, dynamic filtering/search, framework integration point, explicit schema, runtime을 대체하지 않고 bounded retrieval을 평가할 realistic point 중 하나 이상을 이미 가집니다.

따라서 evaluation이 falsifiable합니다. Native search/filter가 같은 문제를 더 잘 풀면 그것도 유용한 evidence입니다.

## Project-specific contribution notes

### PydanticAI

Toolset, MCP, deferred ToolSearch, custom search strategy가 있습니다. SchemaRouter가 ToolSearch를 대체한다고 pitch하지 않습니다. Field-aware typed retrieval이 custom strategy/external boundary로 가치 있는지가 실험입니다.

Maintainer가 upstream example/listing을 원한다고 하기 전에는 SchemaRouter 또는 tiny external example에 둡니다.

Maintainer-owned E0는 [#644](https://github.com/JDeun/SchemaRouter/issues/644), [PydanticAI ToolSearch validation](external-validation-pydanticai.md)에 있습니다. 외부 평가/adoption 전까지 E0입니다.

### OpenAI Agents SDK

Local MCP server는 static/dynamic `tool_filter`, run/agent context, SDK approval/input-output guardrail을 가집니다.

```text
run query
  -> SchemaRouter retrieve candidate tool IDs
  -> Agents SDK dynamic tool_filter exposes that subset
  -> Agents SDK keeps its own approval/invocation semantics
```

Retrieval-only integration이며 SDK approval authority를 duplicate/bypass하지 않습니다.

E0는 [#645](https://github.com/JDeun/SchemaRouter/issues/645)와 [validation](external-validation-openai-agents.md)에 있습니다. Real local stdio MCP lifecycle을 쓰지만 외부 review/reproduction/adoption 전까지 E0입니다.

### mcp-agent

MCP connection/session lifecycle을 이미 소유하므로 대체하지 않습니다. Discovered schema surface를 ranking용으로 import/compile하고 mcp-agent를 orchestrator로 유지합니다. Conversion이 정보를 잃으면 fabricate하지 말고 limitation으로 기록합니다.

E0는 [#646](https://github.com/JDeun/SchemaRouter/issues/646)와 [validation](external-validation-mcp-agent.md)에 있습니다. Native `MCPApp`/Agent stdio lifecycle 및 `tool_filter`를 사용하지만 외부 review/reproduction/adoption 전까지 E0입니다.

### smolagents

MCP/other tool source를 사용할 수 있습니다. Large mixed tool set에서 model exposure 전 SchemaRouter retrieval의 이점을 bounded collection으로 시험합니다. Permanent core dependency보다 self-contained example을 선호합니다.

### Agno

MCP/toolkit layer에 explicit include/exclude가 있습니다. Query-dependent shortlist가 static filtering 이상 가치가 있는지 시험하기 좋습니다. Tool 수 감소만으로 security improvement를 주장하지 않습니다. Execution은 Agno policy/runtime이 authoritative합니다.

### CrewAI

Normal tool abstraction 주변 external bridge/example로 시작합니다. Typed selection/schema preservation 정도의 작은 proof로 충분하며 또 다른 agent lifecycle을 추가하지 않습니다.

### Langflow

Higher-effort UI/integration target입니다. Lower-friction Python integration이 contract를 증명한 뒤 custom component를 고려하며 첫 outreach가 아니라 `help wanted`로 취급합니다.

### Letta

MCP tool search/schema/call을 explicit workflow로 이미 노출하므로 adoption target보다 independent prior-art/evaluation에 적합합니다. Abstraction 차이를 기록하며 억지 winner를 만들지 않습니다.

## Evaluation package

Proposed adopter가 research history를 읽을 필요가 없도록 다음을 제공합니다.

1. 안정 버전 설치:
   ```bash
   pip install schemarouter
   ```
2. framework-specific runnable example 하나
3. 30-second context-reduction demo
4. trust/evidence page
5. 아래 minimal protocol

### Minimal protocol

기록:

- target project version/commit
- SchemaRouter version/commit
- Python/runtime/hardware
- original model-visible tool 수
- shortlisted tool 수
- 전체 노출 대비 제한된 직렬화 스키마·컨텍스트 크기
- test request의 required-tool/capability recall
- task completion 또는 explicit failure
- added routing latency
- invalid/unsupported query behavior
- authority/policy integration notes
- conversion gap/unsupported schema construct

No registered capability가 선택되어야 하는 request를 최소 하나 포함합니다.

Measurement가 실제 model-token based가 아니면 token cost를 비교하지 않습니다. Serialized byte는 bytes로 label합니다.

## 외부 프로젝트 연락용 영문 메시지 예시

상대 프로젝트에 맞춰 간결한 개별 메시지를 작성합니다. 아래 인용문은 해외 유지관리자에게 실제로 전달하는 **영문 템플릿**이므로 번역하지 않고 유지하며, 각 자리표시자와 검증 범위는 전송 전에 해당 프로젝트에 맞게 수정해야 합니다.

> Hi — I maintain SchemaRouter, an MIT-licensed Python layer for typed capability retrieval and schema-aware execution in large agent tool catalogs.
>
> I noticed that <project> already has <specific tool/MCP surface>. Rather than asking you to adopt another framework, I'd like to test one narrow integration: <specific bounded experiment>.
>
> I can prepare the example/PR and keep <project>'s existing runtime/approval semantics authoritative. If the result is not useful, I'll publish that limitation as part of the evaluation.
>
> Would a small reproducible example like that be useful, and if so, where would you prefer it to live?

서로 다른 프로젝트에 동일한 문구를 그대로 발송하지 않습니다.

## Evidence levels

| Level | Meaning |
| --- | --- |
| E0 | maintainer-owned example only |
| E1 | external maintainer/user가 example을 publicly 평가 |
| E2 | downstream repo가 reproducible branch/PR/test에 SchemaRouter 포함 |
| E3 | downstream default/released path가 SchemaRouter 사용 |
| E4 | independent benchmark/reliability reproduction published |

GitHub star, repo mention, friendly reply는 adoption level이 아닙니다.

## Public tracking

Public/permissioned information만 기록합니다.

| Project | Contact/evaluation URL | Level | Status | Evidence | Limitation / next action |
| --- | --- | --- | --- | --- | --- |
| PydanticAI | [#644](https://github.com/JDeun/SchemaRouter/issues/644) | E0 | maintainer-owned deterministic evaluation | [validation](external-validation-pydanticai.md) | external review 필요 |
| OpenAI Agents SDK | [#645](https://github.com/JDeun/SchemaRouter/issues/645) | E0 | maintainer-owned local-MCP filter evaluation | [validation](external-validation-openai-agents.md) | external review 필요 |
| mcp-agent | [#646](https://github.com/JDeun/SchemaRouter/issues/646) | E0 | maintainer-owned native-lifecycle catalog evaluation | [validation](external-validation-mcp-agent.md) | external review 필요 |
| _other candidates_ | — | E0 | candidate set prepared | this page | outreach/evaluation 미실행 |

Private email address/conversation/unpublished organization name은 publish하지 않습니다.

## Case-study promotion rule

README "Used by"에 넣으려면:

- 최소 E2
- integration/use가 current
- 필요 시 name/logo/quote permission
- measurable outcome **및** limitation 포함

[External case-study template](case-study-template.md)을 참고하십시오.

## Feedback loop

Recurring friction은 onboarding/docs, adapter conformance, framework bridge, packaging/compatibility, benchmark/evidence 중 bounded issue로 만듭니다.

Adopter request마다 새 core abstraction을 만들지 않습니다.

# PydanticAI ToolSearch 검증

Issue [#644](https://github.com/JDeun/SchemaRouter/issues/644)는 PydanticAI의 기존
`ToolSearch` capability 뒤에 SchemaRouter를 custom retrieval strategy로 조합하는 방식을
검증합니다.

## 경계

이 통합은 의도적으로 retrieval-only입니다.

```text
PydanticAI deferred ToolDefinition catalog
              |
              | retrieval-only mirror
              v
        SchemaRouter retrieve()
              |
              | bounded tool names
              v
     PydanticAI ToolSearch strategy
              |
              v
PydanticAI disclosure / lifecycle / execution
```

이 검증에서 SchemaRouter는 PydanticAI의 실행 권한을 넘겨받지 않습니다. 도구를 직접
호출하거나 호출을 승인하지 않고, toolset lifecycle을 관리하거나 PydanticAI의 자체
deferred-tool 메커니즘을 대체하지도 않습니다.

## 재현

근거 표면에 사용하는 의존성은 다음 버전으로 고정합니다.

```text
pydantic-ai==2.51.0
```

필수 CI는 SchemaRouter wheel을 빌드한 뒤 새 가상 환경에 고정된 PydanticAI 릴리스와
함께 설치하고 다음 명령을 실행합니다.

```bash
python scripts/external_validation_pydanticai.py \
  --json-out artifacts/external-validation-pydanticai.json

python scripts/external_validation_pydanticai.py \
  --matrix \
  --json-out artifacts/external-validation-pydanticai-matrix.json
```

`schemarouter`가 설치된 환경이 아니라 저장소 source tree에서 직접 resolve되면 이
스크립트는 유효한 downstream evidence로 실행되는 것을 거부합니다.

## 명시적 no-route disclosure gate

첫 검증에서 중요한 통합 특성이 확인됐습니다. SchemaRouter의 raw lexical score는
**abstention probability가 아니라 recall-oriented score**입니다. 따라서 일반적인 query
token이 free-form tool description에만 존재해도, 실제로 공개할 등록 capability가 없는
상황에서 양의 점수가 나올 수 있습니다.

PydanticAI strategy는 `score > 0`을 지원 여부로 간주하지 않습니다. 다음 bounded
relevance signal 중 하나 이상이 존재할 때만 candidate를 공개합니다.

- 선언된 output field가 query와 일치하는 경우
- 호출자가 tool 또는 endpoint를 명시적으로 선호한 경우
- 일치한 `tool_token`이 description 문구에만 있는 것이 아니라 등록된 tool identifier
  자체에도 포함되는 경우

Raw Top-K score, score component, matched field, 최종 gate signal은 각 case의 JSON
evidence에 보존해 동작을 추적할 수 있게 합니다.

## 측정 항목

결정론적 mixed catalog에는 weather, finance, travel, logistics, software, research,
materials capability가 포함됩니다. 지원되는 case와 명시적 no-route case를 함께
평가합니다.

JSON evidence에는 다음 항목을 기록합니다.

- catalog size와 maximum shortlist size
- 전체 및 공개된 **serialized schema bytes**
- supported case의 required-tool recall
- unsupported-query rejection
- retrieval-task success rate
- 평균 및 최대 routing latency
- retrieval mirror의 input-schema 정확 보존 여부
- case별 selected name과 revealed-schema bytes

Byte 수치를 token 수치로 표현하지 않습니다.

## 고정 scaling matrix

재현 가능한 matrix는 **12 / 50 / 100 / 250 tools**입니다. 초기 계획에는 10-tool
지점이 있었지만 고정된 실제 catalog가 12 tools이고 supported case set도 전체 catalog에
의존합니다. 따라서 실제 tool을 삭제하거나 사후에 case를 바꾸는 대신, 12를 최소
faithful point로 사용합니다.

| Catalog size | 구성 |
| ---: | --- |
| 12 | 전체 고정 real catalog |
| 50 | 12 real tools + 결정론적 synthetic distractors |
| 100 | 12 real tools + 결정론적 synthetic distractors |
| 250 | 12 real tools + 결정론적 synthetic distractors |

Matrix 명령은 모든 run을 하나의 JSON 문서로 출력합니다. 따라서 query set이나
retrieval policy를 바꾸지 않고 required-tool recall, unsupported rejection, revealed
serialized schema bytes, shortlist size, routing latency를 비교할 수 있습니다.

## Fidelity 한계

Mirror는 SchemaRouter retrieval에 필요한 정보만 의도적으로 복사합니다. 대상은 tool
name, description, input JSON Schema, 로컬에서 선언한 semantic output hint입니다.

PydanticAI 전용 execution, approval, timeout, strictness, tool kind, toolset lifecycle,
defer/reveal state는 계속 PydanticAI가 authoritative source이며 SchemaRouter에서
재구현하지 않습니다. 로컬 output semantic hint는 명시적인 평가 metadata이며
PydanticAI에서 추론한 값이 아닙니다.

이 결과는 [external adoption plan](external-adoption.md) 기준의
**E0 maintainer-owned evidence**입니다. 독립 검증이 아니며 SchemaRouter가 native
PydanticAI ToolSearch를 대체하거나 능가한다고 주장하지 않습니다.

[external case-study template](case-study-template.md)도 함께 참고할 수 있습니다.

## 고정 matrix 결과

Canonical workflow run은 `37002468981`, source는
`98b7b804002c99751fc7233938fbcf21fca14f7d`입니다.

Artifact: `external-validation-pydanticai-matrix`  
Digest: `sha256:0f449bba15d993a516887c7e12d705c0f5f5f0d9fe69fb662ee20a0d84d6a820`

| Tools | Required-tool recall | Unsupported rejection | Simple baseline unsupported rejection | 평균 revealed schema bytes | 전체 serialized schema bytes | 평균 routing latency |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | 100% | 100% | 0% | 262.2 | 3,130 | 1.565 ms |
| 50 | 100% | 100% | 0% | 262.2 | 12,972 | 3.954 ms |
| 100 | 100% | 100% | 0% | 262.2 | 25,922 | 6.762 ms |
| 250 | 100% | 100% | 0% | 262.2 | 64,922 | 16.400 ms |

단순 name/description baseline은 모든 catalog size에서 4개의 supported case 모두
required tool을 유지했지만, 고정된 unsupported case 1개에서는 매번 tool을 공개했습니다.
SchemaRouter는 모든 size에서 required tool을 유지하면서 해당 unsupported case를
거부했습니다. Routing latency는 catalog size와 함께 증가했으며, 이 결과를 composite
score 뒤에 숨기지 않고 그대로 보존합니다.

이 수치는 고정된 5개 case에 대한 결정론적 retrieval-layer 결과입니다. Final model
answer 품질을 측정하지 않으며 SchemaRouter adoption을 독립적으로 검증하는 근거도
아닙니다.

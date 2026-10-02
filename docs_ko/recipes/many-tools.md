# 대규모 tool catalog

agent가 많은 등록 tool과 endpoint에 접근할 수 있지만 매 turn마다 전체 catalog를 받을 필요가 없을 때 SchemaRouter의 장점이 가장 커집니다.

## 제한된 candidate set 검색

가장 관련성 높은 등록 capability만 노출하려면 public retrieval surface를 사용합니다.

```python
candidates = router.retrieve(
    "current Young's modulus for MAT-7",
    k=5,
)

for candidate in candidates.candidates:
    print(candidate.route_id)
    print(candidate.parameters)
    print(candidate.output_fields)
```

retrieval에는 side effect가 없습니다. tool을 실행하거나 실행 권한을 부여하지 않습니다. downstream agent는 반환된 등록 contract 중에서 선택할 수 있지만 실제 실행은 계속 SchemaRouter validation과 policy를 통과해야 합니다.

shortlist를 현재 실행 가능한 local binding이 있는 route로 제한하려면 `retrieve_executable(..., k=5)`를 사용합니다. async 버전은 `aretrieve`, `aretrieve_executable`입니다.

## 원본별 namespace

우발적인 key collision을 피하세요.

```python
ToolSpec(name="search", namespace="materials_project", endpoints=[...])
ToolSpec(name="search", namespace="pubchem", endpoints=[...])
ToolSpec(name="search", namespace="internal_lab", endpoints=[...])
```

## 의미 정보를 schema 가까이에 유지

전체 catalog를 prompt에 반복해서 넣는 대신 신뢰된 domain synonym과 typed metadata를 등록 contract에 둡니다.

```python
FieldSpec(
    name="formation_energy_per_atom",
    semantic_id="materials.formation_energy_per_atom",
    aliases=["formation energy", "energy per atom"],
    json_schema={"type": "number"},
    unit="eV/atom",
)
```

candidate에는 parameter contract, output field, semantic ID, optional unit/qualifier, provider/access identity, read/write/destructive metadata, schema fingerprint와 함께 전체 유효 input/output JSON Schema가 유지됩니다.

## 신뢰된 context가 있을 때만 preferred tool 사용

```python
request = PlanRequest(
    query="LiFePO4 band gap",
    preferred_tools=["materials_project.search"],
    arguments={"formula": "LiFePO4"},
)
```

preference는 ranking을 유도할 뿐 schema validation이나 execution policy를 우회하지 않습니다.

## Output projection은 recall-first로 유지

downstream answer가 예측하기 어려운 context에 의존한다면 field 수를 줄이기 위해 recall을 희생하지 마세요. output intent가 모호하면 SchemaRouter는 선언된 field를 유지합니다.

## 확장 경계

내장 registry/index 경로는 process-local이며 deterministic합니다. 일반적인 application catalog와 외부 agent에 compact Top-K를 노출하는 용도에 적합합니다.

매우 크거나 공유되는 catalog에서는 public `ToolRegistry` 경계 뒤에 persistent/distributed store를 구현할 수 있습니다. 이때 registry versioning, typed capability contract, local execution authority는 유지해야 합니다. retrieval backend가 candidate search를 가속할 수는 있지만 등록되지 않은 route를 만들거나 policy를 약화해서는 안 됩니다.

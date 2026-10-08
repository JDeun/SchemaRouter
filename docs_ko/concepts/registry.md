# Registry와 schema identity

Registry는 planner와 executor가 사용하는 권위 있는 catalog입니다.

## Namespace

Tool key는 충돌을 방지하도록 구성됩니다:

```python
ToolSpec(name="search", namespace="materials", endpoints=[...])
```

다음과 같이 됩니다:

```text
materials.search
```

## Versioning

Registry mutation마다 monotonic version이 증가합니다. Plan은 compile 당시 registry version을 기록하고, 각 planned call은 endpoint fingerprint와 현재 tool fingerprint를 모두 기록합니다. 두 번째 fingerprint는 endpoint contract만으로 표현할 수 없는 tool-level execution origin과 transport identity를 고정합니다.

## Snapshot semantics

`InMemoryRegistry`는 분리된 deep copy를 저장하고 분리된 snapshot을 반환합니다.

따라서 caller가 이미 등록된 `ToolSpec` object를 변경하여 versioned registry write 없이 execution contract를 조용히 바꿀 수 없습니다.

```python
tool = registry.get("weather")
tool.metadata["local_change"] = True

# Registry를 새로 읽어도 값은 변경되지 않습니다.
assert "local_change" not in registry.get("weather").metadata
```

Custom `ToolRegistry` 구현도 detached snapshot 또는 immutable value를 통해 동일한 semantic guarantee를 제공해야 합니다.

Built-in registry는 모든 write boundary에서 전체 `ToolSpec`을 다시 검증합니다. Nested Pydantic collection은 최초 model construction 이후 assignment validation 없이 변경될 수 있기 때문입니다. Construction 이후 endpoint/parameter/field collection이 invalid해진 tool은 snapshot/persist하지 않고 원자적으로 거부합니다.

## Schema fingerprint

Fingerprinting에서는 임의의 descriptive `metadata`를 제외하지만 선언된 planner/execution contract, 즉 endpoint description, alias, parameter, field, side-effect classification, evidence metadata, JSON Schema, `ToolSpec.remote`, 명시적
`execution_metadata`.

`execution_metadata`는 승인된 OpenAPI base URL, 실제 MCP/OPTIMADE runtime target, request-body mode, built-in callable identity처럼 실제 실행 대상을 바꿀 수 있는 신뢰된 adapter/runtime value 전용입니다. OpenAPI source URL 같은 schema-document provenance는 그 URL 자체가 invocation target인 경우가 아니라면 descriptive metadata로 남습니다. Custom adapter는 execution-affecting value를 invocation 시 ordinary `metadata`에서 읽지 말고 `execution_metadata`에 넣어야 합니다. Ordinary `metadata`는 descriptive/observability data이며 authority를 부여하거나 transport semantic을 바꿔서는 안 됩니다.

이전 endpoint 또는 tool execution contract를 기준으로 compile된 plan은 fail-closed됩니다:

```text
endpoint fingerprint != current endpoint fingerprint
 OR
tool fingerprint != current tool fingerprint
 -> SchemaDriftError
```

Invoker binding도 bind 시점의 tool fingerprint를 보유합니다. Transport를 rebind하지 않고 tool contract를 교체하면 `BindingDriftError`가 발생합니다.

운영 진단을 위해 `compare_endpoint_specs()`와 `compare_tool_specs()`는 두 trusted snapshot의 차이를 설명하고 변경을 보수적으로 분류합니다. Compatible report도 fingerprint gate를 우회하지 않으며 caller는 현재 contract에 대해 다시 plan/bind해야 합니다. [Schema drift analysis](../guides/schema-drift.md)를 참고하십시오.

## 영속 SQLite registry

SchemaRouter에는 Python 표준 `sqlite3` module 기반의 dependency-free persistent implementation이 포함됩니다:

```python
from schemarouter import SQLiteRegistry, SchemaRouter

registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)
```

`SQLiteRegistry`는 process restart 이후에도 tool order와 monotonic registry version을 보존합니다.
Single-tool write, replacement, deletion, `update_many()` batch는 transactional합니다. Collision 또는 invalid batch가 실패하면 version을 증가시키지 않고 rollback합니다.

Tool specification은 pickle이 아니라 검증된 Pydantic JSON으로 저장합니다. 따라서 database를 다시 열어도 임의 Python object를 import하거나 실행하지 않습니다. 손상되었거나 key가 맞지 않는 stored row는 `RegistrationError`로 fail-closed됩니다.

Persistent registry는 **schema/catalog state만** 저장합니다. Trusted invoker, HTTP client, credential, approval callback, execution policy는 serialize하지 않습니다. Process restart 이후 application이 trusted execution binding을 다시 설정해야 합니다:

```python
registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)
router.executor.bind("weather", trusted_weather_invoker)
```

Lifecycle을 context manager로 관리하지 않는 경우 `registry.close()`를 호출하십시오.

## Custom registry

Application은 여전히 임의의 structural registry implementation을 주입할 수 있습니다:

```python
router = SchemaRouter(registry=MyPersistentRegistry(...))
```

Custom persistent implementation은 atomic write, snapshot semantic, write-time contract revalidation, concurrency control을 책임져야 합니다.

## 신뢰된 local code가 수정할 수 있는 범위

Application이 execution authority이므로 result가 무엇을 *의미하는지* 선언하고 annotation할 수 있습니다. 하지만 무엇을 실행하는지 또는 response를 어떻게
validated.

| 항목 | 수정 가능 |
| --- | :---: |
| Source가 게시하지 않은 output field | yes |
| `semantic_id`, `aliases`, `path`, `result_path`, `unit`, `unit_normalization`, `qualifiers`, `identifier`, `source_type`, `license`, field `description` | 가능 |
| Endpoint `description`, `operation_aliases` | yes |
| `output_schema`, 이미 publish된 field의 `json_schema` | 불가 |
| `name`, `method`, `path`, `parameters`, `input_schema`, `read_only`, `destructive`, `server_projection`, `execution_metadata` | no |
| Tool `name`, `namespace`, `provider`, `access_mode`, `remote`, `source_type`; endpoint 추가·삭제·이름 변경 | 불가 |
| Source가 게시한 field 제거 | no |
| Endpoint 또는 tool `metadata` | 불가 |

Endpoint `metadata`는 자유 형식 annotation처럼 보여도 변경할 수 없습니다:
Source가 `output_schema`를 publish하지 않은 경우 `_synthesized_output_schema`는 `endpoint.metadata["output_required"]`를 읽어 validation schema를 구성하므로 metadata만 변경해도 response의 필수 내용이 조용히 달라질 수 있습니다.
Amendment는 이를 annotation이 아니라 다른 미등재 aspect와 동일하게 취급합니다.

Amendment는 drift detection을 약화하지 않습니다. Fingerprint는 계속 변경되므로 bound invoker 아래에서 remote schema가 이동하면 여전히 탐지되고 amendment 전에 만들어진 plan도 계속 거부됩니다.

# GraphQL

SchemaRouter는 GraphQL endpoint를 introspect하고 root query/mutation field를 canonical `ToolSpec -> EndpointSpec -> ParameterSpec -> FieldSpec` 모델로 컴파일할 수 있습니다.

## GraphQL endpoint 등록

```python
router = await SchemaRouter.from_url(
    "https://api.example/graphql",
    kind="graphql",
)
```

SchemaRouter는 같은 URL에 제한된 introspection query를 보내 다음을 가져옵니다.

- root query field → read-only endpoint
- root mutation field → non-read-only endpoint
- field argument → typed `ParameterSpec`
- object/input-object type → JSON Schema
- nested output field → planner-visible `FieldSpec` path
- enum → JSON Schema enum value

subscription은 감지하지만 일반 request/response `ToolCall`과 달리 장기 stream lifecycle이 필요하므로 초기 구현에서는 가져오지 않습니다.

## Field selection을 GraphQL selection set으로 변환

plan이 `id`, `metadata.source`를 요청하면 SchemaRouter는 이에 해당하는 GraphQL selection을 전송합니다.

```graphql
query SchemaRouter($id: ID!) {
  material(id: $id) {
    id
    metadata {
      source
    }
  }
}
```

이는 사후 payload filter가 아니라 native server-side field projection입니다. 선택 field가 complex object인데 하위 field가 명시되지 않았다면 전체 subtree를 암묵적으로 요청하지 않고 제한된 기본 scalar/identifier selection을 선택합니다.

## 권한은 로컬에 유지

GraphQL introspection에서 root field가 `Query`인지 `Mutation`인지 알 수 있지만 이는 권한을 **좁히는 데만** 사용합니다.

- root query → `read_only=True`
- root mutation → `read_only=False`

mutation description/tag/name은 mutation 권한을 부여하지 않습니다. 기본 `ExecutionPolicy`는 신뢰된 로컬 정책이 허용하기 전까지 mutation을 거부합니다.

## Secret

인증은 trusted runtime header에 둡니다.

```python
router = await SchemaRouter.from_url(
    "https://api.example/graphql",
    kind="graphql",
    schema_headers={"Authorization": f"Bearer {schema_token}"},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)
```

이 header들은 planner가 선택하는 argument가 아니며 canonical tool contract에 복사되지 않습니다.

## 안전 경계

- HTTP(S) endpoint만 허용
- redirect 자동 추적 안 함
- introspection/execution response 크기 제한
- recursive type traversal depth 제한
- list field는 다른 adapter와 같은 record-preserving item contract 사용
- GraphQL execution error는 invocation 실패 처리
- transport 실행 후에도 일반 SchemaRouter input/output validation 적용

GraphQL service가 introspection을 비활성화했다면 임의 response에서 schema를 추론하지 말고 신뢰된 local adapter/plugin 또는 declarative contract를 사용하세요.

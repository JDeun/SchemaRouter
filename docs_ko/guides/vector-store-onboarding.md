# Vector store 등록

SchemaRouter는 vendor client, credential, raw vector, embedding model을 model-visible contract에
넣지 않고 vector collection/index를 typed bounded search capability로 노출할 수 있습니다.

## Provider-neutral contract

Trusted backend가 collection discovery와 search를 구현하고, host가 query embedder를 제공합니다.

```python
keys = router.add_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

Async SDK라면 다음을 사용합니다.

```python
keys = await router.aadd_vector_store(
    backend,
    embed_query,
    database_name="knowledge",
)
```

Collection discovery가 선언하는 항목은 다음과 같습니다.

- collection/index 이름
- vector dimension
- distance/similarity metric
- model-visible metadata field
- 명시적으로 공개할 collection metadata

SchemaRouter는 이를 collection별 typed `search` capability로 컴파일합니다.

## 보안 경계

모델은 자연어 `query`와 bounded `top_k`만 전달합니다. 실제 vector는 trusted host embedder가
실행 시점에 만듭니다. Vector-store client와 embedding model은 ToolSpec 밖에 남습니다.

Adapter는 backend 호출 전에 embedding dimension이 introspect한 collection contract와 맞는지
검증합니다.

모델이 임의의 vendor query object나 raw backend command를 실행할 수 있는 API는 없습니다.

## 권한관리

각 collection이 별도 capability가 되므로 principal-aware authorization을 그대로 적용할 수
있습니다.

```python
AuthorizationRule(
    effect="allow",
    operation="vectors.public_docs.*",
    roles_any=("employee", "manager", "executive"),
)

AuthorizationRule(
    effect="allow",
    operation="vectors.executive_memos.*",
    roles_any=("executive",),
)
```

권한이 없는 collection은 model selection 이전에 숨기고 실행 직전에 다시 검증합니다.

Metadata/tenant filter 강제는 #770의 cross-family data-scope 단계에서 추가합니다. Vendor
adapter는 모델 argument가 trusted tenant/department filter를 덮어쓰게 해서는 안 됩니다.

## Vendor adapter

Core contract는 Pinecone, Milvus, Qdrant, Weaviate, Chroma, Redis vector/search, pgvector가
SchemaRouter의 execution-authority model을 바꾸지 않고 thin adapter로 붙을 수 있도록
vendor-neutral하게 설계했습니다.

다만 provider-neutral contract 구현만으로 위 모든 vendor SDK의 native/live acceptance가
끝났다는 뜻은 아닙니다. Vendor별 adapter acceptance는 #767에서 계속 추적합니다.

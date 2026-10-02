# 검색 가능성과 포지셔닝

SchemaRouter는 general agent framework, MCP server, model router인 것처럼 보이지 않으면서 쉽게 발견될 수 있어야 합니다.

## Canonical positioning

> **SchemaRouter는 MCP, OpenAPI, Python, framework tool을 사용하는 LLM/RAG agent를 위한 typed capability retrieval 및 schema-aware execution layer입니다.**

짧은 표현은 “LLM/RAG agent를 위한 typed capability retrieval과 schema-aware tool execution”입니다.

SchemaRouter는 typed tool/capability registry, capability retrieval layer, schema-aware planning/execution boundary, protocol/framework integration layer, validation/projection/policy/health/schema-lifecycle boundary입니다.

반면 general agent framework, LLM provider gateway, model router, MCP server catalog, document retriever/final-answer generator는 아닙니다.

## 검색 vocabulary와 surface 정렬

agent tool routing, typed tool registry, capability retrieval, schema-aware execution, MCP/OpenAPI tools, JSON Schema validation, LangChain/LangGraph/LlamaIndex, RAG tool execution, provider/access fallback, field projection 같은 실제 capability 용어를 자연스럽게 사용합니다. 검색 순위만을 위해 반복하지 않습니다.

stable release마다 GitHub description/homepage/topics, README first screen, PyPI summary/keywords, docs home, release notes가 같은 product boundary/version을 가리키도록 맞춥니다.

외부 listing은 해당 directory의 현재 규칙과 SchemaRouter의 실제 근거를 다시 확인한 뒤 제출합니다. model-routing list나 MCP server-only catalog처럼 category가 맞지 않는 곳에는 제출하지 않습니다. backlink만을 위한 제출도 하지 않습니다.

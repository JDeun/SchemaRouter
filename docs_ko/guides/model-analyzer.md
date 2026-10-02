# 모델 보조 분석

기본 planner는 `KeywordAnalyzer`로 offline 동작합니다. 자연어에서 tool/endpoint/argument/field/evidence requirement를 더 풍부하게 추출해야 할 때 `ModelQueryAnalyzer`를 사용합니다.

## Provider-neutral callable

SchemaRouter는 특정 LLM SDK를 요구하지 않습니다. 애플리케이션이 이미 사용하는 GPT, Gemini, Claude 등 structured-output client를 연결할 수 있습니다.

`ModelQueryAnalyzer`는 query + schema catalog + response contract를 보고 tool/endpoint preference, 선언 argument/field, concept, evidence request를 제안합니다. SchemaRouter는 이를 현재 registry에 맞춰 sanitize한 뒤 deterministic planning을 수행합니다.

반면 `CallableDecisionBackend`는 이미 허가된 finite option ID만 보고 제한된 selection만 반환할 수 있습니다. 어느 방식도 cloud model을 agent runtime으로 만들지 않으며 tool execution/policy/schema fingerprint/authority는 로컬에 남습니다.

## Model output은 실행 권한이 아님

model output은 strict shape validation → known tool/endpoint/argument/field 검사 → deterministic planner 순으로 처리됩니다. 알 수 없거나 만들어낸 schema element는 executable call이 될 수 없습니다. 애플리케이션이 명시한 argument가 model-produced argument보다 우선합니다.

## Remote description은 untrusted

OpenAPI description, MCP annotation, documentation text에는 prompt injection이나 오도하는 instruction이 있을 수 있습니다. analyzer prompt는 catalog description을 untrusted data로 취급합니다. credential을 description/model-visible argument에 넣지 마세요.

## Sync/async

`ModelQueryAnalyzer`는 async를 지원합니다. async analyzer를 붙였다면 `aplan()`, `ainvoke()` 등 async surface를 사용해야 하며 sync planning surface에서 호출하면 명시적으로 실패합니다.

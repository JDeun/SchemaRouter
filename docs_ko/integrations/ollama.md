# Ollama

SchemaRouter는 로컬 Ollama model을 **bounded decision backend**로 사용할 수 있습니다. Ollama가 agent loop나 arbitrary execution plan/tool execution을 소유하는 것은 아니며 SchemaRouter가 이미 허가한 finite option ID 중에서만 선택합니다.

Python SDK 없이 Ollama structured-output `format`과 기존 `httpx` dependency를 사용합니다.

## 준비와 설정

Ollama와 model은 별도로 실행/설치해야 하며 SchemaRouter가 model을 자동 pull하지 않습니다.

```python
from schemarouter.integrations import OllamaDecisionBackend
backend = OllamaDecisionBackend("your-installed-model")
```

기본 API URL은 `http://127.0.0.1:11434`이며 trusted application code가 다른 absolute HTTP(S) URL을 명시할 수 있습니다.

## Bounded structured output

각 request에서 `option_id`를 finite authorized ID enum으로 제한한 JSON Schema를 보냅니다. query, `max_selections`, option ID/label/description, optional bounded context만 전달하며 `DecisionOption.metadata`는 제외합니다.

server response 뒤에도 local validation을 다시 수행해 unknown/duplicate ID, selection overflow, invalid score, malformed JSON, inconsistent abstention을 fail-closed합니다. structured generation은 reliability aid이며 authority boundary는 local validation입니다.

sync/async mode를 지원하고 둘 다 non-streaming `/api/chat`을 사용합니다. context가 불필요하거나 민감하면 `include_context=False`를 사용합니다.

local model benchmark는 shared decision-routing corpus로 실행할 수 있으며 model-reported score는 self-assessment일 뿐 calibrated probability로 취급하지 않습니다.

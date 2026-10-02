# Typed capability retrieval ablation

compact retrieval의 이득이 단순 Top-K 축소 때문인지 typed schema/field/evidence representation 때문인지 분리하기 위한 ablation입니다. route count, schema bytes/tokens, required-route recall, task completion, unsupported behavior를 함께 비교합니다.

representation을 바꿀 때 execution policy나 tool availability까지 동시에 바꾸지 않습니다. 동일 workload/agent/runtime에서 lexical/typed/field-aware representation 차이를 통제하고 결과를 본 뒤 condition을 추가해 같은 holdout을 재사용하지 않습니다.

# 대규모 독립 held-out agent utility

#432는 corrective research와 분리된 **780개의 independent task**로 compact typed retrieval의 일반화를 확인합니다. #431에서 선택된 방법이 있다면 이 held-out에서 동일한 frozen configuration으로 평가해야 합니다.

metric은 downstream task success, required-route recall, unsupported handling, context/schema cost, execution-authority violation을 포함합니다. held-out 결과를 본 뒤 method/threshold를 조정하면 해당 split은 더 이상 fresh evidence가 아니므로 재사용하지 않습니다.

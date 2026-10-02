# Successor runtime qualification

#510은 field-projection/final-answer 계열 실험을 수행할 수 있는 tool-using runtime을 먼저 검증하는 36-episode qualification입니다.

frozen roster는 SmolLM3-3B, Qwen3-4B, Qwen3-8B 순이며 exact pinned revision을 사용합니다. eligibility는 envelope ≥0.80, tool-call ≥0.90, grounded-fact ≥0.70입니다. 첫 qualifying candidate가 successor가 되고 앞 candidate의 **scientific failure**가 완결된 뒤에만 다음 candidate로 진행합니다. infrastructure failure는 roster advance 근거가 아닙니다.

이 screen은 어떤 model이 일반적으로 더 좋다는 순위를 만드는 것이 아니라 downstream experiment가 실제 tool-use/projection 조건을 측정할 수 있는지 확인하는 instrument qualification입니다.

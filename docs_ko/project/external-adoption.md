# 외부 도입과 검증

외부 도입은 maintainer가 만든 예제와 구분해 증거 수준으로 관리합니다.

- **E0**: maintainer-owned integration/example만 존재
- **E1**: 외부 project의 공개 평가
- **E2**: downstream reproducible branch/PR/test에 포함
- **E3**: downstream released/default path에서 사용
- **E4**: 독립 benchmark/reliability reproduction

star, mention, 친근한 답변은 adoption level이 아닙니다. 현재 maintainer-side validation은 PydanticAI ToolSearch, OpenAI Agents SDK dynamic MCP filtering, mcp-agent large-tool-catalog composition에 대해 준비되어 있으며 실제 E1+는 third-party public activity가 있어야 합니다.

outreach는 3–5개의 구체적 fit이 있는 project를 선택해 contribution rule과 architecture를 먼저 확인하고 작은 reproducible example/benchmark/integration을 제안합니다. unsolicited speculative PR, star 요청, testimonial 요청은 하지 않습니다.

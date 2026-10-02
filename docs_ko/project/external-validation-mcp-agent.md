# mcp-agent 외부 검증 경로

large MCP tool catalog에서 mcp-agent가 MCP lifecycle/orchestration을 소유하고 SchemaRouter가 catalog를 typed retrieval로 좁히는 composition을 검증합니다.

SchemaRouter는 server lifecycle, agent loop, approval을 빼앗지 않으며 반환 candidate는 실행 권한이 아닙니다. 현재는 maintainer-side **E0** validation으로, mcp-agent의 실제 채택을 의미하지 않습니다. third-party public engagement와 reproducible downstream evidence가 생길 때만 E1+로 승격합니다.

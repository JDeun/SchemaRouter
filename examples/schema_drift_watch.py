"""Offline example: detect breaking OpenAPI drift and keep the accepted contract."""

from __future__ import annotations

import asyncio

import httpx

from schemarouter import SchemaRouter


def _document(*, required_query: bool = False) -> dict[str, object]:
    parameters: list[dict[str, object]] = []
    if required_query:
        parameters.append(
            {
                "name": "q",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }
        )

    return {
        "openapi": "3.1.0",
        "info": {"title": "Example Watch API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/records": {
                "get": {
                    "operationId": "records_search",
                    "parameters": parameters,
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


async def main() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="records",
        )
        accepted_fingerprint = tool.fingerprint

        router.register_schema_watch(tool.key, interval_seconds=60)

        # The provider now requires a new query argument: this is breaking drift.
        state["document"] = _document(required_query=True)
        snapshots = await router.check_schema_watches_once()
        snapshot = snapshots[0]
        pending = router.schema_watch_pending_review(tool.key)

        assert snapshot.status == "pending_review"
        assert snapshot.last_compatibility == "breaking"
        assert pending is not None
        assert router.registry.get(tool.key).fingerprint == accepted_fingerprint

        print(f"watch status: {snapshot.status}")
        print(f"compatibility: {snapshot.last_compatibility}")
        print(f"pending changes: {snapshot.pending_change_count}")
        print("accepted contract unchanged: yes")


if __name__ == "__main__":
    asyncio.run(main())

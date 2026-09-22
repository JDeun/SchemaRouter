from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..models import PlanRequest, ToolResult
from ..runs import RunConfig
from ..runtime import SchemaRouter

LangGraphState = Mapping[str, Any]
LangGraphRequestFactory = Callable[[LangGraphState], PlanRequest | str | Mapping[str, Any]]


def _coerce_request(value: Any) -> PlanRequest | str:
    if isinstance(value, PlanRequest | str):
        return value
    if isinstance(value, Mapping):
        return PlanRequest.model_validate(dict(value))
    raise TypeError(
        "LangGraph request must be a string, PlanRequest, or mapping compatible with PlanRequest"
    )


def _request_from_state(
    state: LangGraphState,
    *,
    request_key: str | None,
    query_key: str,
    arguments_key: str,
    request_factory: LangGraphRequestFactory | None,
) -> PlanRequest | str:
    if request_factory is not None:
        return _coerce_request(request_factory(state))

    if request_key is not None and request_key in state:
        return _coerce_request(state[request_key])

    query = state.get(query_key)
    if not isinstance(query, str) or not query.strip():
        request_hint = (
            f"state[{request_key!r}] or " if request_key is not None else ""
        )
        raise TypeError(
            "LangGraph state must provide "
            f"{request_hint}a non-empty string at state[{query_key!r}]"
        )

    raw_arguments = state.get(arguments_key, {})
    if raw_arguments is None:
        raw_arguments = {}
    if not isinstance(raw_arguments, Mapping):
        raise TypeError(f"state[{arguments_key!r}] must be a mapping when provided")

    return PlanRequest(query=query, arguments=dict(raw_arguments))


def _node_update(
    results: list[ToolResult],
    *,
    result_key: str,
    serialize_results: bool,
) -> dict[str, Any]:
    value: Any
    if serialize_results:
        value = [result.model_dump(mode="json") for result in results]
    else:
        value = results
    return {result_key: value}


def to_langgraph_node(
    router: SchemaRouter,
    *,
    request_key: str | None = "schemarouter_request",
    query_key: str = "query",
    arguments_key: str = "arguments",
    result_key: str = "schemarouter_results",
    request_factory: LangGraphRequestFactory | None = None,
    run_config: RunConfig | dict[str, Any] | None = None,
    serialize_results: bool = True,
    name: str = "schemarouter",
) -> Any:
    """Return a sync/async Runnable node for direct use in a LangGraph StateGraph.

    The default state contract accepts either a complete request at request_key or a query plus
    optional arguments mapping. The node returns a partial state update under result_key. Results
    are serialized to JSON-compatible dictionaries by default for checkpoint-friendly state.

    request_factory can adapt arbitrary application state into a PlanRequest or string without
    giving LangGraph direct access to SchemaRouter execution authority.
    """
    if not result_key:
        raise ValueError("result_key must be non-empty")
    if not query_key:
        raise ValueError("query_key must be non-empty")
    if not arguments_key:
        raise ValueError("arguments_key must be non-empty")
    if request_key == "":
        raise ValueError("request_key must be non-empty or None")
    if not name:
        raise ValueError("name must be non-empty")

    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError as exc:
        raise ImportError(
            'LangGraph integration requires: pip install "schemarouter[langgraph]"'
        ) from exc

    def invoke_node(state: LangGraphState) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("LangGraph node input must be a mapping")
        request = _request_from_state(
            state,
            request_key=request_key,
            query_key=query_key,
            arguments_key=arguments_key,
            request_factory=request_factory,
        )
        results = router.invoke(request, config=run_config)
        return _node_update(
            results,
            result_key=result_key,
            serialize_results=serialize_results,
        )

    async def ainvoke_node(state: LangGraphState) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("LangGraph node input must be a mapping")
        request = _request_from_state(
            state,
            request_key=request_key,
            query_key=query_key,
            arguments_key=arguments_key,
            request_factory=request_factory,
        )
        results = await router.ainvoke(request, config=run_config)
        return _node_update(
            results,
            result_key=result_key,
            serialize_results=serialize_results,
        )

    return RunnableLambda(invoke_node, afunc=ainvoke_node, name=name)

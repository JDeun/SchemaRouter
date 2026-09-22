from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from .models import EndpointSpec, ToolCall, ToolResult, ToolSpec

BeforeExecutionHook = Callable[
    [ToolSpec, EndpointSpec, ToolCall],
    None | Awaitable[None],
]
AfterExecutionHook = Callable[
    [ToolSpec, EndpointSpec, ToolCall, ToolResult],
    None | Awaitable[None],
]


@dataclass(frozen=True)
class ExecutionHooks:
    """Ordered trusted local hooks around one validated tool-call execution.

    Hooks receive detached model snapshots. They cannot transform the executable ToolCall or the
    ToolResult returned to the caller. Returning any non-None value is rejected by the executor.
    """

    before_call: tuple[BeforeExecutionHook, ...] = ()
    after_call: tuple[AfterExecutionHook, ...] = ()

    def __init__(
        self,
        *,
        before_call: Iterable[BeforeExecutionHook] = (),
        after_call: Iterable[AfterExecutionHook] = (),
    ) -> None:
        before = tuple(before_call)
        after = tuple(after_call)
        if any(not callable(hook) for hook in before):
            raise TypeError("before_call hooks must be callable")
        if any(not callable(hook) for hook in after):
            raise TypeError("after_call hooks must be callable")
        object.__setattr__(self, "before_call", before)
        object.__setattr__(self, "after_call", after)

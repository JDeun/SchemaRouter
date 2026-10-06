from __future__ import annotations

import asyncio
import warnings
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from concurrent.futures import Future
from threading import Event, Lock, Thread
from typing import TypeVar, cast

_T = TypeVar("_T")


class LoopAffinityGuard:
    """Bind loop-affine lifecycle state to one event loop with a clear contract."""

    def __init__(self, component: str) -> None:
        self._component = component
        self._lock = Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def claim(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        with self._lock:
            bound = self._loop
            if bound is None:
                self._loop = loop
                return loop
            if bound is not loop:
                raise RuntimeError(
                    f"{self._component} is already bound to a different event loop; "
                    "do not mix synchronous and asynchronous lifecycle APIs on the "
                    "same SchemaRouter instance"
                )
        return loop

    def notify(self, callback: Callable[[], None]) -> None:
        """Run a loop-owned wake callback safely from synchronous caller threads."""

        with self._lock:
            loop = self._loop
        if loop is None:
            callback()
            return
        if loop.is_closed():
            raise RuntimeError(
                f"{self._component} is bound to a closed event loop; "
                "create a new SchemaRouter instance instead of reusing it across "
                "incompatible lifecycle loops"
            )
        if loop.is_running():
            loop.call_soon_threadsafe(callback)
            return
        callback()


class SyncLoopRunner:
    """Execute synchronous API bridges on one long-lived daemon event loop."""

    def __init__(self) -> None:
        self._state_lock = Lock()
        self._ready = Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None

    @staticmethod
    def _reject_active_caller_loop(kind: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise RuntimeError(
            f"synchronous SchemaRouter {kind} cannot run inside an active event loop; "
            "use the async API instead"
        )

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._state_lock:
            self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                # This runner owns the loop. Even if async-generator cleanup
                # itself fails, never leave the owned loop unclosed.
                loop.close()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._state_lock:
            thread = self._thread
            if thread is None or not thread.is_alive():
                self._ready.clear()
                thread = Thread(
                    target=self._thread_main,
                    name="schemarouter-sync-loop",
                    daemon=True,
                )
                self._thread = thread
                thread.start()
        self._ready.wait()
        with self._state_lock:
            loop = self._loop
        if loop is None or loop.is_closed():
            raise RuntimeError("SchemaRouter synchronous event loop is unavailable")
        return loop

    @staticmethod
    async def _await_factory(factory: Callable[[], Awaitable[_T]]) -> _T:
        return await factory()

    def run(self, factory: Callable[[], Awaitable[_T]]) -> _T:
        self._reject_active_caller_loop("API")
        loop = self._ensure_loop()
        future: Future[_T] = asyncio.run_coroutine_threadsafe(
            self._await_factory(factory),
            loop,
        )
        return future.result()

    def stream(self, factory: Callable[[], AsyncIterator[_T]]) -> Iterator[_T]:
        self._reject_active_caller_loop("streaming")
        loop = self._ensure_loop()
        iterator = factory()
        primary_error: BaseException | None = None
        try:
            while True:
                future = asyncio.run_coroutine_threadsafe(
                    self._await_factory(iterator.__anext__),
                    loop,
                )
                try:
                    yield future.result()
                except StopAsyncIteration:
                    break
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            aclose = getattr(iterator, "aclose", None)
            if callable(aclose):
                close_iterator = cast(Callable[[], Awaitable[None]], aclose)
                try:
                    close_future = asyncio.run_coroutine_threadsafe(
                        self._await_factory(close_iterator),
                        loop,
                    )
                    close_future.result()
                except BaseException as cleanup_error:
                    # An iterator failure is the primary execution signal. Do
                    # not replace it with a secondary aclose() failure. Explicit
                    # generator close (GeneratorExit) has no execution failure
                    # to preserve, so callers still receive the cleanup error.
                    if primary_error is None or isinstance(primary_error, GeneratorExit):
                        raise
                    warnings.warn(
                        "synchronous stream cleanup failed after a primary stream "
                        "error; preserving "
                        f"{type(primary_error).__name__} over "
                        f"{type(cleanup_error).__name__}",
                        RuntimeWarning,
                        stacklevel=2,
                    )

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


class SyncOffloadCapacityError(RuntimeError):
    """Raised when all bounded synchronous worker slots are still occupied."""


class SyncOffloadClosedError(RuntimeError):
    """Raised when work is submitted after the router-owned worker pool closed."""


class BoundedSyncOffloadPool:
    """Bound synchronous offload without pretending Python threads are cancellable."""

    def __init__(
        self,
        *,
        max_workers: int = 8,
        thread_name_prefix: str = "schemarouter-sync",
    ) -> None:
        if not isinstance(max_workers, int) or isinstance(max_workers, bool):
            raise TypeError("max_workers must be an int")
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")

        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._slots = threading.BoundedSemaphore(max_workers)
        self._lock = threading.RLock()
        self._closed = False
        self._inflight: set[Future[Any]] = set()

    @property
    def in_flight(self) -> int:
        with self._lock:
            return len(self._inflight)

    def submit(
        self,
        callback: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Future[Any]:
        if not self._slots.acquire(blocking=False):
            raise SyncOffloadCapacityError(
                "offloaded synchronous worker capacity is exhausted"
            )

        context = contextvars.copy_context()
        future: Future[Any] | None = None
        try:
            with self._lock:
                if self._closed:
                    raise SyncOffloadClosedError(
                        "offloaded synchronous worker pool is closed"
                    )
                future = self._executor.submit(
                    context.run,
                    callback,
                    *args,
                    **kwargs,
                )
                self._inflight.add(future)
        except BaseException:
            self._slots.release()
            raise

        def cleanup(done: Future[Any]) -> None:
            with self._lock:
                self._inflight.discard(done)
            self._slots.release()

        future.add_done_callback(cleanup)
        return asyncio.wrap_future(future)

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            executor = self._executor

        # Running Python threads cannot be stopped safely. Prevent new submissions and cancel
        # anything that has not started; already-running calls are allowed to finish naturally.
        executor.shutdown(wait=False, cancel_futures=True)

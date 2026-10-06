from __future__ import annotations

import pytest

from schemarouter.runtime import _stream_sync


class _FailingSyncBridgeIterator:
    def __init__(
        self,
        *,
        iteration_error: BaseException | None = None,
        cleanup_error: BaseException | None = None,
        yield_once: bool = False,
    ) -> None:
        self.iteration_error = iteration_error
        self.cleanup_error = cleanup_error
        self.yield_once = yield_once
        self._yielded = False
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.yield_once and not self._yielded:
            self._yielded = True
            return "value"
        if self.iteration_error is not None:
            raise self.iteration_error
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True
        if self.cleanup_error is not None:
            raise self.cleanup_error


def test_sync_stream_preserves_primary_error_when_aclose_also_fails() -> None:
    iterator = _FailingSyncBridgeIterator(
        iteration_error=RuntimeError("iteration failed"),
        cleanup_error=ValueError("cleanup failed"),
    )

    with pytest.warns(
        RuntimeWarning,
        match="preserving RuntimeError over ValueError",
    ):
        with pytest.raises(RuntimeError, match="iteration failed"):
            list(_stream_sync(lambda: iterator))

    assert iterator.closed is True


def test_sync_stream_propagates_cleanup_error_after_normal_exhaustion() -> None:
    iterator = _FailingSyncBridgeIterator(
        cleanup_error=ValueError("cleanup failed"),
    )

    with pytest.raises(ValueError, match="cleanup failed"):
        list(_stream_sync(lambda: iterator))

    assert iterator.closed is True


def test_sync_stream_explicit_close_surfaces_cleanup_error() -> None:
    iterator = _FailingSyncBridgeIterator(
        cleanup_error=ValueError("cleanup failed"),
        yield_once=True,
    )
    stream = _stream_sync(lambda: iterator)

    assert next(stream) == "value"
    with pytest.raises(ValueError, match="cleanup failed"):
        stream.close()

    assert iterator.closed is True

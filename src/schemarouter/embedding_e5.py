"""Opt-in, dependency-free E5 retrieval embedding adapter.

This adapter receives the request/query first and *already authorized* catalog
option texts after it. Actual model loading is always host-owned; the core
SchemaRouter package does not download model weights or execute a tool.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable
from hashlib import sha256
from threading import RLock

from .decisions import EmbeddingDecisionBackend
from .errors import PlanningError

E5Encoder = Callable[[list[str]], Iterable[Iterable[float]]]


class E5CachedEmbedder:
    """Add asymmetric E5 prefixes and a bounded in-memory passage-vector cache.

    The caller supplies the encoder, e.g. a locally loaded sentence-transformers
    model. Only candidate texts are cached, keyed by a digest; the query is
    encoded anew on every call. This does not perform authorization, no-fit
    calibration, or semantic translation, and it does not change default routing.
    """

    def __init__(
        self,
        encoder: E5Encoder,
        *,
        max_cached_passages: int = 2048,
    ) -> None:
        if not callable(encoder):
            raise TypeError("E5 encoder must be callable")
        if type(max_cached_passages) is not int or not 0 <= max_cached_passages <= 50_000:
            raise ValueError("max_cached_passages must be an integer between 0 and 50000")
        self._encoder = encoder
        self._limit = max_cached_passages
        self._passages: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._lock = RLock()

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(type(item) is not str or not item.strip() for item in texts):
            raise PlanningError("E5 embeddings require non-empty query and option text")

        # One lock serializes a host-supplied encoder and makes LRU updates
        # consistent when multiple requests share the same local model.
        with self._lock:
            hashes: list[str] = []
            missing: dict[str, str] = {}
            for option_text in texts[1:]:
                passage = "passage: " + option_text
                digest = sha256(passage.encode("utf-8")).hexdigest()
                hashes.append(digest)
                if digest in self._passages:
                    self._passages.move_to_end(digest)
                elif digest not in missing:
                    missing[digest] = passage

            batch = ["query: " + texts[0], *missing.values()]
            vectors = EmbeddingDecisionBackend._coerce_vectors(
                self._encoder(batch), expected_count=len(batch),
            )
            query_vector, *new_vectors = vectors
            resolved = dict(zip(missing, new_vectors, strict=True))
            # Cached entries are not mutated or exposed as writable references.
            result = [query_vector]
            for digest in hashes:
                vector = resolved.get(digest)
                if vector is None:
                    vector = list(self._passages[digest])
                if len(vector) != len(query_vector):
                    raise PlanningError("E5 embeddings have inconsistent cached dimensions")
                result.append(list(vector))

            # Do not populate a cache with invalid or inconsistent outputs.
            for digest, vector in resolved.items():
                if self._limit == 0:
                    break
                self._passages[digest] = tuple(vector)
                self._passages.move_to_end(digest)
                if len(self._passages) > self._limit:
                    self._passages.popitem(last=False)
            return result

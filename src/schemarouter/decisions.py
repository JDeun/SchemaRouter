from __future__ import annotations

import inspect
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PlanningError


class _DecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DecisionOption(_DecisionModel):
    """One locally authorized choice exposed to a decision backend."""

    id: str = Field(min_length=1)
    label: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(_DecisionModel):
    """A bounded choice request.

    Option IDs are the only authoritative values. Descriptions and metadata are
    untrusted context and cannot grant execution authority.
    """

    query: str
    options: list[DecisionOption] = Field(min_length=1)
    max_selections: int = Field(default=1, ge=1)
    context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_bounds(self) -> DecisionRequest:
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("decision option IDs must be unique")
        if self.max_selections > len(self.options):
            raise ValueError("max_selections cannot exceed the option count")
        return self


class DecisionSelection(_DecisionModel):
    option_id: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_finite_score(self) -> DecisionSelection:
        if self.score is not None and not math.isfinite(self.score):
            raise ValueError("decision scores must be finite")
        return self


class DecisionResult(_DecisionModel):
    selections: list[DecisionSelection] = Field(default_factory=list)
    abstained: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_abstention(self) -> DecisionResult:
        if self.abstained and self.selections:
            raise ValueError("an abstaining decision cannot contain selections")
        return self


class DecisionBackend(Protocol):
    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]: ...


DecisionCallable = Callable[
    [DecisionRequest],
    DecisionResult | dict[str, Any] | Awaitable[DecisionResult | dict[str, Any]],
]
EmbeddingCallable = Callable[
    [list[str]],
    Iterable[Iterable[float]] | Awaitable[Iterable[Iterable[float]]],
]
DecisionOptionTextCallable = Callable[[DecisionOption], str]


def validate_decision(request: DecisionRequest, result: DecisionResult) -> DecisionResult:
    """Fail closed if a backend returns anything outside the offered choice set."""

    allowed = {option.id for option in request.options}
    selected = [selection.option_id for selection in result.selections]

    if len(selected) != len(set(selected)):
        raise PlanningError("decision backend returned duplicate option IDs")
    unknown = sorted(set(selected) - allowed)
    if unknown:
        raise PlanningError(
            "decision backend returned unknown option IDs: " + ", ".join(unknown)
        )
    if len(selected) > request.max_selections:
        raise PlanningError("decision backend exceeded max_selections")
    return result


class _ValidatedAwaitable:
    """Awaitable wrapper that can explicitly release an unconsumed coroutine."""

    def __init__(
        self,
        raw: Awaitable[DecisionResult | dict[str, Any]],
        request: DecisionRequest,
    ) -> None:
        self._raw = raw
        self._request = request

    def __await__(self):  # type: ignore[no-untyped-def]
        async def resolve() -> DecisionResult:
            value = await self._raw
            result = (
                value
                if isinstance(value, DecisionResult)
                else DecisionResult.model_validate(value)
            )
            return validate_decision(self._request, result)

        return resolve().__await__()

    def close(self) -> None:
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()


class CallableDecisionBackend:
    """Provider-neutral adapter for hosted or local bounded-decision models."""

    def __init__(self, model: DecisionCallable) -> None:
        self.model = model

    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]:
        raw = self.model(request)
        if inspect.isawaitable(raw):
            return _ValidatedAwaitable(raw, request)

        result = raw if isinstance(raw, DecisionResult) else DecisionResult.model_validate(raw)
        return validate_decision(request, result)


class _EmbeddingAwaitable:
    """Awaitable embedding result that can release an unconsumed provider coroutine."""

    def __init__(
        self,
        backend: EmbeddingDecisionBackend,
        request: DecisionRequest,
        raw: Awaitable[Iterable[Iterable[float]]],
    ) -> None:
        self._backend = backend
        self._request = request
        self._raw = raw

    def __await__(self):  # type: ignore[no-untyped-def]
        async def resolve() -> DecisionResult:
            return self._backend._result(self._request, await self._raw)

        return resolve().__await__()

    def close(self) -> None:
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()


class EmbeddingDecisionBackend:
    """Bounded local/provider-neutral decision backend based on embedding similarity.

    The embedder receives the query followed by one text representation for every locally
    authorized option. SchemaRouter performs cosine ranking itself and maps ranked vector positions
    back to the original opaque option IDs. The default option text omits DecisionOption.metadata;
    a custom option_text callback is trusted application code and controls its own disclosure.
    Execution authority is never forwarded to the embedder.
    """

    def __init__(
        self,
        embedder: EmbeddingCallable,
        *,
        min_similarity: float = -1.0,
        min_margin: float = 0.0,
        option_text: DecisionOptionTextCallable | None = None,
    ) -> None:
        if not callable(embedder):
            raise TypeError("embedder must be callable")
        if not math.isfinite(min_similarity) or not -1.0 <= min_similarity <= 1.0:
            raise ValueError("min_similarity must be finite and between -1 and 1")
        if not math.isfinite(min_margin) or not 0.0 <= min_margin <= 2.0:
            raise ValueError("min_margin must be finite and between 0 and 2")
        self.embedder = embedder
        self.min_similarity = min_similarity
        self.min_margin = min_margin
        self.option_text = option_text or self._default_option_text

    @staticmethod
    def _default_option_text(option: DecisionOption) -> str:
        label = option.label.strip() or option.id
        description = option.description.strip()
        return f"{label}\n{description}" if description else label

    @staticmethod
    def _coerce_vectors(
        raw: Iterable[Iterable[float]],
        *,
        expected_count: int,
    ) -> list[list[float]]:
        try:
            values = list(raw)
        except TypeError as exc:
            raise PlanningError("embedding backend returned a non-iterable batch") from exc
        if len(values) != expected_count:
            raise PlanningError(
                "embedding backend returned the wrong number of vectors: "
                f"expected {expected_count}, got {len(values)}"
            )

        vectors: list[list[float]] = []
        dimensions: int | None = None
        for index, raw_vector in enumerate(values):
            if isinstance(raw_vector, (str, bytes)):
                raise PlanningError(
                    f"embedding backend returned an invalid vector at index {index}"
                )
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise PlanningError(
                    f"embedding backend returned an invalid vector at index {index}"
                ) from exc
            if not vector:
                raise PlanningError(
                    f"embedding backend returned an empty vector at index {index}"
                )
            if any(not math.isfinite(value) for value in vector):
                raise PlanningError("embedding backend returned a non-finite vector value")
            if dimensions is None:
                dimensions = len(vector)
            elif len(vector) != dimensions:
                raise PlanningError("embedding backend returned inconsistent vector dimensions")
            vectors.append(vector)
        return vectors

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            raise PlanningError("embedding backend returned a zero-norm vector")
        value = sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
        return max(-1.0, min(1.0, value))

    def _result(
        self,
        request: DecisionRequest,
        raw: Iterable[Iterable[float]],
    ) -> DecisionResult:
        vectors = self._coerce_vectors(raw, expected_count=len(request.options) + 1)
        query_vector, *option_vectors = vectors
        ranked = sorted(
            (
                (index, self._cosine(query_vector, vector))
                for index, vector in enumerate(option_vectors)
            ),
            key=lambda item: (-item[1], item[0]),
        )
        eligible = [item for item in ranked if item[1] >= self.min_similarity]

        metadata: dict[str, Any] = {
            "provider": "embedding-similarity",
            "dimensions": len(query_vector),
            "option_count": len(request.options),
            "min_similarity": self.min_similarity,
            "min_margin": self.min_margin,
            "top_similarity": ranked[0][1],
        }
        if not eligible:
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    metadata={**metadata, "reason": "below_min_similarity"},
                ),
            )

        limit = min(request.max_selections, len(eligible))
        selected = eligible[:limit]
        if self.min_margin > 0.0 and len(eligible) > limit:
            boundary_margin = selected[-1][1] - eligible[limit][1]
            metadata["boundary_margin"] = boundary_margin
            if boundary_margin < self.min_margin:
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        metadata={**metadata, "reason": "ambiguous_selection_boundary"},
                    ),
                )

        return validate_decision(
            request,
            DecisionResult(
                selections=[
                    DecisionSelection(
                        option_id=request.options[index].id,
                        score=(similarity + 1.0) / 2.0,
                    )
                    for index, similarity in selected
                ],
                metadata=metadata,
            ),
        )

    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]:
        texts = [request.query, *(self.option_text(option) for option in request.options)]
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise PlanningError("embedding decision text must be a non-empty string")

        raw = self.embedder(texts)
        if inspect.isawaitable(raw):
            return _EmbeddingAwaitable(self, request, raw)
        return self._result(request, raw)


class _CachedEmbeddingAwaitable:
    """Awaitable wrapper for cached embedding decisions."""

    def __init__(
        self,
        backend: CachedEmbeddingDecisionBackend,
        request: DecisionRequest,
        raw: Awaitable[Iterable[Iterable[float]]],
        option_keys: list[tuple[str, str]],
        missing_keys: list[tuple[str, str]],
    ) -> None:
        self._backend = backend
        self._request = request
        self._raw = raw
        self._option_keys = option_keys
        self._missing_keys = missing_keys

    def __await__(self):  # type: ignore[no-untyped-def]
        async def resolve() -> DecisionResult:
            return self._backend._cached_result(
                self._request,
                await self._raw,
                option_keys=self._option_keys,
                missing_keys=self._missing_keys,
            )

        return resolve().__await__()

    def close(self) -> None:
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()


class CachedEmbeddingDecisionBackend(EmbeddingDecisionBackend):
    """Embedding decision backend that caches static option vectors by ID and text.

    This is useful when the authorized option catalog is stable across many queries,
    such as schema-graph operation nodes. Only option embeddings are cached; every
    request still embeds the current query. A changed option text uses a new cache key,
    so schema-description drift cannot silently reuse the previous vector.
    """

    def __init__(
        self,
        embedder: EmbeddingCallable,
        *,
        min_similarity: float = -1.0,
        min_margin: float = 0.0,
        option_text: DecisionOptionTextCallable | None = None,
    ) -> None:
        super().__init__(
            embedder,
            min_similarity=min_similarity,
            min_margin=min_margin,
            option_text=option_text,
        )
        self._option_vector_cache: dict[tuple[str, str], list[float]] = {}

    def clear_cache(self) -> None:
        self._option_vector_cache.clear()

    def _cached_result(
        self,
        request: DecisionRequest,
        raw: Iterable[Iterable[float]],
        *,
        option_keys: list[tuple[str, str]],
        missing_keys: list[tuple[str, str]],
    ) -> DecisionResult:
        vectors = self._coerce_vectors(
            raw,
            expected_count=1 + len(missing_keys),
        )
        query_vector, *missing_vectors = vectors
        for key, vector in zip(missing_keys, missing_vectors, strict=True):
            self._option_vector_cache[key] = vector

        option_vectors = [
            self._option_vector_cache[key]
            for key in option_keys
        ]
        dimensions = len(query_vector)
        if any(len(vector) != dimensions for vector in option_vectors):
            raise PlanningError(
                "cached embedding option dimensions do not match the query vector"
            )

        ranked = sorted(
            (
                (index, self._cosine(query_vector, vector))
                for index, vector in enumerate(option_vectors)
            ),
            key=lambda item: (-item[1], item[0]),
        )
        eligible = [item for item in ranked if item[1] >= self.min_similarity]
        metadata: dict[str, Any] = {
            "provider": "embedding-similarity-cached",
            "dimensions": dimensions,
            "option_count": len(request.options),
            "min_similarity": self.min_similarity,
            "min_margin": self.min_margin,
            "top_similarity": ranked[0][1],
            "cache_hits": len(option_keys) - len(missing_keys),
            "cache_misses": len(missing_keys),
        }
        if not eligible:
            return validate_decision(
                request,
                DecisionResult(
                    abstained=True,
                    metadata={**metadata, "reason": "below_min_similarity"},
                ),
            )

        limit = min(request.max_selections, len(eligible))
        selected = eligible[:limit]
        if self.min_margin > 0.0 and len(eligible) > limit:
            boundary_margin = selected[-1][1] - eligible[limit][1]
            metadata["boundary_margin"] = boundary_margin
            if boundary_margin < self.min_margin:
                return validate_decision(
                    request,
                    DecisionResult(
                        abstained=True,
                        metadata={**metadata, "reason": "ambiguous_selection_boundary"},
                    ),
                )

        return validate_decision(
            request,
            DecisionResult(
                selections=[
                    DecisionSelection(
                        option_id=request.options[index].id,
                        score=(similarity + 1.0) / 2.0,
                    )
                    for index, similarity in selected
                ],
                metadata=metadata,
            ),
        )

    def decide(
        self,
        request: DecisionRequest,
    ) -> DecisionResult | Awaitable[DecisionResult]:
        option_texts = [self.option_text(option) for option in request.options]
        texts = [request.query, *option_texts]
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise PlanningError("embedding decision text must be a non-empty string")

        option_keys = [
            (option.id, text)
            for option, text in zip(request.options, option_texts, strict=True)
        ]
        missing_keys = [
            key for key in option_keys if key not in self._option_vector_cache
        ]
        missing_texts = [text for _option_id, text in missing_keys]
        raw = self.embedder([request.query, *missing_texts])
        if inspect.isawaitable(raw):
            return _CachedEmbeddingAwaitable(
                self,
                request,
                raw,
                option_keys,
                missing_keys,
            )
        return self._cached_result(
            request,
            raw,
            option_keys=option_keys,
            missing_keys=missing_keys,
        )


class FirstOptionDecisionBackend:
    """Deterministic reference backend for tests and integration examples."""

    def decide(self, request: DecisionRequest) -> DecisionResult:
        return DecisionResult(
            selections=[DecisionSelection(option_id=request.options[0].id, score=1.0)]
        )


def choose_sync(
    backend: DecisionBackend,
    request: DecisionRequest,
) -> DecisionResult:
    result = backend.decide(request)
    if inspect.isawaitable(result):
        close = getattr(result, "close", None)
        if callable(close):
            close()
        raise PlanningError("the configured decision backend is asynchronous; use an async path")
    return validate_decision(request, result)


async def choose_async(
    backend: DecisionBackend,
    request: DecisionRequest,
) -> DecisionResult:
    result = backend.decide(request)
    if inspect.isawaitable(result):
        result = await result
    return validate_decision(request, result)

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from pydantic import Field, model_validator

from ..authorization import _current_data_scope
from ..errors import PolicyViolationError, RegistrationError, SchemaValidationError
from ..models import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    StrictModel,
    ToolCall,
    ToolSpec,
)

_SEARCH_ENDPOINT = "search"
_MAX_TOP_K = 100


class VectorMetadataField(StrictModel):
    """One model-visible metadata field exposed by a vector collection."""

    name: str
    description: str = ""
    json_schema: dict[str, Any] = Field(default_factory=dict)
    filterable: bool = False

    @model_validator(mode="after")
    def validate_name(self) -> VectorMetadataField:
        if not self.name.strip():
            raise ValueError("vector metadata field name must be non-empty")
        return self


class VectorCollectionSpec(StrictModel):
    """Provider-neutral collection/index description returned by trusted introspection."""

    name: str
    dimension: int
    metric: str = "unknown"
    description: str = ""
    metadata_fields: tuple[VectorMetadataField, ...] = ()
    public_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_collection(self) -> VectorCollectionSpec:
        if not self.name.strip():
            raise ValueError("vector collection name must be non-empty")
        if self.dimension < 1:
            raise ValueError("vector collection dimension must be >= 1")
        names = [field.name for field in self.metadata_fields]
        if len(names) != len(set(names)):
            raise ValueError("vector collection metadata field names must be unique")
        reserved = sorted({"id", "score"} & set(names))
        if reserved:
            raise ValueError(
                "vector collection metadata fields use reserved names: "
                + ", ".join(reserved)
            )
        return self


class VectorStoreBackend(Protocol):
    """Base vector backend contract.

    Backends that do not enforce trusted authorization predicates implement only
    this interface and remain usable when no trusted data-scope filters apply.
    """

    def list_collections(
        self,
    ) -> Iterable[VectorCollectionSpec] | Awaitable[Iterable[VectorCollectionSpec]]: ...

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


class ScopedVectorStoreBackend(VectorStoreBackend, Protocol):
    """Vector backend that explicitly supports trusted data-scope predicates.

    Filter values use exact-match semantics for scalars. Tuple values represent
    an any-of match for the same field. The filters are trusted host data and
    must never be exposed as model-controlled search arguments.
    """

    supports_trusted_filters: bool

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


VectorQueryEmbedder = Callable[
    [str],
    Sequence[float] | Awaitable[Sequence[float]],
]


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or "collection"


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _call_backend(
    function: Any,
    /,
    *args: Any,
    offload_sync: bool,
    **kwargs: Any,
) -> Any:
    if offload_sync and not inspect.iscoroutinefunction(function):
        value = await asyncio.to_thread(function, *args, **kwargs)
    else:
        value = function(*args, **kwargs)
    return await _await_if_needed(value)


@dataclass(frozen=True)
class VectorCollectionBinding:
    """One introspected vector collection plus its trusted search invoker."""

    tool: ToolSpec
    invoker: VectorCollectionInvoker


class VectorCollectionInvoker:
    """Call-aware bounded vector search invoker with a caller-owned embedder/backend."""

    projects_fields = True
    supports_trusted_filters = True

    def __init__(
        self,
        backend: VectorStoreBackend,
        embed_query: VectorQueryEmbedder,
        *,
        collection: VectorCollectionSpec,
        default_top_k: int,
        offload_sync_backend: bool,
    ) -> None:
        self._backend = backend
        self._embed_query = embed_query
        self._collection = collection
        self._default_top_k = default_top_k
        self._offload_sync_backend = offload_sync_backend
        self._metadata_fields = {
            field.name for field in collection.metadata_fields
        }
        self._filterable_metadata = {
            field.name
            for field in collection.metadata_fields
            if field.filterable
        }

    async def invoke_call(self, call: ToolCall) -> list[dict[str, Any]]:
        if call.endpoint != _SEARCH_ENDPOINT:
            raise RuntimeError(f"unknown vector endpoint: {call.endpoint!r}")

        query = call.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise RuntimeError("vector search requires a non-empty query string")

        top_k = int(call.arguments.get("top_k", self._default_top_k))
        if top_k < 1 or top_k > _MAX_TOP_K:
            raise RuntimeError(f"vector top_k must be between 1 and {_MAX_TOP_K}")

        raw_vector = await _await_if_needed(self._embed_query(query))
        if isinstance(raw_vector, (str, bytes)):
            raise SchemaValidationError("vector embedder must return a numeric iterable")
        try:
            vector = [float(value) for value in raw_vector]
        except (TypeError, ValueError) as exc:
            raise SchemaValidationError(
                "vector embedder must return a numeric iterable"
            ) from exc
        if len(vector) != self._collection.dimension:
            raise SchemaValidationError(
                "vector embedder dimension does not match collection contract: "
                f"expected {self._collection.dimension}, got {len(vector)}"
            )

        selected_fields = tuple(call.fields)
        selected_metadata = tuple(
            field
            for field in selected_fields
            if field in self._metadata_fields
        )
        search_kwargs: dict[str, Any] = {
            "collection": self._collection.name,
            "vector": vector,
            "top_k": top_k,
            "include_fields": selected_metadata,
        }
        search = self._backend.search
        scope = _current_data_scope()
        if scope is not None and scope.trusted_filters:
            trusted_filters = scope.filter_dict()
            unknown_filters = sorted(
                set(trusted_filters) - self._filterable_metadata
            )
            if unknown_filters:
                raise PolicyViolationError(
                    "authorization denied for requested data scope"
                )
            if getattr(self._backend, "supports_trusted_filters", False) is not True:
                raise PolicyViolationError(
                    "authorization denied for requested data scope"
                )
            scoped_backend = cast(ScopedVectorStoreBackend, self._backend)
            search = scoped_backend.search
            search_kwargs["filters"] = trusted_filters

        raw_results = await _call_backend(
            search,
            offload_sync=self._offload_sync_backend,
            **search_kwargs,
        )
        if not isinstance(raw_results, list):
            raise SchemaValidationError("vector backend search must return a list")

        selected = set(selected_fields)
        rows: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_results):
            if not isinstance(raw, dict):
                raise SchemaValidationError(
                    f"vector backend result {index} must be an object"
                )
            row = {
                key: value
                for key, value in raw.items()
                if key in selected
            }
            rows.append(row)
        return rows


async def introspect_vector_backend(
    backend: VectorStoreBackend,
    embed_query: VectorQueryEmbedder,
    *,
    database_name: str,
    namespace: str | None = None,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    default_top_k: int = 10,
    remote: bool = True,
    offload_sync_backend: bool | None = None,
) -> tuple[VectorCollectionBinding, ...]:
    """Compile trusted vector collection descriptors into bounded search capabilities."""

    if not database_name.strip():
        raise ValueError("database_name must be non-empty")
    if default_top_k < 1 or default_top_k > _MAX_TOP_K:
        raise ValueError(f"default_top_k must be between 1 and {_MAX_TOP_K}")

    offload_backend = remote if offload_sync_backend is None else offload_sync_backend
    discovered_raw = await _call_backend(
        backend.list_collections,
        offload_sync=offload_backend,
    )
    discovered = tuple(
        item
        if isinstance(item, VectorCollectionSpec)
        else VectorCollectionSpec.model_validate(item)
        for item in discovered_raw
    )
    names = [collection.name for collection in discovered]
    if len(names) != len(set(names)):
        raise RegistrationError("vector backend returned duplicate collection names")

    selected = None if collections is None else {str(value) for value in collections}
    if selected is not None:
        missing = sorted(selected - set(names))
        if missing:
            raise RegistrationError(
                "unknown vector collections/indexes: " + ", ".join(missing)
            )

    bindings: list[VectorCollectionBinding] = []
    used_names: set[str] = set()
    for collection in discovered:
        if selected is not None and collection.name not in selected:
            continue

        fields = [
            FieldSpec(
                name="id",
                description="Vector record identifier",
                json_schema={"type": ["string", "integer"]},
                identifier=True,
                source_type="database",
            ),
            FieldSpec(
                name="score",
                description=(
                    f"Vector similarity score ({collection.metric})"
                    if collection.metric != "unknown"
                    else "Vector similarity score"
                ),
                json_schema={"type": "number"},
                source_type="database",
            ),
            *[
                FieldSpec(
                    name=field.name,
                    description=field.description,
                    json_schema=dict(field.json_schema),
                    aliases=[field.name.replace("_", " ")],
                    source_type="database",
                )
                for field in collection.metadata_fields
            ],
        ]
        output_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    field.name: field.json_schema or {}
                    for field in fields
                },
                "additionalProperties": False,
            },
        }
        endpoint = EndpointSpec(
            name=_SEARCH_ENDPOINT,
            description=f"Bounded similarity search in vector collection {collection.name}",
            parameters=[
                ParameterSpec(
                    name="query",
                    description="Natural-language query embedded by trusted host code",
                    required=True,
                    location="argument",
                    json_schema={"type": "string", "minLength": 1},
                ),
                ParameterSpec(
                    name="top_k",
                    description="Maximum vector matches to return",
                    required=False,
                    location="argument",
                    json_schema={
                        "type": "integer",
                        "minimum": 1,
                        "maximum": _MAX_TOP_K,
                        "default": default_top_k,
                    },
                ),
            ],
            output_fields=fields,
            output_schema=output_schema,
            read_only=True,
            destructive=False,
            execution_metadata={
                "database_family": "vector",
                "collection": collection.name,
                "dimension": collection.dimension,
                "metric": collection.metric,
                "default_top_k": default_top_k,
            },
            metadata={
                "database_family": "vector",
                "collection": collection.name,
                "dimension": collection.dimension,
                "metric": collection.metric,
                "metadata_fields": [
                    field.model_dump(mode="json")
                    for field in collection.metadata_fields
                ],
                "public_metadata": dict(collection.public_metadata),
            },
        )

        tool_name = _slug(collection.name)
        if tool_name in used_names:
            tool_name = f"{tool_name}_{len(used_names) + 1}"
        used_names.add(tool_name)
        tool = ToolSpec(
            name=tool_name,
            namespace=namespace or _slug(database_name),
            description=collection.description or f"Vector collection {collection.name}",
            endpoints=[endpoint],
            source_type="database",
            provider=database_name,
            access_mode="vector",
            remote=remote,
            execution_metadata={
                "adapter": "vector_store",
                "database_family": "vector",
                "collection": collection.name,
            },
            metadata={
                "adapter": "vector_store",
                "database_family": "vector",
                "collection": collection.name,
            },
        )
        bindings.append(
            VectorCollectionBinding(
                tool=tool,
                invoker=VectorCollectionInvoker(
                    backend,
                    embed_query,
                    collection=collection,
                    default_top_k=default_top_k,
                    offload_sync_backend=offload_backend,
                ),
            )
        )

    return tuple(bindings)

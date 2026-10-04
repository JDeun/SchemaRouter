from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ..errors import RegistrationError, SchemaValidationError
from .vector_store import VectorCollectionSpec, VectorMetadataField


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _enum_text(value: Any) -> str:
    raw = getattr(value, "value", value)
    if raw is None:
        return "unknown"
    text = str(raw)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.lower()


def _json_schema_from_vendor_type(value: Any) -> dict[str, Any]:
    text = _enum_text(value).upper()
    if any(token in text for token in ("INT", "LONG")):
        return {"type": "integer"}
    if any(token in text for token in ("FLOAT", "DOUBLE", "DECIMAL", "NUMBER")):
        return {"type": "number"}
    if "BOOL" in text:
        return {"type": "boolean"}
    if any(token in text for token in ("STRING", "VARCHAR", "TEXT", "KEYWORD", "UUID")):
        return {"type": "string"}
    if "JSON" in text or "OBJECT" in text:
        return {"type": "object"}
    return {}


class QdrantVectorBackend:
    """Thin adapter over a caller-owned qdrant-client instance.

    The client owns endpoint/authentication configuration. SchemaRouter only inspects collection
    metadata and normalizes query results into the provider-neutral vector-store contract.
    """

    def __init__(
        self,
        client: Any,
        *,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[
            str,
            Sequence[VectorMetadataField],
        ]
        | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._client = client
        self._vector_name_by_collection = dict(vector_name_by_collection or {})
        self._metadata_fields_by_collection = {
            name: tuple(fields)
            for name, fields in (metadata_fields_by_collection or {}).items()
        }
        self._filter_builder = filter_builder

    def _collection_names(self) -> list[str]:
        response = self._client.get_collections()
        entries = _read(response, "collections", response)
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise SchemaValidationError(
                "Qdrant get_collections() returned an unexpected response"
            )
        names = [str(_read(entry, "name", entry)) for entry in entries]
        if any(not name for name in names):
            raise SchemaValidationError("Qdrant returned an empty collection name")
        return names

    def _vector_config(self, collection: str, info: Any) -> tuple[int, str, str | None]:
        config = _read(info, "config")
        params = _read(config, "params")
        vectors = _read(params, "vectors")
        if vectors is None:
            raise RegistrationError(
                f"Qdrant collection {collection!r} has no dense vector configuration"
            )

        configured_name = self._vector_name_by_collection.get(collection)
        vector_name: str | None = None
        selected = vectors

        if isinstance(vectors, Mapping):
            if "size" in vectors:
                selected = vectors
            else:
                if configured_name is not None:
                    if configured_name not in vectors:
                        raise RegistrationError(
                            f"Qdrant collection {collection!r} has no vector "
                            f"{configured_name!r}"
                        )
                    vector_name = configured_name
                    selected = vectors[configured_name]
                elif len(vectors) == 1:
                    vector_name, selected = next(iter(vectors.items()))
                    vector_name = str(vector_name)
                else:
                    raise RegistrationError(
                        f"Qdrant collection {collection!r} has multiple named vectors; "
                        "set vector_name_by_collection"
                    )
        elif configured_name is not None:
            # qdrant-client model objects for named vectors can expose a root mapping.
            root = _read(vectors, "root")
            if isinstance(root, Mapping):
                if configured_name not in root:
                    raise RegistrationError(
                        f"Qdrant collection {collection!r} has no vector "
                        f"{configured_name!r}"
                    )
                vector_name = configured_name
                selected = root[configured_name]

        size = _read(selected, "size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise SchemaValidationError(
                f"Qdrant collection {collection!r} did not expose a valid vector size"
            )
        metric = _enum_text(_read(selected, "distance"))
        return size, metric, vector_name

    def _metadata_fields(self, collection: str, info: Any) -> tuple[VectorMetadataField, ...]:
        declared: dict[str, VectorMetadataField] = {
            field.name: field.model_copy(deep=True)
            for field in self._metadata_fields_by_collection.get(collection, ())
        }
        payload_schema = _read(info, "payload_schema", {})
        if isinstance(payload_schema, Mapping):
            for name, schema in payload_schema.items():
                field_name = str(name)
                if field_name in declared:
                    existing = declared[field_name]
                    if not existing.filterable:
                        declared[field_name] = existing.model_copy(
                            update={"filterable": True}
                        )
                    continue
                declared[field_name] = VectorMetadataField(
                    name=field_name,
                    json_schema=_json_schema_from_vendor_type(
                        _read(schema, "data_type", schema)
                    ),
                    filterable=True,
                )
        return tuple(declared[name] for name in sorted(declared))

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for collection in self._collection_names():
            info = self._client.get_collection(collection_name=collection)
            dimension, metric, vector_name = self._vector_config(collection, info)
            results.append(
                VectorCollectionSpec(
                    name=collection,
                    dimension=dimension,
                    metric=metric,
                    metadata_fields=self._metadata_fields(collection, info),
                    public_metadata=(
                        {}
                        if vector_name is None
                        else {"vector_name": vector_name}
                    ),
                )
            )
        return tuple(results)

    @staticmethod
    def _qdrant_filter(filters: Mapping[str, Any]) -> Any:
        try:
            models = importlib.import_module("qdrant_client.models")
        except ImportError as exc:
            raise RegistrationError(
                "Qdrant trusted metadata filtering requires qdrant-client"
            ) from exc

        conditions = []
        for field, value in sorted(filters.items()):
            if isinstance(value, tuple):
                match = models.MatchAny(any=list(value))
            else:
                match = models.MatchValue(value=value)
            conditions.append(
                models.FieldCondition(
                    key=field,
                    match=match,
                )
            )
        return models.Filter(must=conditions)

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        vector_name = self._vector_name_by_collection.get(collection)
        kwargs: dict[str, Any] = {
            "collection_name": collection,
            "query": list(vector),
            "limit": top_k,
            "with_vectors": False,
            "with_payload": list(include_fields) if include_fields else False,
        }
        if vector_name is not None:
            kwargs["using"] = vector_name
        if filters:
            kwargs["query_filter"] = (
                self._filter_builder(filters)
                if self._filter_builder is not None
                else self._qdrant_filter(filters)
            )

        response = self._client.query_points(**kwargs)
        points = _read(response, "points", response)
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
            raise SchemaValidationError(
                "Qdrant query_points() returned an unexpected response"
            )

        rows: list[dict[str, Any]] = []
        for point in points:
            payload = _read(point, "payload", {}) or {}
            if not isinstance(payload, Mapping):
                raise SchemaValidationError("Qdrant point payload must be an object")
            row: dict[str, Any] = {
                "id": _read(point, "id"),
                "score": float(_read(point, "score")),
            }
            row.update(
                {
                    field: payload[field]
                    for field in include_fields
                    if field in payload
                }
            )
            rows.append(row)
        return rows


class PineconeVectorBackend:
    """Thin adapter over a caller-owned Pinecone control-plane client.

    Index clients are created through the caller-owned control client. Metadata fields are
    explicit because Pinecone index configuration does not guarantee a complete typed schema for
    every stored metadata key.
    """

    def __init__(
        self,
        client: Any,
        *,
        metadata_fields_by_index: Mapping[
            str,
            Sequence[VectorMetadataField],
        ]
        | None = None,
        namespace_by_index: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._metadata_fields_by_index = {
            name: tuple(fields)
            for name, fields in (metadata_fields_by_index or {}).items()
        }
        self._namespace_by_index = dict(namespace_by_index or {})
        self._index_cache: dict[str, Any] = {}
        self._index_info: dict[str, Any] = {}

    def _index_names(self) -> list[str]:
        response = self._client.list_indexes()
        names_method = _read(response, "names")
        if callable(names_method):
            raw_names = names_method()
        else:
            raw_entries = _read(response, "indexes", response)
            if not isinstance(raw_entries, Sequence) or isinstance(
                raw_entries,
                (str, bytes),
            ):
                raise SchemaValidationError(
                    "Pinecone list_indexes() returned an unexpected response"
                )
            raw_names = [
                _read(entry, "name", entry)
                for entry in raw_entries
            ]
        names = [str(value) for value in raw_names]
        if any(not value for value in names):
            raise SchemaValidationError("Pinecone returned an empty index name")
        return names

    def _describe_index(self, index_name: str) -> Any:
        if index_name not in self._index_info:
            self._index_info[index_name] = self._client.describe_index(
                name=index_name
            )
        return self._index_info[index_name]

    def _index(self, index_name: str) -> Any:
        cached = self._index_cache.get(index_name)
        if cached is not None:
            return cached

        info = self._describe_index(index_name)
        host = _read(info, "host")
        index_factory = _read(self._client, "Index")
        if not callable(index_factory):
            raise RegistrationError(
                "Pinecone client does not expose an Index(...) factory"
            )
        if isinstance(host, str) and host:
            try:
                index = index_factory(host=host)
            except TypeError:
                index = index_factory(index_name)
        else:
            index = index_factory(index_name)
        self._index_cache[index_name] = index
        return index

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for index_name in self._index_names():
            info = self._describe_index(index_name)
            vector_type = _enum_text(_read(info, "vector_type", "dense"))
            if vector_type not in {"dense", "unknown"}:
                # The current generic contract represents dense query vectors only.
                continue
            dimension = _read(info, "dimension")
            if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
                raise SchemaValidationError(
                    f"Pinecone index {index_name!r} did not expose a valid dense dimension"
                )
            metric = _enum_text(_read(info, "metric"))
            results.append(
                VectorCollectionSpec(
                    name=index_name,
                    dimension=dimension,
                    metric=metric,
                    metadata_fields=tuple(
                        field.model_copy(deep=True)
                        for field in self._metadata_fields_by_index.get(
                            index_name,
                            (),
                        )
                    ),
                    public_metadata=(
                        {}
                        if index_name not in self._namespace_by_index
                        else {
                            "namespace": self._namespace_by_index[index_name]
                        }
                    ),
                )
            )
        return tuple(results)

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        declared = {
            field.name: field
            for field in self._metadata_fields_by_index.get(collection, ())
        }
        unknown_fields = sorted(set(include_fields) - set(declared))
        if unknown_fields:
            raise SchemaValidationError(
                "Pinecone search requested undeclared metadata fields: "
                + ", ".join(unknown_fields)
            )

        if filters:
            allowed_filters = {
                field.name
                for field in declared.values()
                if field.filterable
            }
            unknown_filters = sorted(set(filters) - allowed_filters)
            if unknown_filters:
                raise SchemaValidationError(
                    "Pinecone trusted filter requested non-filterable metadata fields: "
                    + ", ".join(unknown_filters)
                )

        kwargs: dict[str, Any] = {
            "vector": list(vector),
            "top_k": top_k,
            "include_metadata": bool(include_fields),
            "include_values": False,
        }
        namespace = self._namespace_by_index.get(collection)
        if namespace is not None:
            kwargs["namespace"] = namespace
        if filters:
            kwargs["filter"] = dict(filters)

        response = self._index(collection).query(**kwargs)
        matches = _read(response, "matches", response)
        if not isinstance(matches, Sequence) or isinstance(
            matches,
            (str, bytes),
        ):
            raise SchemaValidationError(
                "Pinecone query() returned an unexpected response"
            )

        rows: list[dict[str, Any]] = []
        for match in matches:
            metadata = _read(match, "metadata", {}) or {}
            if not isinstance(metadata, Mapping):
                raise SchemaValidationError(
                    "Pinecone match metadata must be an object"
                )
            score = _read(match, "score")
            if score is None:
                raise SchemaValidationError("Pinecone match has no score")
            row: dict[str, Any] = {
                "id": _read(match, "id"),
                "score": float(score),
            }
            row.update(
                {
                    field: metadata[field]
                    for field in include_fields
                    if field in metadata
                }
            )
            rows.append(row)
        return rows


class WeaviateVectorBackend:
    """Thin adapter over a caller-owned Weaviate Python v4 client.

    Weaviate collection configuration is used for property discovery. Query-vector dimensions are
    explicit because external vector dimensions are not guaranteed to be recoverable from every
    collection/vectorizer configuration.
    """

    def __init__(
        self,
        client: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        target_vector_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._dimension_by_collection = {
            name: int(value)
            for name, value in dimension_by_collection.items()
        }
        self._target_vector_by_collection = dict(target_vector_by_collection or {})
        self._metric_by_collection = dict(metric_by_collection or {})
        self._collection_cache: dict[str, Any] = {}
        self._config_cache: dict[str, Any] = {}

    def _collection_names(self) -> list[str]:
        collections_api = _read(self._client, "collections")
        list_all = _read(collections_api, "list_all")
        if not callable(list_all):
            raise RegistrationError(
                "Weaviate client does not expose collections.list_all(...)"
            )
        response = list_all(simple=False)
        if isinstance(response, Mapping):
            names = [str(name) for name in response]
        elif isinstance(response, Sequence) and not isinstance(
            response,
            (str, bytes),
        ):
            names = [str(_read(value, "name", value)) for value in response]
        else:
            raise SchemaValidationError(
                "Weaviate collections.list_all() returned an unexpected response"
            )
        return names

    def _collection(self, collection_name: str) -> Any:
        cached = self._collection_cache.get(collection_name)
        if cached is not None:
            return cached
        collections_api = _read(self._client, "collections")
        use = _read(collections_api, "use") or _read(collections_api, "get")
        if not callable(use):
            raise RegistrationError(
                "Weaviate client does not expose collections.use/get(...)"
            )
        collection = use(collection_name)
        self._collection_cache[collection_name] = collection
        return collection

    def _config(self, collection_name: str) -> Any:
        cached = self._config_cache.get(collection_name)
        if cached is not None:
            return cached
        collection = self._collection(collection_name)
        config_api = _read(collection, "config")
        getter = _read(config_api, "get")
        if not callable(getter):
            raise RegistrationError(
                "Weaviate collection does not expose config.get()"
            )
        config = getter()
        self._config_cache[collection_name] = config
        return config

    def _target_vector(self, collection_name: str, config: Any) -> str | None:
        configured = self._target_vector_by_collection.get(collection_name)
        vector_config = _read(config, "vector_config")
        if not vector_config:
            return configured

        if isinstance(vector_config, Mapping):
            names = [str(name) for name in vector_config]
        else:
            names = []
        if configured is not None:
            if names and configured not in names:
                raise RegistrationError(
                    f"Weaviate collection {collection_name!r} has no target vector "
                    f"{configured!r}"
                )
            return configured
        if len(names) == 1:
            return names[0]
        if len(names) > 1:
            raise RegistrationError(
                f"Weaviate collection {collection_name!r} has multiple named vectors; "
                "set target_vector_by_collection"
            )
        return None

    def _metadata_fields(
        self,
        collection_name: str,
        config: Any,
    ) -> tuple[VectorMetadataField, ...]:
        raw_properties = _read(config, "properties", ()) or ()
        if not isinstance(raw_properties, Sequence) or isinstance(
            raw_properties,
            (str, bytes),
        ):
            raise SchemaValidationError(
                "Weaviate collection properties must be a sequence"
            )
        fields: list[VectorMetadataField] = []
        for raw in raw_properties:
            name = str(_read(raw, "name", ""))
            if not name:
                continue
            data_type = _read(raw, "data_type")
            fields.append(
                VectorMetadataField(
                    name=name,
                    description=str(_read(raw, "description", "") or ""),
                    json_schema=_json_schema_from_vendor_type(data_type),
                    filterable=bool(_read(raw, "index_filterable", False)),
                )
            )
        return tuple(fields)

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for collection_name in self._collection_names():
            dimension = self._dimension_by_collection.get(collection_name)
            if dimension is None or dimension < 1:
                raise RegistrationError(
                    f"Weaviate collection {collection_name!r} requires an explicit "
                    "dimension_by_collection entry"
                )
            config = self._config(collection_name)
            target_vector = self._target_vector(collection_name, config)
            results.append(
                VectorCollectionSpec(
                    name=collection_name,
                    dimension=dimension,
                    metric=self._metric_by_collection.get(
                        collection_name,
                        "unknown",
                    ),
                    metadata_fields=self._metadata_fields(
                        collection_name,
                        config,
                    ),
                    public_metadata=(
                        {}
                        if target_vector is None
                        else {"target_vector": target_vector}
                    ),
                )
            )
        return tuple(results)

    @staticmethod
    def _weaviate_filter(filters: Mapping[str, Any]) -> Any:
        try:
            query_module = importlib.import_module("weaviate.classes.query")
        except ImportError as exc:
            raise RegistrationError(
                "Weaviate trusted filtering requires weaviate-client"
            ) from exc

        filter_class = _read(query_module, "Filter")
        if filter_class is None:
            raise RegistrationError("weaviate.classes.query.Filter is unavailable")

        combined: Any = None
        for field, value in sorted(filters.items()):
            by_property = filter_class.by_property(field)
            if isinstance(value, tuple):
                if not value:
                    raise SchemaValidationError(
                        "Weaviate trusted filter cannot use an empty value set"
                    )
                current: Any = None
                for entry in value:
                    condition = by_property.equal(entry)
                    current = condition if current is None else current | condition
            else:
                current = by_property.equal(value)
            combined = current if combined is None else combined & current
        return combined

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        config = self._config(collection)
        metadata_fields = {
            field.name: field
            for field in self._metadata_fields(collection, config)
        }
        unknown_fields = sorted(set(include_fields) - set(metadata_fields))
        if unknown_fields:
            raise SchemaValidationError(
                "Weaviate search requested undeclared properties: "
                + ", ".join(unknown_fields)
            )
        if filters:
            allowed_filters = {
                field.name
                for field in metadata_fields.values()
                if field.filterable
            }
            unknown_filters = sorted(set(filters) - allowed_filters)
            if unknown_filters:
                raise SchemaValidationError(
                    "Weaviate trusted filter requested non-filterable properties: "
                    + ", ".join(unknown_filters)
                )

        try:
            query_module = importlib.import_module("weaviate.classes.query")
        except ImportError as exc:
            raise RegistrationError(
                "Weaviate native search requires weaviate-client"
            ) from exc
        metadata_query = _read(query_module, "MetadataQuery")
        if metadata_query is None:
            raise RegistrationError(
                "weaviate.classes.query.MetadataQuery is unavailable"
            )

        kwargs: dict[str, Any] = {
            "near_vector": list(vector),
            "limit": top_k,
            "return_properties": list(include_fields),
            "return_metadata": metadata_query(distance=True),
        }
        target_vector = self._target_vector(collection, config)
        if target_vector is not None:
            kwargs["target_vector"] = target_vector
        if filters:
            kwargs["filters"] = self._weaviate_filter(filters)

        query_api = _read(self._collection(collection), "query")
        near_vector = _read(query_api, "near_vector")
        if not callable(near_vector):
            raise RegistrationError(
                "Weaviate collection does not expose query.near_vector(...)"
            )
        response = near_vector(**kwargs)
        objects = _read(response, "objects", ())
        if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
            raise SchemaValidationError(
                "Weaviate near_vector() returned an unexpected response"
            )

        rows: list[dict[str, Any]] = []
        for obj in objects:
            properties = _read(obj, "properties", {}) or {}
            if not isinstance(properties, Mapping):
                raise SchemaValidationError(
                    "Weaviate object properties must be an object"
                )
            metadata = _read(obj, "metadata")
            distance = _read(metadata, "distance")
            if distance is None:
                raise SchemaValidationError(
                    "Weaviate vector result has no distance metadata"
                )
            row: dict[str, Any] = {
                "id": str(_read(obj, "uuid")),
                "score": float(distance),
            }
            row.update(
                {
                    field: properties[field]
                    for field in include_fields
                    if field in properties
                }
            )
            rows.append(row)
        return rows


class MilvusVectorBackend:
    """Thin adapter over a caller-owned pymilvus.MilvusClient-compatible client."""

    def __init__(
        self,
        client: Any,
        *,
        vector_field_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._vector_field_by_collection = dict(vector_field_by_collection or {})
        self._metric_by_collection = dict(metric_by_collection or {})
        self._schema_cache: dict[str, dict[str, Any]] = {}

    def _describe(self, collection: str) -> dict[str, Any]:
        cached = self._schema_cache.get(collection)
        if cached is not None:
            return cached
        raw = self._client.describe_collection(collection_name=collection)
        if not isinstance(raw, Mapping):
            raise SchemaValidationError(
                "Milvus describe_collection() must return an object"
            )
        result = dict(raw)
        self._schema_cache[collection] = result
        return result

    def _collection_contract(
        self,
        collection: str,
    ) -> tuple[str, int, tuple[VectorMetadataField, ...]]:
        description = self._describe(collection)
        raw_fields = description.get("fields", ())
        if not isinstance(raw_fields, Sequence):
            raise SchemaValidationError("Milvus collection fields must be a list")

        vector_fields: list[tuple[str, int]] = []
        metadata: list[VectorMetadataField] = []
        for raw in raw_fields:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("name", ""))
            if not name:
                continue
            params = raw.get("params") or {}
            dimension = params.get("dim") if isinstance(params, Mapping) else None
            if dimension is not None:
                try:
                    parsed_dimension = int(dimension)
                except (TypeError, ValueError) as exc:
                    raise SchemaValidationError(
                        f"Milvus vector field {name!r} has an invalid dimension"
                    ) from exc
                vector_fields.append((name, parsed_dimension))
                continue
            if bool(raw.get("is_primary")):
                continue
            metadata.append(
                VectorMetadataField(
                    name=name,
                    description=str(raw.get("description") or ""),
                    json_schema=_json_schema_from_vendor_type(raw.get("type")),
                    filterable=True,
                )
            )

        configured = self._vector_field_by_collection.get(collection)
        if configured is not None:
            matches = [
                (name, dimension)
                for name, dimension in vector_fields
                if name == configured
            ]
            if not matches:
                raise RegistrationError(
                    f"Milvus collection {collection!r} has no vector field {configured!r}"
                )
            vector_field, dimension = matches[0]
        elif len(vector_fields) == 1:
            vector_field, dimension = vector_fields[0]
        elif not vector_fields:
            raise RegistrationError(
                f"Milvus collection {collection!r} has no dense vector field"
            )
        else:
            raise RegistrationError(
                f"Milvus collection {collection!r} has multiple vector fields; "
                "set vector_field_by_collection"
            )

        return vector_field, dimension, tuple(metadata)

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        names = self._client.list_collections()
        if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
            raise SchemaValidationError(
                "Milvus list_collections() returned an unexpected response"
            )
        results: list[VectorCollectionSpec] = []
        for raw_name in names:
            collection = str(raw_name)
            vector_field, dimension, metadata = self._collection_contract(collection)
            results.append(
                VectorCollectionSpec(
                    name=collection,
                    dimension=dimension,
                    metric=self._metric_by_collection.get(collection, "unknown"),
                    metadata_fields=metadata,
                    public_metadata={"vector_field": vector_field},
                )
            )
        return tuple(results)

    def _filter_template(
        self,
        collection: str,
        filters: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        _vector_field, _dimension, metadata = self._collection_contract(collection)
        allowed = {field.name for field in metadata if field.filterable}
        unknown = sorted(set(filters) - allowed)
        if unknown:
            raise SchemaValidationError(
                "Milvus filter requested unknown metadata fields: "
                + ", ".join(unknown)
            )

        expressions: list[str] = []
        values: dict[str, Any] = {}
        for index, (field, value) in enumerate(sorted(filters.items())):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) is None:
                raise SchemaValidationError(
                    "Milvus trusted filter field has an unsafe identifier"
                )
            placeholder = f"p{index}"
            if isinstance(value, tuple):
                expressions.append(f"{field} IN {{{placeholder}}}")
                values[placeholder] = list(value)
            else:
                expressions.append(f"{field} == {{{placeholder}}}")
                values[placeholder] = value
        return " AND ".join(expressions), values

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        vector_field, _dimension, _metadata = self._collection_contract(collection)
        kwargs: dict[str, Any] = {
            "collection_name": collection,
            "data": [list(vector)],
            "anns_field": vector_field,
            "limit": top_k,
            "output_fields": list(include_fields),
        }
        if filters:
            expression, values = self._filter_template(collection, filters)
            kwargs["filter"] = expression
            kwargs["filter_params"] = values

        raw_results = self._client.search(**kwargs)
        if not isinstance(raw_results, Sequence) or isinstance(
            raw_results,
            (str, bytes),
        ):
            raise SchemaValidationError("Milvus search() returned an unexpected response")
        hits = raw_results[0] if raw_results else []
        if not isinstance(hits, Sequence) or isinstance(hits, (str, bytes)):
            raise SchemaValidationError("Milvus search hits must be a list")

        rows: list[dict[str, Any]] = []
        for hit in hits:
            if not isinstance(hit, Mapping):
                raise SchemaValidationError("Milvus search hit must be an object")
            entity = hit.get("entity") or {}
            if not isinstance(entity, Mapping):
                raise SchemaValidationError("Milvus hit entity must be an object")
            score_raw = hit.get("distance", hit.get("score"))
            if score_raw is None:
                raise SchemaValidationError("Milvus search hit has no distance/score")
            row: dict[str, Any] = {
                "id": hit.get("id"),
                "score": float(score_raw),
            }
            row.update(
                {
                    field: entity[field]
                    for field in include_fields
                    if field in entity
                }
            )
            rows.append(row)
        return rows

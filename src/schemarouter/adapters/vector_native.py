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

class PineconeVectorBackend:
    """Thin adapter over a caller-owned Pinecone control-plane client."""

    def __init__(
        self,
        client: Any,
        *,
        indexes: Sequence[str] | None = None,
        namespace_by_index: Mapping[str, str] | None = None,
        metadata_fields_by_index: Mapping[str, Sequence[VectorMetadataField]] | None = None,
    ) -> None:
        self._client = client
        self._indexes = None if indexes is None else tuple(str(value) for value in indexes)
        self._namespaces = dict(namespace_by_index or {})
        self._metadata_fields = {
            str(name): tuple(fields)
            for name, fields in (metadata_fields_by_index or {}).items()
        }
        self._index_cache: dict[str, Any] = {}

    def _index_names(self) -> tuple[str, ...]:
        if self._indexes is not None:
            return self._indexes
        raw = self._client.list_indexes()
        names = getattr(raw, "names", None)
        if callable(names):
            values = names()
        elif isinstance(raw, Mapping):
            values = raw.get("indexes", raw.get("names", ()))
        else:
            values = raw
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise SchemaValidationError("Pinecone list_indexes() returned an unexpected response")
        result = tuple(str(_read(item, "name", item)) for item in values)
        if any(not name for name in result):
            raise SchemaValidationError("Pinecone returned an empty index name")
        return result

    def _describe(self, index: str) -> Any:
        try:
            return self._client.describe_index(name=index)
        except TypeError:
            return self._client.describe_index(index)

    def _index(self, name: str) -> Any:
        cached = self._index_cache.get(name)
        if cached is not None:
            return cached
        factory = getattr(self._client, "Index", None)
        if not callable(factory):
            factory = getattr(self._client, "index", None)
        if not callable(factory):
            raise RegistrationError("Pinecone client must expose Index() or index()")
        value = factory(name)
        self._index_cache[name] = value
        return value

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for name in self._index_names():
            description = self._describe(name)
            dimension = _read(description, "dimension")
            if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
                raise SchemaValidationError(
                    f"Pinecone index {name!r} did not expose a valid dimension"
                )
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=_enum_text(_read(description, "metric")),
                    metadata_fields=self._metadata_fields.get(name, ()),
                    public_metadata=(
                        {} if name not in self._namespaces else {"namespace": self._namespaces[name]}
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
        if collection not in set(self._index_names()):
            raise RegistrationError(f"unknown Pinecone index {collection!r}")
        allowed = {
            field.name
            for field in self._metadata_fields.get(collection, ())
            if field.filterable
        }
        pinecone_filter: dict[str, Any] = {}
        for field, value in sorted((filters or {}).items()):
            if field not in allowed:
                raise SchemaValidationError(
                    f"Pinecone filter field {field!r} is not declared filterable"
                )
            pinecone_filter[field] = (
                {"$in": list(value)} if isinstance(value, tuple) else {"$eq": value}
            )
        kwargs: dict[str, Any] = {
            "vector": list(vector),
            "top_k": top_k,
            "include_metadata": bool(include_fields),
            "include_values": False,
        }
        namespace = self._namespaces.get(collection)
        if namespace is not None:
            kwargs["namespace"] = namespace
        if pinecone_filter:
            kwargs["filter"] = pinecone_filter
        matches = _read(self._index(collection).query(**kwargs), "matches", ())
        if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
            raise SchemaValidationError("Pinecone query() returned an unexpected response")
        rows: list[dict[str, Any]] = []
        for match in matches:
            metadata = _read(match, "metadata", {}) or {}
            if not isinstance(metadata, Mapping):
                raise SchemaValidationError("Pinecone match metadata must be an object")
            row: dict[str, Any] = {
                "id": _read(match, "id"),
                "score": float(_read(match, "score", 0.0)),
            }
            row.update({field: metadata[field] for field in include_fields if field in metadata})
            rows.append(row)
        return rows


class WeaviateVectorBackend:
    """Thin adapter over a caller-owned Weaviate v4-style client."""

    def __init__(
        self,
        client: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        metric_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[VectorMetadataField]] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        metadata_query_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._client = client
        self._dimensions = {
            str(key): int(value) for key, value in dimension_by_collection.items()
        }
        self._metrics = {
            str(key): str(value)
            for key, value in (metric_by_collection or {}).items()
        }
        self._declared_metadata = {
            str(name): tuple(fields)
            for name, fields in (metadata_fields_by_collection or {}).items()
        }
        self._filter_builder = filter_builder
        self._metadata_query_factory = metadata_query_factory
        self._configs: dict[str, Any] = {}

    def _discover(self) -> Mapping[str, Any]:
        raw = self._client.collections.list_all(simple=False)
        if isinstance(raw, Mapping):
            return raw
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return {
                str(_read(item, "name", "")): item
                for item in raw
                if str(_read(item, "name", ""))
            }
        raise SchemaValidationError("Weaviate list_all() returned an unexpected response")

    def _metadata(self, collection: str, config: Any) -> tuple[VectorMetadataField, ...]:
        fields: dict[str, VectorMetadataField] = {
            field.name: field.model_copy(deep=True)
            for field in self._declared_metadata.get(collection, ())
        }
        properties = _read(config, "properties", ()) or ()
        if isinstance(properties, Mapping):
            properties = tuple(properties.values())
        if isinstance(properties, Sequence) and not isinstance(properties, (str, bytes)):
            for prop in properties:
                name = str(_read(prop, "name", ""))
                if not name or name in fields:
                    continue
                data_type = _read(prop, "data_type", _read(prop, "dataType"))
                fields[name] = VectorMetadataField(
                    name=name,
                    json_schema=_json_schema_from_vendor_type(data_type),
                    filterable=True,
                )
        return tuple(fields[name] for name in sorted(fields))

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        configs = self._discover()
        self._configs = {str(name): config for name, config in configs.items()}
        results: list[VectorCollectionSpec] = []
        for name, config in sorted(self._configs.items()):
            dimension = self._dimensions.get(name)
            if dimension is None or dimension < 1:
                raise RegistrationError(
                    f"Weaviate collection {name!r} requires dimension_by_collection"
                )
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=self._metrics.get(name, "unknown"),
                    metadata_fields=self._metadata(name, config),
                )
            )
        return tuple(results)

    def _trusted_filter(self, filters: Mapping[str, Any]) -> Any:
        if self._filter_builder is not None:
            return self._filter_builder(filters)
        try:
            query_module = importlib.import_module("weaviate.classes.query")
            filter_type = query_module.Filter
        except (ImportError, AttributeError) as exc:
            raise RegistrationError(
                "Weaviate trusted metadata filtering requires weaviate-client "
                "or a caller-supplied filter_builder"
            ) from exc
        clauses = []
        for field, value in sorted(filters.items()):
            prop = filter_type.by_property(field)
            clauses.append(
                prop.contains_any(list(value)) if isinstance(value, tuple) else prop.equal(value)
            )
        if not clauses:
            return None
        combined = clauses[0]
        for clause in clauses[1:]:
            combined = combined & clause
        return combined

    def _metadata_query(self) -> Any:
        if self._metadata_query_factory is not None:
            return self._metadata_query_factory()
        try:
            query_module = importlib.import_module("weaviate.classes.query")
            return query_module.MetadataQuery(distance=True, certainty=True, score=True)
        except (ImportError, AttributeError, TypeError):
            return None

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if collection not in self._configs:
            self.list_collections()
        if collection not in self._configs:
            raise RegistrationError(f"unknown Weaviate collection {collection!r}")
        allowed = {
            field.name
            for field in self._metadata(collection, self._configs[collection])
            if field.filterable
        }
        unknown = sorted(set(filters or {}) - allowed)
        if unknown:
            raise SchemaValidationError(
                "Weaviate filter requested unknown metadata fields: " + ", ".join(unknown)
            )
        kwargs: dict[str, Any] = {
            "near_vector": list(vector),
            "limit": top_k,
            "return_properties": list(include_fields),
        }
        if filters:
            kwargs["filters"] = self._trusted_filter(filters)
        metadata_query = self._metadata_query()
        if metadata_query is not None:
            kwargs["return_metadata"] = metadata_query
        response = self._client.collections.get(collection).query.near_vector(**kwargs)
        objects = _read(response, "objects", ())
        if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
            raise SchemaValidationError("Weaviate near_vector() returned an unexpected response")
        rows: list[dict[str, Any]] = []
        for obj in objects:
            properties = _read(obj, "properties", {}) or {}
            if not isinstance(properties, Mapping):
                raise SchemaValidationError("Weaviate object properties must be an object")
            metadata = _read(obj, "metadata", None)
            score = _read(metadata, "score", None)
            if score is None:
                score = _read(metadata, "certainty", None)
            if score is None:
                score = _read(metadata, "distance", 0.0)
            row: dict[str, Any] = {
                "id": str(_read(obj, "uuid", _read(obj, "id", ""))),
                "score": float(score),
            }
            row.update({field: properties[field] for field in include_fields if field in properties})
            rows.append(row)
        return rows


class ChromaVectorBackend:
    """Thin adapter over a caller-owned Chroma client."""

    def __init__(
        self,
        client: Any,
        *,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[VectorMetadataField]] | None = None,
    ) -> None:
        self._client = client
        self._dimensions = {
            str(key): int(value)
            for key, value in (dimension_by_collection or {}).items()
        }
        self._declared_metadata = {
            str(name): tuple(fields)
            for name, fields in (metadata_fields_by_collection or {}).items()
        }
        self._collections: dict[str, Any] = {}

    def _collection(self, name: str) -> Any:
        cached = self._collections.get(name)
        if cached is not None:
            return cached
        value = self._client.get_collection(name=name)
        self._collections[name] = value
        return value

    def _metadata_fields(self, name: str, collection: Any) -> tuple[VectorMetadataField, ...]:
        declared = {
            field.name: field.model_copy(deep=True)
            for field in self._declared_metadata.get(name, ())
        }
        if declared:
            return tuple(declared[key] for key in sorted(declared))
        peek = getattr(collection, "peek", None)
        if not callable(peek):
            return ()
        raw = peek(limit=1)
        if not isinstance(raw, Mapping):
            return ()
        metadatas = raw.get("metadatas") or ()
        if (
            isinstance(metadatas, Sequence)
            and not isinstance(metadatas, (str, bytes))
            and metadatas
            and isinstance(metadatas[0], Mapping)
        ):
            for key, value in metadatas[0].items():
                declared[str(key)] = VectorMetadataField(
                    name=str(key),
                    json_schema=_json_schema_from_vendor_type(type(value).__name__),
                    filterable=True,
                )
        return tuple(declared[key] for key in sorted(declared))

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        raw = self._client.list_collections()
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise SchemaValidationError("Chroma list_collections() returned an unexpected response")
        results: list[VectorCollectionSpec] = []
        for item in raw:
            name = str(_read(item, "name", item))
            if not name:
                continue
            collection = item if hasattr(item, "query") else self._collection(name)
            self._collections[name] = collection
            metadata = _read(collection, "metadata", {}) or {}
            if not isinstance(metadata, Mapping):
                metadata = {}
            dimension = self._dimensions.get(name, metadata.get("dimension"))
            if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
                raise RegistrationError(
                    f"Chroma collection {name!r} requires dimension_by_collection "
                    "or metadata['dimension']"
                )
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=str(metadata.get("hnsw:space") or "unknown"),
                    metadata_fields=self._metadata_fields(name, collection),
                )
            )
        return tuple(results)

    @staticmethod
    def _where(filters: Mapping[str, Any]) -> Mapping[str, Any]:
        clauses = [
            {
                field: (
                    {"$in": list(value)} if isinstance(value, tuple) else {"$eq": value}
                )
            }
            for field, value in sorted(filters.items())
        ]
        if not clauses:
            return {}
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def search(
        self,
        *,
        collection: str,
        vector: Sequence[float],
        top_k: int,
        include_fields: tuple[str, ...],
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "query_embeddings": [list(vector)],
            "n_results": top_k,
            "include": ["metadatas", "distances"],
        }
        if filters:
            kwargs["where"] = self._where(filters)
        raw = self._collection(collection).query(**kwargs)
        if not isinstance(raw, Mapping):
            raise SchemaValidationError("Chroma query() returned an unexpected response")
        ids = raw.get("ids") or [[]]
        distances = raw.get("distances") or [[]]
        metadatas = raw.get("metadatas") or [[]]
        first_ids = ids[0] if ids else []
        first_distances = distances[0] if distances else []
        first_metadatas = metadatas[0] if metadatas else []
        rows: list[dict[str, Any]] = []
        for index, identifier in enumerate(first_ids):
            metadata = (
                first_metadatas[index]
                if index < len(first_metadatas) and isinstance(first_metadatas[index], Mapping)
                else {}
            )
            score = first_distances[index] if index < len(first_distances) else 0.0
            row: dict[str, Any] = {"id": identifier, "score": float(score)}
            row.update({field: metadata[field] for field in include_fields if field in metadata})
            rows.append(row)
        return rows


class PgVectorBackend:
    """Bounded pgvector adapter over a caller-owned SQLAlchemy Engine."""

    def __init__(
        self,
        engine: Any,
        *,
        tables: Sequence[str] | None = None,
        schema: str | None = None,
        vector_column_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
    ) -> None:
        self._engine = engine
        self._tables = None if tables is None else tuple(str(value) for value in tables)
        self._schema = schema
        self._vector_columns = dict(vector_column_by_table or {})
        self._metrics = {
            str(key): str(value).lower()
            for key, value in (metric_by_table or {}).items()
        }
        self._cache: dict[
            str,
            tuple[Any, Any, Any, tuple[VectorMetadataField, ...], int],
        ] = {}

    @staticmethod
    def _sqlalchemy() -> Any:
        try:
            return importlib.import_module("sqlalchemy")
        except ImportError as exc:
            raise RegistrationError(
                "pgvector adapter requires the optional 'database' extra (SQLAlchemy)"
            ) from exc

    def _table_names(self) -> tuple[str, ...]:
        if self._tables is not None:
            return self._tables
        sa = self._sqlalchemy()
        return tuple(
            str(name)
            for name in sa.inspect(self._engine).get_table_names(schema=self._schema)
        )

    @staticmethod
    def _schema_for_column(column: Any) -> dict[str, Any]:
        try:
            python_type = column.type.python_type
        except (AttributeError, NotImplementedError):
            return {}
        if python_type is bool:
            return {"type": "boolean"}
        if python_type is int:
            return {"type": "integer"}
        if python_type is float:
            return {"type": "number"}
        if python_type is str:
            return {"type": "string"}
        return {}

    def _reflect(
        self,
        table_name: str,
    ) -> tuple[Any, Any, Any, tuple[VectorMetadataField, ...], int]:
        cached = self._cache.get(table_name)
        if cached is not None:
            return cached
        sa = self._sqlalchemy()
        table = sa.Table(
            table_name,
            sa.MetaData(),
            schema=self._schema,
            autoload_with=self._engine,
        )
        configured = self._vector_columns.get(table_name)
        candidates = [
            column
            for column in table.columns
            if (
                column.name == configured
                if configured is not None
                else column.type.__class__.__name__.lower() in {"vector", "halfvec"}
            )
        ]
        if len(candidates) != 1:
            if configured is not None:
                raise RegistrationError(
                    f"pgvector table {table_name!r} has no unique vector column {configured!r}"
                )
            raise RegistrationError(
                f"pgvector table {table_name!r} requires exactly one dense vector column "
                "or vector_column_by_table"
            )
        vector_column = candidates[0]
        dimension = getattr(vector_column.type, "dim", None)
        if dimension is None:
            dimension = getattr(vector_column.type, "dimensions", None)
        if not isinstance(dimension, int) or dimension < 1:
            raise RegistrationError(
                f"pgvector table {table_name!r} did not expose vector dimension metadata"
            )
        primary = next(iter(table.primary_key.columns), None)
        if primary is None:
            primary = table.columns.get("id")
        if primary is None:
            raise RegistrationError(
                f"pgvector table {table_name!r} requires a primary key or id column"
            )
        metadata = tuple(
            VectorMetadataField(
                name=column.name,
                json_schema=self._schema_for_column(column),
                filterable=True,
            )
            for column in table.columns
            if column.name not in {vector_column.name, primary.name}
        )
        result = (table, vector_column, primary, metadata, dimension)
        self._cache[table_name] = result
        return result

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for name in self._table_names():
            table, vector_column, primary, metadata, dimension = self._reflect(name)
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=self._metrics.get(name, "cosine"),
                    metadata_fields=metadata,
                    public_metadata={
                        "schema": self._schema,
                        "table": table.name,
                        "vector_column": vector_column.name,
                        "primary_key": primary.name,
                    },
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
        if collection not in set(self._table_names()):
            raise RegistrationError(f"unknown pgvector table {collection!r}")
        table, vector_column, primary, metadata, _dimension = self._reflect(collection)
        allowed = {field.name for field in metadata if field.filterable}
        unknown = sorted(set(filters or {}) - allowed)
        if unknown:
            raise SchemaValidationError(
                "pgvector filter requested unknown metadata fields: " + ", ".join(unknown)
            )
        metric = self._metrics.get(collection, "cosine")
        method_name = {
            "cosine": "cosine_distance",
            "l2": "l2_distance",
            "euclidean": "l2_distance",
            "inner_product": "max_inner_product",
            "ip": "max_inner_product",
            "dot": "max_inner_product",
        }.get(metric)
        if method_name is None:
            raise RegistrationError(f"unsupported pgvector metric {metric!r}")
        distance_method = getattr(vector_column, method_name, None)
        if not callable(distance_method):
            raise RegistrationError(
                f"pgvector column {vector_column.name!r} does not expose {method_name}()"
            )
        score_expr = distance_method(list(vector)).label("_schemarouter_score")
        sa = self._sqlalchemy()
        selected_columns = [primary]
        for field in include_fields:
            if field in table.columns and field != primary.name:
                selected_columns.append(table.columns[field])
        statement = sa.select(*selected_columns, score_expr).order_by(score_expr).limit(top_k)
        for field, value in sorted((filters or {}).items()):
            column = table.columns[field]
            statement = statement.where(
                column.in_(list(value)) if isinstance(value, tuple) else column == value
            )
        with self._engine.connect() as connection:
            raw_rows = connection.execute(statement).mappings().all()
        rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            row: dict[str, Any] = {
                "id": raw[primary.name],
                "score": float(raw["_schemarouter_score"]),
            }
            row.update({field: raw[field] for field in include_fields if field in raw})
            rows.append(row)
        return rows


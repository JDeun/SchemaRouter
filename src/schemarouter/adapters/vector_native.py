from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
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

    supports_trusted_filters = True

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

    supports_trusted_filters = True

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
    """Thin adapter over a caller-owned Pinecone client."""

    supports_trusted_filters = True

    def __init__(
        self,
        client: Any,
        *,
        metadata_fields_by_index: Mapping[str, Sequence[VectorMetadataField]] | None = None,
    ) -> None:
        self._client = client
        self._metadata_fields_by_index = {
            name: tuple(fields)
            for name, fields in (metadata_fields_by_index or {}).items()
        }

    def _index_names(self) -> list[str]:
        raw = self._client.list_indexes()
        names_method = getattr(raw, "names", None)
        if callable(names_method):
            names = names_method()
        elif isinstance(raw, Mapping):
            names = raw.get("indexes", raw)
        else:
            names = raw
        if isinstance(names, Mapping):
            values = list(names.values())
        elif isinstance(names, Iterable) and not isinstance(names, (str, bytes)):
            values = list(names)
        else:
            raise SchemaValidationError(
                "Pinecone list_indexes() returned an unexpected response"
            )
        result = [str(_read(value, "name", value)) for value in values]
        if any(not value for value in result):
            raise SchemaValidationError("Pinecone returned an empty index name")
        return result

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for index_name in self._index_names():
            description = self._client.describe_index(index_name)
            dimension = _read(description, "dimension")
            if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
                raise SchemaValidationError(
                    f"Pinecone index {index_name!r} did not expose a valid dimension"
                )
            metric = _enum_text(_read(description, "metric"))
            results.append(
                VectorCollectionSpec(
                    name=index_name,
                    dimension=dimension,
                    metric=metric,
                    metadata_fields=self._metadata_fields_by_index.get(index_name, ()),
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
        index = self._client.Index(collection)
        kwargs: dict[str, Any] = {
            "vector": list(vector),
            "top_k": top_k,
            "include_values": False,
            "include_metadata": bool(include_fields),
        }
        if filters:
            kwargs["filter"] = dict(filters)
        raw = index.query(**kwargs)
        matches = _read(raw, "matches", raw)
        if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
            raise SchemaValidationError(
                "Pinecone query() returned an unexpected response"
            )
        rows: list[dict[str, Any]] = []
        for match in matches:
            metadata = _read(match, "metadata", {}) or {}
            if not isinstance(metadata, Mapping):
                raise SchemaValidationError("Pinecone match metadata must be an object")
            row: dict[str, Any] = {
                "id": _read(match, "id"),
                "score": float(_read(match, "score")),
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


class ChromaVectorBackend:
    """Thin adapter over a caller-owned Chroma client."""

    supports_trusted_filters = True

    def __init__(
        self,
        client: Any,
        *,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[VectorMetadataField]] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._dimension_by_collection = dict(dimension_by_collection or {})
        self._metadata_fields_by_collection = {
            name: tuple(fields)
            for name, fields in (metadata_fields_by_collection or {}).items()
        }
        self._metric_by_collection = dict(metric_by_collection or {})

    def _collection(self, name: str) -> Any:
        return self._client.get_collection(name=name)

    def _dimension(self, name: str, collection: Any) -> int:
        configured = self._dimension_by_collection.get(name)
        if configured is not None:
            if configured < 1:
                raise RegistrationError(
                    f"Chroma collection {name!r} has an invalid configured dimension"
                )
            return configured
        peek = collection.peek(limit=1)
        embeddings = _read(peek, "embeddings")
        if isinstance(peek, Mapping):
            embeddings = peek.get("embeddings")
        if (
            isinstance(embeddings, Sequence)
            and embeddings
            and isinstance(embeddings[0], Sequence)
            and not isinstance(embeddings[0], (str, bytes))
        ):
            dimension = len(embeddings[0])
            if dimension > 0:
                return dimension
        raise RegistrationError(
            f"Chroma collection {name!r} is empty or does not expose embeddings; "
            "set dimension_by_collection"
        )

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        raw = self._client.list_collections()
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise SchemaValidationError(
                "Chroma list_collections() returned an unexpected response"
            )
        results: list[VectorCollectionSpec] = []
        for entry in raw:
            name = str(_read(entry, "name", entry))
            collection = entry if hasattr(entry, "query") else self._collection(name)
            dimension = self._dimension(name, collection)
            metadata = _read(collection, "metadata", {}) or {}
            metric = self._metric_by_collection.get(
                name,
                str(metadata.get("hnsw:space", "unknown"))
                if isinstance(metadata, Mapping)
                else "unknown",
            )
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=metric,
                    metadata_fields=self._metadata_fields_by_collection.get(name, ()),
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
        target = self._collection(collection)
        include: list[str] = ["distances"]
        metadata_fields = tuple(
            field for field in include_fields if field != "document"
        )
        if metadata_fields:
            include.append("metadatas")
        if "document" in include_fields:
            include.append("documents")
        kwargs: dict[str, Any] = {
            "query_embeddings": [list(vector)],
            "n_results": top_k,
            "include": include,
        }
        if filters:
            kwargs["where"] = dict(filters)
        raw = target.query(**kwargs)
        if not isinstance(raw, Mapping):
            raise SchemaValidationError("Chroma query() must return an object")
        ids = (raw.get("ids") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0] if "metadatas" in include else []
        documents = (raw.get("documents") or [[]])[0] if "documents" in include else []
        rows: list[dict[str, Any]] = []
        for index, item_id in enumerate(ids):
            row: dict[str, Any] = {"id": item_id}
            if index < len(distances):
                row["score"] = float(distances[index])
            metadata = (
                metadatas[index]
                if index < len(metadatas) and isinstance(metadatas[index], Mapping)
                else {}
            )
            for field in metadata_fields:
                if field in metadata:
                    row[field] = metadata[field]
            if "document" in include_fields and index < len(documents):
                row["document"] = documents[index]
            rows.append(row)
        return rows


class WeaviateVectorBackend:
    """Thin adapter over a caller-owned Weaviate v4 client."""

    supports_trusted_filters = True

    def __init__(
        self,
        client: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        vector_name_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        self._client = client
        self._dimension_by_collection = dict(dimension_by_collection)
        self._vector_name_by_collection = dict(vector_name_by_collection or {})
        self._metric_by_collection = dict(metric_by_collection or {})
        self._filter_builder = filter_builder

    def _names(self) -> list[str]:
        raw = self._client.collections.list_all(simple=False)
        if isinstance(raw, Mapping):
            return [str(name) for name in raw]
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return [str(_read(value, "name", value)) for value in raw]
        raise SchemaValidationError(
            "Weaviate collections.list_all() returned an unexpected response"
        )

    @staticmethod
    def _property_schema(value: Any) -> dict[str, Any]:
        raw_type = _read(value, "data_type", _read(value, "dataType"))
        if isinstance(raw_type, Sequence) and not isinstance(raw_type, (str, bytes)):
            raw_type = raw_type[0] if raw_type else None
        return _json_schema_from_vendor_type(raw_type)

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        results: list[VectorCollectionSpec] = []
        for name in self._names():
            dimension = self._dimension_by_collection.get(name)
            if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
                raise RegistrationError(
                    f"Weaviate collection {name!r} requires dimension_by_collection"
                )
            collection = self._client.collections.get(name)
            config = collection.config.get()
            properties = _read(config, "properties", ()) or ()
            metadata: list[VectorMetadataField] = []
            for prop in properties:
                prop_name = str(_read(prop, "name", ""))
                if not prop_name or prop_name in {"id", "score"}:
                    continue
                metadata.append(
                    VectorMetadataField(
                        name=prop_name,
                        json_schema=self._property_schema(prop),
                        filterable=True,
                    )
                )
            results.append(
                VectorCollectionSpec(
                    name=name,
                    dimension=dimension,
                    metric=self._metric_by_collection.get(name, "unknown"),
                    metadata_fields=tuple(metadata),
                    public_metadata=(
                        {}
                        if name not in self._vector_name_by_collection
                        else {"vector_name": self._vector_name_by_collection[name]}
                    ),
                )
            )
        return tuple(results)

    def _filter(self, filters: Mapping[str, Any]) -> Any:
        if self._filter_builder is not None:
            return self._filter_builder(filters)
        try:
            module = importlib.import_module("weaviate.classes.query")
            filter_cls = module.Filter
        except (ImportError, AttributeError) as exc:
            raise RegistrationError(
                "Weaviate trusted metadata filtering requires weaviate-client "
                "or a filter_builder"
            ) from exc
        combined = None
        for field, value in sorted(filters.items()):
            current = (
                filter_cls.by_property(field).contains_any(list(value))
                if isinstance(value, tuple)
                else filter_cls.by_property(field).equal(value)
            )
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
        target = self._client.collections.get(collection)
        kwargs: dict[str, Any] = {
            "near_vector": list(vector),
            "limit": top_k,
            "return_properties": list(include_fields),
        }
        vector_name = self._vector_name_by_collection.get(collection)
        if vector_name is not None:
            kwargs["target_vector"] = vector_name
        if filters:
            kwargs["filters"] = self._filter(filters)
        response = target.query.near_vector(**kwargs)
        objects = _read(response, "objects", ())
        if not isinstance(objects, Sequence) or isinstance(objects, (str, bytes)):
            raise SchemaValidationError(
                "Weaviate near_vector() returned an unexpected response"
            )
        rows: list[dict[str, Any]] = []
        for obj in objects:
            props = _read(obj, "properties", {}) or {}
            metadata = _read(obj, "metadata")
            score_raw = _read(metadata, "distance", _read(metadata, "certainty"))
            row: dict[str, Any] = {"id": str(_read(obj, "uuid", _read(obj, "id")))}
            if score_raw is not None:
                row["score"] = float(score_raw)
            if isinstance(props, Mapping):
                row.update(
                    {
                        field: props[field]
                        for field in include_fields
                        if field in props
                    }
                )
            rows.append(row)
        return rows


class PgvectorVectorBackend:
    """SQLAlchemy/pgvector adapter over caller-owned PostgreSQL Engine."""

    supports_trusted_filters = True

    def __init__(
        self,
        engine: Any,
        *,
        tables: Sequence[str] | None = None,
        vector_field_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
        schema: str | None = None,
    ) -> None:
        self._engine = engine
        self._tables = None if tables is None else tuple(tables)
        self._vector_field_by_table = dict(vector_field_by_table or {})
        self._metric_by_table = dict(metric_by_table or {})
        self._schema = schema
        self._table_cache: dict[str, Any] = {}
        self._pk_by_table: dict[str, str] = {}

    def _sqlalchemy(self) -> tuple[Any, Any, Any]:
        try:
            from sqlalchemy import MetaData, Table, inspect
        except ImportError as exc:
            raise RegistrationError(
                "pgvector onboarding requires SQLAlchemy"
            ) from exc
        return MetaData, Table, inspect

    def _table(self, name: str) -> Any:
        cached = self._table_cache.get(name)
        if cached is not None:
            return cached
        MetaData, Table, _inspect = self._sqlalchemy()
        table = Table(
            name,
            MetaData(),
            schema=self._schema,
            autoload_with=self._engine,
        )
        self._table_cache[name] = table
        return table

    @staticmethod
    def _dimension(column: Any) -> int | None:
        dimension = _read(_read(column, "type"), "dim")
        if dimension is None:
            text = str(_read(column, "type", ""))
            match = re.search(r"VECTOR\((\d+)\)", text, flags=re.IGNORECASE)
            dimension = int(match.group(1)) if match else None
        return dimension if isinstance(dimension, int) and dimension > 0 else None

    def _contract(self, table_name: str) -> tuple[str, int, tuple[VectorMetadataField, ...]]:
        table = self._table(table_name)
        vector_columns = [
            (column.name, dimension)
            for column in table.columns
            if (dimension := self._dimension(column)) is not None
        ]
        configured = self._vector_field_by_table.get(table_name)
        if configured is not None:
            matches = [
                (name, dimension)
                for name, dimension in vector_columns
                if name == configured
            ]
            if not matches:
                raise RegistrationError(
                    f"pgvector table {table_name!r} has no vector column {configured!r}"
                )
            vector_field, dimension = matches[0]
        elif len(vector_columns) == 1:
            vector_field, dimension = vector_columns[0]
        elif not vector_columns:
            raise RegistrationError(
                f"pgvector table {table_name!r} has no VECTOR column"
            )
        else:
            raise RegistrationError(
                f"pgvector table {table_name!r} has multiple VECTOR columns; "
                "set vector_field_by_table"
            )

        pk_columns = [column.name for column in table.primary_key.columns]
        if not pk_columns:
            raise RegistrationError(
                f"pgvector table {table_name!r} requires a primary key"
            )
        self._pk_by_table[table_name] = pk_columns[0]
        metadata = tuple(
            VectorMetadataField(
                name=column.name,
                json_schema=_json_schema_from_vendor_type(_read(column, "type")),
                filterable=True,
            )
            for column in table.columns
            if column.name not in {vector_field, pk_columns[0]}
        )
        return vector_field, dimension, metadata

    def list_collections(self) -> tuple[VectorCollectionSpec, ...]:
        _metadata, _table, inspect = self._sqlalchemy()
        inspector = inspect(self._engine)
        table_names = (
            list(self._tables)
            if self._tables is not None
            else list(inspector.get_table_names(schema=self._schema))
        )
        results: list[VectorCollectionSpec] = []
        for table_name in table_names:
            vector_field, dimension, metadata = self._contract(table_name)
            results.append(
                VectorCollectionSpec(
                    name=table_name,
                    dimension=dimension,
                    metric=self._metric_by_table.get(table_name, "cosine"),
                    metadata_fields=metadata,
                    public_metadata={"vector_field": vector_field},
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
        try:
            from sqlalchemy import select
        except ImportError as exc:
            raise RegistrationError(
                "pgvector search requires SQLAlchemy"
            ) from exc
        table = self._table(collection)
        vector_field, _dimension, metadata = self._contract(collection)
        pk_name = self._pk_by_table[collection]
        allowed = {field.name for field in metadata if field.filterable}
        unknown = sorted(set(filters or ()) - allowed)
        if unknown:
            raise SchemaValidationError(
                "pgvector filter requested unknown metadata fields: "
                + ", ".join(unknown)
            )
        vector_column = table.c[vector_field]
        metric = self._metric_by_table.get(collection, "cosine").lower()
        method_name = {
            "cosine": "cosine_distance",
            "l2": "l2_distance",
            "euclidean": "l2_distance",
            "inner_product": "max_inner_product",
            "ip": "max_inner_product",
        }.get(metric)
        if method_name is None or not hasattr(vector_column, method_name):
            raise RegistrationError(
                f"pgvector metric {metric!r} is not supported by reflected column"
            )
        distance = getattr(vector_column, method_name)(list(vector)).label("__distance")
        selected_columns = [
            table.c[field]
            for field in include_fields
            if field in table.c and field not in {pk_name, vector_field}
        ]
        statement = select(
            table.c[pk_name].label("__id"),
            distance,
            *selected_columns,
        )
        for field, value in sorted((filters or {}).items()):
            column = table.c[field]
            if isinstance(value, tuple):
                statement = statement.where(column.in_(list(value)))
            else:
                statement = statement.where(column == value)
        statement = statement.order_by(distance).limit(top_k)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [
            {
                "id": row["__id"],
                "score": float(row["__distance"]),
                **{
                    field: row[field]
                    for field in include_fields
                    if field in row
                },
            }
            for row in rows
        ]

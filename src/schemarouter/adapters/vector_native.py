from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    ) -> None:
        self._client = client
        self._vector_name_by_collection = dict(vector_name_by_collection or {})
        self._metadata_fields_by_collection = {
            name: tuple(fields)
            for name, fields in (metadata_fields_by_collection or {}).items()
        }

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
            from qdrant_client import models
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
            kwargs["query_filter"] = self._qdrant_filter(filters)

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

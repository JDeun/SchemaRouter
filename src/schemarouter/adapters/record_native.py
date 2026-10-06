from __future__ import annotations

import datetime as dt
import json
import re
import time
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from ..errors import RegistrationError, SchemaValidationError
from .record_store import RecordFieldSpec, RecordSourceSpec


def _record_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    data = getattr(value, "data", None)
    if callable(data):
        result = data()
        if isinstance(result, Mapping):
            return result
    if hasattr(value, "items"):
        try:
            result = dict(value.items())
        except Exception as exc:  # pragma: no cover - vendor object defensive path
            raise SchemaValidationError("record result row is not mapping-like") from exc
        return result
    raise SchemaValidationError("record result row is not mapping-like")


def _json_schema_from_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer"}
    if isinstance(value, (float, Decimal)):
        return {"type": "number"}
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return {"type": "string"}
    if isinstance(value, bytes):
        return {"type": "string"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, Mapping):
        return {"type": "object"}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return {"type": "array"}
    if value.__class__.__name__ in {"ObjectId", "UUID"}:
        return {"type": "string"}
    return {}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_json_safe(item) for item in value)
    return str(value)


_SCHEMA_SAMPLE_ROW_LIMIT = 16
_SCHEMA_SAMPLE_BYTE_LIMIT = 256 * 1024
_SCHEMA_SAMPLE_TIME_LIMIT_SECONDS = 5.0
_COMPLEX_SAMPLE_TYPES = (Mapping, list, tuple, set, frozenset)


def _bounded_sample_documents(rows: Any) -> tuple[dict[str, Any], ...]:
    """Materialize a small, byte/time-bounded set of mapping-like sample documents."""

    started = time.monotonic()
    total_bytes = 0
    samples: list[dict[str, Any]] = []
    for raw in rows:
        if len(samples) >= _SCHEMA_SAMPLE_ROW_LIMIT:
            break
        if time.monotonic() - started >= _SCHEMA_SAMPLE_TIME_LIMIT_SECONDS:
            break
        if not isinstance(raw, Mapping):
            raise SchemaValidationError("sample document must be an object")
        sample = {str(name): value for name, value in raw.items()}
        encoded = json.dumps(
            _json_safe(sample),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > _SCHEMA_SAMPLE_BYTE_LIMIT - total_bytes:
            break
        total_bytes += len(encoded)
        samples.append(sample)
    return tuple(samples)


def _sample_field_names(
    samples: Sequence[Mapping[str, Any]],
    *,
    required: Sequence[str] = (),
) -> tuple[str, ...]:
    observed = {
        str(name)
        for sample in samples
        for name in sample
        if str(name)
    }
    ordered_required = tuple(dict.fromkeys(str(name) for name in required if str(name)))
    return ordered_required + tuple(sorted(observed - set(ordered_required)))


def _sample_field_is_scalar(
    samples: Sequence[Mapping[str, Any]],
    name: str,
) -> bool:
    values = [sample[name] for sample in samples if name in sample and sample[name] is not None]
    return bool(values) and all(not isinstance(value, _COMPLEX_SAMPLE_TYPES) for value in values)


def _sample_discovery_metadata(vendor: str) -> dict[str, Any]:
    return {
        "vendor": vendor,
        "schema_discovery": {
            "mode": "bounded_sample",
            "partial": True,
            "row_limit": _SCHEMA_SAMPLE_ROW_LIMIT,
            "byte_limit": _SCHEMA_SAMPLE_BYTE_LIMIT,
            "time_limit_seconds": _SCHEMA_SAMPLE_TIME_LIMIT_SECONDS,
            "sampled_field_types": "unconstrained",
        },
    }


class MongoRecordBackend:
    """Thin adapter over a caller-owned PyMongo Database-like object."""

    def __init__(
        self,
        database: Any,
        *,
        collections: Sequence[str] | None = None,
        text_search_collections: Sequence[str] = (),
        time_field_by_collection: Mapping[str, str] | None = None,
    ) -> None:
        self._database = database
        self._collections = None if collections is None else tuple(collections)
        self._text_search = set(text_search_collections)
        self._time_fields = dict(time_field_by_collection or {})

    def _names(self) -> tuple[str, ...]:
        if self._collections is not None:
            return self._collections
        names = self._database.list_collection_names()
        if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
            raise SchemaValidationError("MongoDB list_collection_names() must return a list")
        return tuple(str(name) for name in names if str(name))

    def _sample_documents(self, collection: Any) -> tuple[dict[str, Any], ...]:
        cursor = collection.find({})
        sort = getattr(cursor, "sort", None)
        if callable(sort):
            sort("_id", 1)
        max_time_ms = getattr(cursor, "max_time_ms", None)
        if callable(max_time_ms):
            max_time_ms(int(_SCHEMA_SAMPLE_TIME_LIMIT_SECONDS * 1000))
        cursor = cursor.limit(_SCHEMA_SAMPLE_ROW_LIMIT)
        return _bounded_sample_documents(cursor)

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for name in self._names():
            collection = self._database[name]
            samples = self._sample_documents(collection)
            required = ["_id"]
            time_field = self._time_fields.get(name)
            if time_field is not None:
                required.append(time_field)
            fields = [
                RecordFieldSpec(
                    name=field_name,
                    # MongoDB collections are schemaless unless an external validator is
                    # supplied. Sampled values prove presence, not a complete type contract.
                    json_schema={},
                    identifier=field_name == "_id",
                    filterable=(
                        field_name == "_id"
                        or _sample_field_is_scalar(samples, field_name)
                    ),
                )
                for field_name in _sample_field_names(samples, required=required)
            ]
            results.append(
                RecordSourceSpec(
                    name=name,
                    model="document",
                    fields=tuple(fields),
                    supports_text_search=name in self._text_search,
                    time_field=time_field,
                    public_metadata=_sample_discovery_metadata("mongodb"),
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if source not in set(self._names()):
            raise RegistrationError(f"unknown MongoDB collection {source!r}")
        query: dict[str, Any] = {
            field: (
                {"$in": list(value)}
                if isinstance(value, tuple)
                else value
            )
            for field, value in filters.items()
        }
        if text_query is not None:
            if source not in self._text_search:
                raise SchemaValidationError(
                    "MongoDB text search is not enabled for this collection"
                )
            query["$text"] = {"$search": text_query}

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None:
                raise SchemaValidationError(
                    "MongoDB time bounds are not enabled for this collection"
                )
            bounds: dict[str, Any] = {}
            if start_time is not None:
                bounds["$gte"] = start_time
            if end_time is not None:
                bounds["$lt"] = end_time
            query[time_field] = bounds

        projection = {field: 1 for field in include_fields}
        if "_id" not in include_fields:
            projection["_id"] = 0
        cursor = self._database[source].find(query, projection).limit(limit)
        return [
            {
                field: _json_safe(document[field])
                for field in include_fields
                if field in document
            }
            for document in cursor
        ]


_ELASTIC_TYPE_SCHEMAS: dict[str, dict[str, Any]] = {
    "boolean": {"type": "boolean"},
    "byte": {"type": "integer"},
    "short": {"type": "integer"},
    "integer": {"type": "integer"},
    "long": {"type": "integer"},
    "unsigned_long": {"type": "integer"},
    "half_float": {"type": "number"},
    "float": {"type": "number"},
    "double": {"type": "number"},
    "scaled_float": {"type": "number"},
    "keyword": {"type": "string"},
    "constant_keyword": {"type": "string"},
    "wildcard": {"type": "string"},
    "text": {"type": "string"},
    "date": {"type": "string"},
    "date_nanos": {"type": "string"},
    "ip": {"type": "string"},
    "object": {"type": "object"},
    "nested": {"type": "object"},
}


def _response_body(value: Any) -> Any:
    body = getattr(value, "body", None)
    return value if body is None else body


class ElasticRecordBackend:
    """Shared thin adapter for caller-owned Elasticsearch/OpenSearch clients."""

    def __init__(
        self,
        client: Any,
        *,
        indices: Sequence[str] | None = None,
        time_field_by_index: Mapping[str, str] | None = None,
        vendor: str = "elasticsearch",
    ) -> None:
        self._client = client
        self._indices = None if indices is None else tuple(indices)
        self._time_fields = dict(time_field_by_index or {})
        self._vendor = vendor
        self._text_fields: dict[str, tuple[str, ...]] = {}
        self._filterable_fields: dict[str, frozenset[str]] = {}

    def _mapping(self) -> Mapping[str, Any]:
        if self._indices is None:
            raw = self._client.indices.get_mapping()
        else:
            raw = self._client.indices.get_mapping(index=",".join(self._indices))
        raw = _response_body(raw)
        if not isinstance(raw, Mapping):
            raise SchemaValidationError(
                "Elasticsearch/OpenSearch get_mapping() must return an object"
            )
        return raw

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        mappings = self._mapping()
        results: list[RecordSourceSpec] = []
        for index_name, raw_index in sorted(mappings.items()):
            if self._indices is not None and index_name not in self._indices:
                continue
            if not isinstance(raw_index, Mapping):
                continue
            mapping = raw_index.get("mappings") or {}
            properties = mapping.get("properties") or {} if isinstance(mapping, Mapping) else {}
            if not isinstance(properties, Mapping):
                properties = {}

            fields = [
                RecordFieldSpec(
                    name="_id",
                    json_schema={"type": "string"},
                    identifier=True,
                    filterable=True,
                )
            ]
            text_fields: list[str] = []
            filterable: set[str] = {"_id"}
            for name, raw_field in sorted(properties.items()):
                raw_field = raw_field if isinstance(raw_field, Mapping) else {}
                field_type = str(raw_field.get("type") or "object")
                is_text = field_type in {"text", "search_as_you_type"}
                is_filterable = field_type not in {"text", "object", "nested"}
                if is_text:
                    text_fields.append(str(name))
                if is_filterable:
                    filterable.add(str(name))
                fields.append(
                    RecordFieldSpec(
                        name=str(name),
                        json_schema=dict(_ELASTIC_TYPE_SCHEMAS.get(field_type, {})),
                        filterable=is_filterable,
                    )
                )

            time_field = self._time_fields.get(str(index_name))
            if time_field is None and "@timestamp" in properties:
                time_field = "@timestamp"
            self._text_fields[str(index_name)] = tuple(text_fields)
            self._filterable_fields[str(index_name)] = frozenset(filterable)
            results.append(
                RecordSourceSpec(
                    name=str(index_name),
                    model="search",
                    fields=tuple(fields),
                    supports_text_search=bool(text_fields),
                    time_field=time_field,
                    public_metadata={"vendor": self._vendor},
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if source not in self._text_fields:
            self.list_sources()
        if source not in self._text_fields:
            raise RegistrationError(f"unknown Elasticsearch/OpenSearch index {source!r}")

        clauses: list[dict[str, Any]] = []
        if text_query is not None:
            text_fields = self._text_fields[source]
            if not text_fields:
                raise SchemaValidationError("text search is not enabled for this index")
            clauses.append({"multi_match": {"query": text_query, "fields": list(text_fields)}})

        filter_clauses: list[dict[str, Any]] = []
        allowed = self._filterable_fields[source]
        for field, value in sorted(filters.items()):
            if field not in allowed:
                raise SchemaValidationError(f"index filter field {field!r} is not filterable")
            filter_clauses.append(
                {"terms": {field: list(value)}}
                if isinstance(value, tuple)
                else {"term": {field: value}}
            )

        time_field = self._time_fields.get(source)
        if time_field is None:
            mapping = self._mapping().get(source, {})
            props = (
                mapping.get("mappings", {}).get("properties", {})
                if isinstance(mapping, Mapping)
                else {}
            )
            if "@timestamp" in props:
                time_field = "@timestamp"
        if start_time is not None or end_time is not None:
            if time_field is None:
                raise SchemaValidationError("time bounds are not enabled for this index")
            bounds: dict[str, str] = {}
            if start_time is not None:
                bounds["gte"] = start_time
            if end_time is not None:
                bounds["lt"] = end_time
            filter_clauses.append({"range": {time_field: bounds}})

        if clauses or filter_clauses:
            query: dict[str, Any] = {"bool": {}}
            if clauses:
                query["bool"]["must"] = clauses
            if filter_clauses:
                query["bool"]["filter"] = filter_clauses
        else:
            query = {"match_all": {}}

        source_fields = [field for field in include_fields if field != "_id"]
        try:
            raw = self._client.search(
                index=source,
                size=limit,
                query=query,
                source=source_fields,
            )
        except TypeError:
            raw = self._client.search(
                index=source,
                body={
                    "size": limit,
                    "query": query,
                    "_source": source_fields,
                },
            )
        raw = _response_body(raw)
        hits = raw.get("hits", {}).get("hits", []) if isinstance(raw, Mapping) else []
        if not isinstance(hits, Sequence):
            raise SchemaValidationError("search response hits must be a list")

        rows: list[dict[str, Any]] = []
        selected = set(include_fields)
        for hit in hits:
            if not isinstance(hit, Mapping):
                continue
            source_doc = hit.get("_source") or {}
            source_doc = source_doc if isinstance(source_doc, Mapping) else {}
            row: dict[str, Any] = {}
            if "_id" in selected:
                row["_id"] = str(hit.get("_id", ""))
            row.update(
                {
                    field: _json_safe(source_doc[field])
                    for field in include_fields
                    if field != "_id" and field in source_doc
                }
            )
            rows.append(row)
        return rows


def _ddb_decode(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    if "S" in value:
        return value["S"]
    if "N" in value:
        text = str(value["N"])
        return float(text) if any(token in text.lower() for token in (".", "e")) else int(text)
    if "BOOL" in value:
        return bool(value["BOOL"])
    if "NULL" in value:
        return None
    if "B" in value:
        return _json_safe(value["B"])
    if "SS" in value:
        return list(value["SS"])
    if "NS" in value:
        return [_ddb_decode({"N": item}) for item in value["NS"]]
    if "L" in value:
        return [_ddb_decode(item) for item in value["L"]]
    if "M" in value:
        return {str(key): _ddb_decode(item) for key, item in value["M"].items()}
    return {str(key): _ddb_decode(item) for key, item in value.items()}


def _ddb_encode(value: Any) -> dict[str, Any]:
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return {"N": str(value)}
    if isinstance(value, bytes):
        return {"B": value}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, Mapping):
        return {"M": {str(key): _ddb_encode(item) for key, item in value.items()}}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return {"L": [_ddb_encode(item) for item in value]}
    return {"S": str(value)}


class DynamoDBRecordBackend:
    """Thin adapter over a caller-owned low-level boto3 DynamoDB client."""

    def __init__(
        self,
        client: Any,
        *,
        tables: Sequence[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._tables = None if tables is None else tuple(tables)
        self._time_fields = dict(time_field_by_table or {})
        self._key_fields: dict[str, tuple[str, ...]] = {}
        self._field_names: dict[str, frozenset[str]] = {}

    def _table_names(self) -> tuple[str, ...]:
        if self._tables is not None:
            return self._tables
        names: list[str] = []
        start: str | None = None
        while True:
            kwargs = {} if start is None else {"ExclusiveStartTableName": start}
            response = self._client.list_tables(**kwargs)
            names.extend(str(value) for value in response.get("TableNames", ()))
            start = response.get("LastEvaluatedTableName")
            if not start:
                break
        return tuple(names)

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for table_name in self._table_names():
            description = self._client.describe_table(TableName=table_name).get("Table", {})
            key_fields = tuple(
                str(item["AttributeName"])
                for item in description.get("KeySchema", ())
                if isinstance(item, Mapping) and item.get("AttributeName")
            )
            sample_response = self._client.scan(
                TableName=table_name,
                Limit=_SCHEMA_SAMPLE_ROW_LIMIT,
            )
            sample_items = sample_response.get("Items", ())
            decoded_samples: list[dict[str, Any]] = []
            for sample in sample_items:
                if not isinstance(sample, Mapping):
                    raise SchemaValidationError("DynamoDB sample item must be an object")
                decoded_samples.append(
                    {
                        str(name): _ddb_decode(value)
                        for name, value in sample.items()
                    }
                )
            samples = _bounded_sample_documents(decoded_samples)

            attribute_types = {
                str(item.get("AttributeName")): str(item.get("AttributeType"))
                for item in description.get("AttributeDefinitions", ())
                if isinstance(item, Mapping) and item.get("AttributeName")
            }
            required = list(key_fields)
            time_field = self._time_fields.get(table_name)
            if time_field is not None:
                required.append(time_field)
            names = _sample_field_names(samples, required=required)

            fields = []
            for name in names:
                code = attribute_types.get(name)
                if code == "S":
                    schema = {"type": "string"}
                elif code == "N":
                    schema = {"type": "number"}
                elif code == "B":
                    schema = {"type": "string"}
                else:
                    schema = {}
                fields.append(
                    RecordFieldSpec(
                        name=name,
                        # AttributeDefinitions are authoritative for key/index attributes;
                        # all other sampled values remain intentionally unconstrained.
                        json_schema=dict(schema),
                        identifier=name in key_fields,
                        filterable=(
                            name in key_fields
                            or _sample_field_is_scalar(samples, name)
                        ),
                    )
                )
            self._key_fields[table_name] = key_fields
            self._field_names[table_name] = frozenset(names)
            results.append(
                RecordSourceSpec(
                    name=table_name,
                    model="document",
                    fields=tuple(fields),
                    time_field=time_field,
                    public_metadata=_sample_discovery_metadata("dynamodb"),
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if text_query is not None:
            raise SchemaValidationError("DynamoDB adapter does not expose free-text queries")
        if source not in self._field_names:
            self.list_sources()
        if source not in self._field_names:
            raise RegistrationError(f"unknown DynamoDB table {source!r}")

        expression_names: dict[str, str] = {}
        expression_values: dict[str, Any] = {}
        clauses: list[str] = []
        for index, (field, value) in enumerate(sorted(filters.items())):
            if field not in self._field_names[source]:
                raise SchemaValidationError(f"unknown DynamoDB filter field {field!r}")
            name_token = f"#f{index}"
            value_token = f":v{index}"
            expression_names[name_token] = field
            if isinstance(value, tuple):
                tokens: list[str] = []
                for member_index, member in enumerate(value):
                    member_token = f"{value_token}_{member_index}"
                    expression_values[member_token] = _ddb_encode(member)
                    tokens.append(member_token)
                if not tokens:
                    raise SchemaValidationError(
                        "DynamoDB membership filter cannot be empty"
                    )
                clauses.append(
                    f"{name_token} IN (" + ", ".join(tokens) + ")"
                )
            else:
                expression_values[value_token] = _ddb_encode(value)
                clauses.append(f"{name_token} = {value_token}")

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None:
                raise SchemaValidationError("DynamoDB time bounds are not enabled for this table")
            name_token = "#time"
            expression_names[name_token] = time_field
            if start_time is not None:
                expression_values[":start"] = _ddb_encode(start_time)
                clauses.append(f"{name_token} >= :start")
            if end_time is not None:
                expression_values[":end"] = _ddb_encode(end_time)
                clauses.append(f"{name_token} < :end")

        projection_names: dict[str, str] = {}
        projection_tokens: list[str] = []
        for index, field in enumerate(include_fields):
            token = f"#p{index}"
            projection_names[token] = field
            projection_tokens.append(token)
        kwargs: dict[str, Any] = {
            "TableName": source,
            "Limit": limit,
        }
        all_names = {**expression_names, **projection_names}
        if all_names:
            kwargs["ExpressionAttributeNames"] = all_names
        if expression_values:
            kwargs["ExpressionAttributeValues"] = expression_values
        if clauses:
            kwargs["FilterExpression"] = " AND ".join(clauses)
        if projection_tokens:
            kwargs["ProjectionExpression"] = ", ".join(projection_tokens)

        response = self._client.scan(**kwargs)
        items = response.get("Items", ())
        if not isinstance(items, Sequence):
            raise SchemaValidationError("DynamoDB scan Items must be a list")
        rows: list[dict[str, Any]] = []
        selected = set(include_fields)
        for item in items:
            if not isinstance(item, Mapping):
                continue
            decoded = {
                str(name): _ddb_decode(value)
                for name, value in item.items()
            }
            rows.append(
                {
                    field: _json_safe(decoded[field])
                    for field in include_fields
                    if field in decoded and field in selected
                }
            )
        return rows


def _cosmos_property(name: str) -> str:
    if not name or "\x00" in name:
        raise SchemaValidationError("Cosmos DB field name is unsafe")
    return "c[" + json.dumps(name, ensure_ascii=True) + "]"


class CosmosRecordBackend:
    """Thin adapter over a caller-owned synchronous Azure Cosmos DatabaseProxy."""

    def __init__(
        self,
        database: Any,
        *,
        containers: Sequence[str] | None = None,
        time_field_by_container: Mapping[str, str] | None = None,
    ) -> None:
        self._database = database
        self._containers = None if containers is None else tuple(containers)
        self._time_fields = dict(time_field_by_container or {})
        self._field_names: dict[str, frozenset[str]] = {}

    def _container_names(self) -> tuple[str, ...]:
        if self._containers is not None:
            return self._containers
        names: list[str] = []
        for raw in self._database.list_containers():
            if isinstance(raw, Mapping) and raw.get("id"):
                names.append(str(raw["id"]))
        return tuple(names)

    def _samples(self, container_name: str) -> tuple[dict[str, Any], ...]:
        container = self._database.get_container_client(container_name)
        rows = container.query_items(
            query=(
                f"SELECT TOP {_SCHEMA_SAMPLE_ROW_LIMIT} * FROM c "
                "ORDER BY c.id"
            ),
            enable_cross_partition_query=True,
        )
        return _bounded_sample_documents(rows)

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for container_name in self._container_names():
            samples = self._samples(container_name)
            required = ["id"]
            time_field = self._time_fields.get(container_name)
            if time_field is not None:
                required.append(time_field)
            names = _sample_field_names(samples, required=required)
            fields: list[RecordFieldSpec] = []
            for name in names:
                fields.append(
                    RecordFieldSpec(
                        name=name,
                        json_schema={"type": "string"} if name == "id" else {},
                        identifier=name == "id",
                        filterable=(
                            name == "id"
                            or _sample_field_is_scalar(samples, name)
                        ),
                    )
                )
            self._field_names[container_name] = frozenset(names)
            results.append(
                RecordSourceSpec(
                    name=container_name,
                    model="document",
                    fields=tuple(fields),
                    time_field=time_field,
                    public_metadata=_sample_discovery_metadata("azure-cosmos-db"),
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if text_query is not None:
            raise SchemaValidationError("Cosmos DB adapter does not expose free-text query text")
        if source not in self._field_names:
            self.list_sources()
        if source not in self._field_names:
            raise RegistrationError(f"unknown Cosmos DB container {source!r}")

        clauses: list[str] = []
        parameters: list[dict[str, Any]] = []
        parameter_index = 0
        for field, value in sorted(filters.items()):
            if field not in self._field_names[source]:
                raise SchemaValidationError(f"unknown Cosmos DB filter field {field!r}")
            prop = _cosmos_property(field)
            if isinstance(value, tuple):
                members: list[str] = []
                for member in value:
                    param_name = f"@p{parameter_index}"
                    parameter_index += 1
                    parameters.append({"name": param_name, "value": _json_safe(member)})
                    members.append(f"{prop} = {param_name}")
                if not members:
                    raise SchemaValidationError("Cosmos DB membership filter cannot be empty")
                clauses.append("(" + " OR ".join(members) + ")")
            else:
                param_name = f"@p{parameter_index}"
                parameter_index += 1
                parameters.append({"name": param_name, "value": _json_safe(value)})
                clauses.append(f"{prop} = {param_name}")

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None:
                raise SchemaValidationError(
                    "Cosmos DB time bounds are not enabled for this container"
                )
            prop = _cosmos_property(time_field)
            if start_time is not None:
                parameters.append({"name": "@start", "value": start_time})
                clauses.append(f"{prop} >= @start")
            if end_time is not None:
                parameters.append({"name": "@end", "value": end_time})
                clauses.append(f"{prop} < @end")

        parameters.append({"name": "@limit", "value": limit})
        statement = "SELECT * FROM c"
        if clauses:
            statement += " WHERE " + " AND ".join(clauses)
        statement += " OFFSET 0 LIMIT @limit"

        container = self._database.get_container_client(source)
        rows = container.query_items(
            query=statement,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        result: list[dict[str, Any]] = []
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise SchemaValidationError("Cosmos DB query item must be an object")
            result.append(
                {
                    field: _json_safe(raw[field])
                    for field in include_fields
                    if field in raw
                }
            )
            if len(result) >= limit:
                break
        return result


def _n1ql_identifier(value: str) -> str:
    if not value or "\x00" in value or "`" in value:
        raise SchemaValidationError("Couchbase identifier is unsafe")
    return f"`{value}`"


def _query_rows(result: Any) -> list[dict[str, Any]]:
    rows = result.rows() if hasattr(result, "rows") else result
    return [dict(_record_mapping(row)) for row in rows]


class CouchbaseRecordBackend:
    """Thin adapter over a caller-owned Couchbase Cluster."""

    def __init__(
        self,
        cluster: Any,
        *,
        keyspaces: Sequence[str] | None = None,
        time_field_by_source: Mapping[str, str] | None = None,
    ) -> None:
        self._cluster = cluster
        self._configured = None if keyspaces is None else tuple(keyspaces)
        self._time_fields = dict(time_field_by_source or {})
        self._paths: dict[str, tuple[str, str, str]] = {}
        self._field_names: dict[str, frozenset[str]] = {}

    def _discover_paths(self) -> dict[str, tuple[str, str, str]]:
        if self._configured is not None:
            paths: dict[str, tuple[str, str, str]] = {}
            for value in self._configured:
                parts = value.split(".")
                if len(parts) != 3:
                    raise RegistrationError(
                        "Couchbase keyspaces must use bucket.scope.collection"
                    )
                paths[value] = (parts[0], parts[1], parts[2])
            return paths

        result = self._cluster.query(
            "SELECT bucket, scope, name FROM system:keyspaces "
            "WHERE namespace = 'default' AND bucket IS NOT MISSING "
            "AND scope IS NOT MISSING ORDER BY bucket, scope, name"
        )
        paths = {}
        for row in _query_rows(result):
            bucket = str(row.get("bucket") or "")
            scope = str(row.get("scope") or "")
            name = str(row.get("name") or "")
            if not bucket or not scope or not name:
                continue
            source = f"{bucket}.{scope}.{name}"
            paths[source] = (bucket, scope, name)
        return paths

    @staticmethod
    def _keyspace(path: tuple[str, str, str]) -> str:
        return ".".join(_n1ql_identifier(value) for value in path)

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        self._paths = self._discover_paths()
        results: list[RecordSourceSpec] = []
        for source, path in sorted(self._paths.items()):
            statement = (
                f"SELECT RAW c FROM {self._keyspace(path)} AS c "
                f"ORDER BY META(c).id LIMIT {_SCHEMA_SAMPLE_ROW_LIMIT}"
            )
            samples = _bounded_sample_documents(
                _query_rows(self._cluster.query(statement))
            )
            names = _sample_field_names(samples)
            fields = []
            for name in names:
                safe_filter = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None
                fields.append(
                    RecordFieldSpec(
                        name=name,
                        json_schema={},
                        identifier=name == "id",
                        filterable=(
                            safe_filter
                            and (
                                name == "id"
                                or _sample_field_is_scalar(samples, name)
                            )
                        ),
                    )
                )
            if not fields:
                fields.append(
                    RecordFieldSpec(
                        name="id",
                        json_schema={"type": "string"},
                        identifier=True,
                        filterable=True,
                    )
                )
            self._field_names[source] = frozenset(field.name for field in fields)
            results.append(
                RecordSourceSpec(
                    name=source,
                    model="document",
                    fields=tuple(fields),
                    time_field=self._time_fields.get(source),
                    public_metadata=_sample_discovery_metadata("couchbase"),
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if text_query is not None:
            raise SchemaValidationError(
                "Couchbase native adapter does not expose raw/full-text query text"
            )
        if source not in self._paths:
            self.list_sources()
        path = self._paths.get(source)
        if path is None:
            raise RegistrationError(f"unknown Couchbase keyspace {source!r}")

        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        for index, (field, value) in enumerate(sorted(filters.items())):
            if field not in self._field_names[source]:
                raise SchemaValidationError(f"unknown Couchbase filter field {field!r}")
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) is None:
                raise SchemaValidationError("Couchbase filter field is not safely addressable")
            identifier = _n1ql_identifier(field)
            param_name = f"p{index}"
            if isinstance(value, tuple):
                params[param_name] = list(value)
                clauses.append(f"c.{identifier} IN $" + param_name)
            else:
                params[param_name] = _json_safe(value)
                clauses.append(f"c.{identifier} = $" + param_name)

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", time_field) is None:
                raise SchemaValidationError(
                    "Couchbase time bounds are not enabled for this keyspace"
                )
            identifier = _n1ql_identifier(time_field)
            if start_time is not None:
                params["start"] = start_time
                clauses.append(f"c.{identifier} >= $start")
            if end_time is not None:
                params["end"] = end_time
                clauses.append(f"c.{identifier} < $end")

        statement = f"SELECT RAW c FROM {self._keyspace(path)} AS c"
        if clauses:
            statement += " WHERE " + " AND ".join(clauses)
        statement += " LIMIT $limit"
        rows = _query_rows(self._cluster.query(statement, **params))
        return [
            {
                field: _json_safe(row[field])
                for field in include_fields
                if field in row
            }
            for row in rows[:limit]
        ]


def _clickhouse_identifier(value: str) -> str:
    if not value or "\x00" in value or "`" in value:
        raise SchemaValidationError("ClickHouse identifier is unsafe")
    return f"`{value}`"


def _clickhouse_type_schema(value: str) -> dict[str, Any]:
    normalized = value.strip()
    while normalized.startswith("Nullable(") and normalized.endswith(")"):
        normalized = normalized[9:-1]
    upper = normalized.upper()
    if upper.startswith(("UINT", "INT")):
        return {"type": "integer"}
    if upper.startswith(("FLOAT", "DECIMAL")):
        return {"type": "number"}
    if upper.startswith(("DATE", "DATETIME")):
        return {"type": "string"}
    if upper.startswith(("STRING", "FIXEDSTRING", "UUID", "ENUM", "LOWCARDINALITY")):
        return {"type": "string"}
    if upper.startswith("BOOL"):
        return {"type": "boolean"}
    if upper.startswith(("ARRAY", "TUPLE")):
        return {"type": "array"}
    if upper.startswith(("MAP", "JSON", "OBJECT")):
        return {"type": "object"}
    return {}


def _safe_clickhouse_type(value: str) -> str:
    if not value or re.fullmatch(r"[A-Za-z0-9_(),.' ]+", value) is None:
        raise SchemaValidationError("ClickHouse column type is unsafe for parameter binding")
    return value


class ClickHouseRecordBackend:
    """Thin adapter over a caller-owned clickhouse-connect Client."""

    def __init__(
        self,
        client: Any,
        *,
        tables: Sequence[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._configured = None if tables is None else tuple(tables)
        self._time_fields = dict(time_field_by_table or {})
        self._fields: dict[str, dict[str, str]] = {}

    @staticmethod
    def _rows(result: Any) -> list[tuple[Any, ...]]:
        rows = getattr(result, "result_set", None)
        if rows is None:
            raise SchemaValidationError("ClickHouse query result has no result_set")
        return [tuple(row) for row in rows]

    def _table_names(self) -> tuple[str, ...]:
        if self._configured is not None:
            return self._configured
        result = self._client.query(
            "SELECT database, name FROM system.tables "
            "WHERE is_temporary = 0 AND database NOT IN "
            "('system', 'INFORMATION_SCHEMA', 'information_schema') "
            "ORDER BY database, name"
        )
        return tuple(
            f"{str(database)}.{str(name)}"
            for database, name in self._rows(result)
        )

    @staticmethod
    def _split_table(value: str) -> tuple[str, str]:
        parts = value.split(".", 1)
        if len(parts) != 2 or not all(parts):
            raise RegistrationError("ClickHouse tables must use database.table")
        return parts[0], parts[1]

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for source in self._table_names():
            database, table = self._split_table(source)
            describe = self._client.query(
                f"DESCRIBE TABLE {_clickhouse_identifier(database)}."
                f"{_clickhouse_identifier(table)}"
            )
            fields: list[RecordFieldSpec] = []
            types: dict[str, str] = {}
            for row in self._rows(describe):
                if len(row) < 2:
                    continue
                name = str(row[0])
                ch_type = str(row[1])
                types[name] = ch_type
                schema = _clickhouse_type_schema(ch_type)
                scalar = schema.get("type") not in {"array", "object"}
                fields.append(
                    RecordFieldSpec(
                        name=name,
                        json_schema=schema,
                        filterable=scalar,
                    )
                )
            if not fields:
                continue
            self._fields[source] = types
            results.append(
                RecordSourceSpec(
                    name=source,
                    model=("time_series" if source in self._time_fields else "document"),
                    fields=tuple(fields),
                    time_field=self._time_fields.get(source),
                    public_metadata={"vendor": "clickhouse"},
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if text_query is not None:
            raise SchemaValidationError("ClickHouse adapter does not expose free-text SQL")
        if source not in self._fields:
            self.list_sources()
        types = self._fields.get(source)
        if types is None:
            raise RegistrationError(f"unknown ClickHouse table {source!r}")
        database, table = self._split_table(source)

        selected = list(include_fields) or list(types)
        unknown_fields = sorted(set(selected) - set(types))
        if unknown_fields:
            raise SchemaValidationError(
                "ClickHouse projection requested unknown fields: "
                + ", ".join(unknown_fields)
            )

        params: dict[str, Any] = {"limit": limit}
        clauses: list[str] = []
        for index, (field, value) in enumerate(sorted(filters.items())):
            if field not in types:
                raise SchemaValidationError(f"unknown ClickHouse filter field {field!r}")
            identifier = _clickhouse_identifier(field)
            ch_type = _safe_clickhouse_type(types[field])
            if isinstance(value, tuple):
                names: list[str] = []
                for member_index, member in enumerate(value):
                    param_name = f"p{index}_{member_index}"
                    params[param_name] = member
                    names.append(f"{{{param_name}:{ch_type}}}")
                if not names:
                    raise SchemaValidationError("ClickHouse membership filter cannot be empty")
                clauses.append(f"{identifier} IN (" + ", ".join(names) + ")")
            else:
                param_name = f"p{index}"
                params[param_name] = value
                clauses.append(f"{identifier} = {{{param_name}:{ch_type}}}")

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None or time_field not in types:
                raise SchemaValidationError("ClickHouse time bounds are not enabled for this table")
            identifier = _clickhouse_identifier(time_field)
            ch_type = _safe_clickhouse_type(types[time_field])
            if start_time is not None:
                params["start"] = start_time
                clauses.append(f"{identifier} >= {{start:{ch_type}}}")
            if end_time is not None:
                params["end"] = end_time
                clauses.append(f"{identifier} < {{end:{ch_type}}}")

        projection = ", ".join(_clickhouse_identifier(field) for field in selected)
        statement = (
            f"SELECT {projection} FROM {_clickhouse_identifier(database)}."
            f"{_clickhouse_identifier(table)}"
        )
        if clauses:
            statement += " WHERE " + " AND ".join(clauses)
        statement += " LIMIT {limit:UInt64}"

        result = self._client.query(statement, parameters=params)
        rows = self._rows(result)
        return [
            {
                field: _json_safe(value)
                for field, value in zip(selected, row, strict=True)
            }
            for row in rows[:limit]
        ]


def _flux_string(value: str) -> str:
    if "\x00" in value:
        raise SchemaValidationError("InfluxDB string contains a null byte")
    return json.dumps(value, ensure_ascii=True)


def _flux_identifier_access(field: str) -> str:
    return "r[" + _flux_string(field) + "]"


class InfluxRecordBackend:
    """Thin adapter over a caller-owned InfluxDB 2.x QueryApi."""

    def __init__(
        self,
        query_api: Any,
        *,
        bucket: str,
        org: str,
        measurements: Sequence[str] | None = None,
        default_start: str = "-30d",
    ) -> None:
        if not bucket.strip() or not org.strip():
            raise ValueError("InfluxDB bucket and org must be non-empty")
        if re.fullmatch(r"-[1-9][0-9]*[smhdw]", default_start) is None:
            raise ValueError("InfluxDB default_start must be a negative Flux duration")
        self._query_api = query_api
        self._bucket = bucket
        self._org = org
        self._configured = None if measurements is None else tuple(measurements)
        self._default_start = default_start
        self._tag_fields: dict[str, frozenset[str]] = {}
        self._field_keys: dict[str, frozenset[str]] = {}

    def _query(self, flux: str) -> list[Any]:
        raw = self._query_api.query(org=self._org, query=flux)
        return list(raw)

    @staticmethod
    def _record_values(tables: Sequence[Any]) -> list[Any]:
        values: list[Any] = []
        for table in tables:
            for record in getattr(table, "records", ()):
                values.append(record)
        return values

    def _schema_values(self, flux: str) -> tuple[str, ...]:
        records = self._record_values(self._query(flux))
        result: list[str] = []
        for record in records:
            value = record.get_value()
            if value is not None:
                result.append(str(value))
        return tuple(result)

    def _measurement_names(self) -> tuple[str, ...]:
        if self._configured is not None:
            return self._configured
        return self._schema_values(
            'import "influxdata/influxdb/schema"\n'
            f"schema.measurements(bucket: {_flux_string(self._bucket)})"
        )

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for measurement in self._measurement_names():
            predicate = "fn: (r) => r._measurement == " + _flux_string(measurement)
            fields = self._schema_values(
                'import "influxdata/influxdb/schema"\n'
                "schema.fieldKeys("
                f"bucket: {_flux_string(self._bucket)}, predicate: {predicate})"
            )
            tags = self._schema_values(
                'import "influxdata/influxdb/schema"\n'
                "schema.tagKeys("
                f"bucket: {_flux_string(self._bucket)}, predicate: {predicate})"
            )
            tag_set = frozenset(value for value in tags if not value.startswith("_"))
            self._tag_fields[measurement] = tag_set
            self._field_keys[measurement] = frozenset(fields)
            output_fields = [
                RecordFieldSpec(name="timestamp", json_schema={"type": "string"}),
                RecordFieldSpec(
                    name="field",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
                RecordFieldSpec(name="value", json_schema={}),
                *[
                    RecordFieldSpec(
                        name=tag,
                        json_schema={"type": "string"},
                        filterable=True,
                    )
                    for tag in sorted(tag_set)
                ],
            ]
            results.append(
                RecordSourceSpec(
                    name=measurement,
                    model="time_series",
                    fields=tuple(output_fields),
                    time_field="timestamp",
                    public_metadata={
                        "vendor": "influxdb",
                        "bucket": self._bucket,
                        "field_keys": sorted(fields),
                    },
                )
            )
        return tuple(results)

    def query(
        self,
        *,
        source: str,
        text_query: str | None,
        filters: dict[str, Any],
        start_time: str | None,
        end_time: str | None,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if text_query is not None:
            raise SchemaValidationError("InfluxDB adapter does not expose free-text Flux")
        if source not in self._tag_fields:
            self.list_sources()
        tags = self._tag_fields.get(source)
        field_keys = self._field_keys.get(source)
        if tags is None or field_keys is None:
            raise RegistrationError(f"unknown InfluxDB measurement {source!r}")

        start_expr = (
            f"time(v: {_flux_string(start_time)})"
            if start_time is not None
            else self._default_start
        )
        range_args = f"start: {start_expr}"
        if end_time is not None:
            range_args += f", stop: time(v: {_flux_string(end_time)})"

        predicates = [f"r._measurement == {_flux_string(source)}"]
        for field, value in sorted(filters.items()):
            if field == "field":
                values = value if isinstance(value, tuple) else (value,)
                unknown = sorted(set(str(item) for item in values) - field_keys)
                if unknown:
                    raise SchemaValidationError(
                        "InfluxDB filter requested unknown field keys: "
                        + ", ".join(unknown)
                    )
                predicates.append(
                    "("
                    + " or ".join(
                        f"r._field == {_flux_string(str(item))}"
                        for item in values
                    )
                    + ")"
                )
            elif field in tags:
                values = value if isinstance(value, tuple) else (value,)
                predicates.append(
                    "("
                    + " or ".join(
                        f"{_flux_identifier_access(field)} == {_flux_string(str(item))}"
                        for item in values
                    )
                    + ")"
                )
            else:
                raise SchemaValidationError(
                    f"InfluxDB filter field {field!r} is not a discovered tag/field"
                )

        predicate = " and ".join(predicates)
        flux = (
            f"from(bucket: {_flux_string(self._bucket)})\n"
            f"  |> range({range_args})\n"
            f"  |> filter(fn: (r) => {predicate})\n"
            f"  |> limit(n: {int(limit)})"
        )
        records = self._record_values(self._query(flux))
        rows: list[dict[str, Any]] = []
        for record in records[:limit]:
            values = getattr(record, "values", {}) or {}
            row = {
                "timestamp": _json_safe(record.get_time()),
                "field": str(record.get_field()),
                "value": _json_safe(record.get_value()),
            }
            for tag in tags:
                if tag in values:
                    row[tag] = _json_safe(values[tag])
            rows.append(
                {
                    field: row[field]
                    for field in include_fields
                    if field in row
                }
            )
        return rows

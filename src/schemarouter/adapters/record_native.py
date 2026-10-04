from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from ..errors import RegistrationError, SchemaValidationError
from .record_store import RecordFieldSpec, RecordSourceSpec


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

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        results: list[RecordSourceSpec] = []
        for name in self._names():
            collection = self._database[name]
            sample = collection.find_one({}) or {}
            if not isinstance(sample, Mapping):
                raise SchemaValidationError(
                    f"MongoDB collection {name!r} sample document must be an object"
                )
            keys = list(sample)
            if "_id" not in keys:
                keys.insert(0, "_id")
            fields = []
            for field_name in keys:
                value = sample.get(field_name)
                scalar = not isinstance(value, (Mapping, list, tuple, set, frozenset))
                fields.append(
                    RecordFieldSpec(
                        name=str(field_name),
                        json_schema=_json_schema_from_value(value),
                        identifier=field_name == "_id",
                        filterable=field_name == "_id" or scalar,
                    )
                )
            results.append(
                RecordSourceSpec(
                    name=name,
                    model="document",
                    fields=tuple(fields),
                    supports_text_search=name in self._text_search,
                    time_field=self._time_fields.get(name),
                    public_metadata={"vendor": "mongodb"},
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
                raise SchemaValidationError("MongoDB text search is not enabled for this collection")
            query["$text"] = {"$search": text_query}

        time_field = self._time_fields.get(source)
        if start_time is not None or end_time is not None:
            if time_field is None:
                raise SchemaValidationError("MongoDB time bounds are not enabled for this collection")
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
            raise SchemaValidationError("Elasticsearch/OpenSearch get_mapping() must return an object")
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
                (
                    {"terms": {field: list(value)}}
                    if isinstance(value, tuple)
                    else {"term": {field: value}}
                )
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


class RedisRecordBackend:
    """Bounded key-value adapter over a caller-owned redis-py client."""

    def __init__(
        self,
        client: Any,
        *,
        source_name: str = "keys",
        pattern: str = "*",
    ) -> None:
        self._client = client
        self._source_name = source_name
        self._pattern = pattern

    def list_sources(self) -> tuple[RecordSourceSpec, ...]:
        return (
            RecordSourceSpec(
                name=self._source_name,
                model="key_value",
                fields=(
                    RecordFieldSpec(
                        name="key",
                        json_schema={"type": "string"},
                        identifier=True,
                        filterable=True,
                    ),
                    RecordFieldSpec(name="type", json_schema={"type": "string"}),
                    RecordFieldSpec(name="value", json_schema={}),
                ),
                public_metadata={"vendor": "redis", "pattern": self._pattern},
            ),
        )

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _read_value(self, key: Any, kind: str) -> Any:
        if kind == "string":
            return _json_safe(self._client.get(key))
        if kind == "hash":
            raw = self._client.hgetall(key)
            return {
                self._text(field): _json_safe(value)
                for field, value in raw.items()
            }
        if kind == "list":
            return [_json_safe(value) for value in self._client.lrange(key, 0, -1)]
        if kind == "set":
            return sorted(_json_safe(value) for value in self._client.smembers(key))
        if kind == "zset":
            return [
                [_json_safe(value), float(score)]
                for value, score in self._client.zrange(key, 0, -1, withscores=True)
            ]
        return None

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
        if source != self._source_name:
            raise RegistrationError(f"unknown Redis source {source!r}")
        if text_query is not None or start_time is not None or end_time is not None:
            raise SchemaValidationError("Redis key-value adapter does not expose text/time queries")

        if "key" in filters:
            requested = filters["key"]
            raw_keys = (
                list(requested)
                if isinstance(requested, tuple)
                else [requested]
            )
        else:
            raw_keys = []
            for key in self._client.scan_iter(match=self._pattern, count=min(limit, 1000)):
                raw_keys.append(key)
                if len(raw_keys) >= limit:
                    break

        rows: list[dict[str, Any]] = []
        selected = set(include_fields)
        for raw_key in raw_keys[:limit]:
            key = self._text(raw_key)
            kind = self._text(self._client.type(raw_key))
            row = {
                "key": key,
                "type": kind,
                "value": self._read_value(raw_key, kind),
            }
            rows.append({field: row[field] for field in include_fields if field in row and field in selected})
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
            sample_response = self._client.scan(TableName=table_name, Limit=1)
            sample_items = sample_response.get("Items", ())
            sample = sample_items[0] if sample_items else {}
            decoded_sample = {
                str(name): _ddb_decode(value)
                for name, value in sample.items()
            } if isinstance(sample, Mapping) else {}

            attribute_types = {
                str(item.get("AttributeName")): str(item.get("AttributeType"))
                for item in description.get("AttributeDefinitions", ())
                if isinstance(item, Mapping) and item.get("AttributeName")
            }
            names = list(decoded_sample)
            for key in key_fields:
                if key not in names:
                    names.insert(0, key)

            fields = []
            for name in names:
                value = decoded_sample.get(name)
                if value is None and name in attribute_types:
                    code = attribute_types[name]
                    schema = {"S": {"type": "string"}, "N": {"type": "number"}, "B": {"type": "string"}}.get(code, {})
                else:
                    schema = _json_schema_from_value(value)
                scalar = not isinstance(value, (Mapping, list, tuple, set, frozenset))
                fields.append(
                    RecordFieldSpec(
                        name=name,
                        json_schema=dict(schema),
                        identifier=name in key_fields,
                        filterable=name in key_fields or scalar,
                    )
                )
            self._key_fields[table_name] = key_fields
            self._field_names[table_name] = frozenset(names)
            results.append(
                RecordSourceSpec(
                    name=table_name,
                    model="document",
                    fields=tuple(fields),
                    time_field=self._time_fields.get(table_name),
                    public_metadata={"vendor": "dynamodb"},
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

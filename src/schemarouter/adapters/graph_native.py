from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from ..errors import RegistrationError, SchemaValidationError
from .graph_store import (
    GraphNodeTypeSpec,
    GraphRelationshipTypeSpec,
    GraphSourceSpec,
)

_MAX_SCHEMA_ITEMS = 1000


def _as_mapping(value: Any) -> Mapping[str, Any]:
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
            raise SchemaValidationError("graph result row is not mapping-like") from exc
        return result
    raise SchemaValidationError("graph result row is not mapping-like")


def _cypher_identifier(value: str) -> str:
    if not value or "\x00" in value or "`" in value:
        raise SchemaValidationError("graph relationship type has an unsafe identifier")
    return f"`{value}`"


def _absolute_iri(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or any(token in value for token in ("<", ">", "\x00", "\n", "\r")):
        raise SchemaValidationError("SPARQL traversal requires an absolute safe IRI")
    return f"<{value}>"


def _normalize_neo4j_result(result: Any) -> list[dict[str, Any]]:
    records = getattr(result, "records", None)
    if records is None and isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
        if len(result) >= 1 and isinstance(result[0], Sequence):
            records = result[0]
        else:
            records = result
    if records is None:
        raise SchemaValidationError("Neo4j execute_query() returned an unexpected result")
    return [dict(_as_mapping(record)) for record in records]


def _json_payload_rows(payload: Any) -> list[dict[str, Any]]:
    if hasattr(payload, "read"):
        payload = payload.read()
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, Mapping):
        if "results" in payload:
            payload = payload["results"]
        else:
            payload = [payload]
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise SchemaValidationError("graph query response must contain a list of rows")
    return [dict(_as_mapping(row)) for row in payload]


class Neo4jGraphBackend:
    """Thin adapter over a caller-owned Neo4j Python driver."""

    def __init__(
        self,
        driver: Any,
        *,
        database: str,
        graph_name: str | None = None,
    ) -> None:
        if not database.strip():
            raise ValueError("Neo4j database must be non-empty")
        self._driver = driver
        self._database = database
        self._graph_name = graph_name or database
        self._relationships: tuple[str, ...] | None = None

    def _execute(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"database_": self._database}
        if parameters:
            kwargs["parameters_"] = dict(parameters)
        return _normalize_neo4j_result(self._driver.execute_query(query, **kwargs))

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        label_rows = self._execute(
            "CALL db.labels() YIELD label RETURN label ORDER BY label"
        )
        relationship_rows = self._execute(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN relationshipType ORDER BY relationshipType"
        )
        labels = tuple(
            str(row["label"])
            for row in label_rows[:_MAX_SCHEMA_ITEMS]
            if row.get("label")
        )
        relationships = tuple(
            str(row["relationshipType"])
            for row in relationship_rows[:_MAX_SCHEMA_ITEMS]
            if row.get("relationshipType")
        )
        self._relationships = relationships
        return (
            GraphSourceSpec(
                name=self._graph_name,
                model="property_graph",
                node_types=tuple(GraphNodeTypeSpec(name=label) for label in labels),
                relationship_types=tuple(
                    GraphRelationshipTypeSpec(name=name)
                    for name in relationships
                ),
                public_metadata={
                    "vendor": "neo4j",
                    "database": self._database,
                },
            ),
        )

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if graph != self._graph_name:
            raise RegistrationError(f"unknown Neo4j graph {graph!r}")
        known = self._relationships
        if known is None:
            self.list_graphs()
            known = self._relationships or ()
        unknown = sorted(set(relationship_types) - set(known))
        if unknown:
            raise SchemaValidationError(
                "Neo4j traversal requested unknown relationship types: "
                + ", ".join(unknown)
            )
        if not relationship_types:
            return []

        rel_expr = "|".join(_cypher_identifier(value) for value in relationship_types)
        if direction == "out":
            pattern = f"(start)-[rels:{rel_expr}*1..{max_hops}]->(target)"
        elif direction == "in":
            pattern = f"(start)<-[rels:{rel_expr}*1..{max_hops}]-(target)"
        elif direction == "both":
            pattern = f"(start)-[rels:{rel_expr}*1..{max_hops}]-(target)"
        else:
            raise SchemaValidationError("Neo4j traversal direction is invalid")

        query = (
            f"MATCH p={pattern} "
            "WHERE elementId(start) = $start_id "
            "RETURN elementId(start) AS source_id, "
            "elementId(target) AS target_id, "
            "type(last(rels)) AS relationship, "
            "size(rels) AS depth, "
            "coalesce(head(labels(start)), '') AS source_type, "
            "coalesce(head(labels(target)), '') AS target_type "
            "LIMIT $limit"
        )
        rows = self._execute(
            query,
            {"start_id": start_id, "limit": limit},
        )
        selected = set(include_fields)
        return [
            {key: value for key, value in row.items() if key in selected}
            for row in rows
        ]


class NeptuneOpenCypherBackend:
    """Thin adapter for caller-owned Neptune Database or Neptune Analytics clients."""

    def __init__(
        self,
        client: Any,
        *,
        graph_name: str = "neptune",
        graph_identifier: str | None = None,
    ) -> None:
        if not graph_name.strip():
            raise ValueError("Neptune graph_name must be non-empty")
        self._client = client
        self._graph_name = graph_name
        self._graph_identifier = graph_identifier
        self._relationships: tuple[str, ...] | None = None

    def _execute(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params = dict(parameters or {})
        if self._graph_identifier is not None and hasattr(self._client, "execute_query"):
            response = self._client.execute_query(
                graphIdentifier=self._graph_identifier,
                queryString=query,
                language="OPEN_CYPHER",
                parameters=params,
            )
            return _json_payload_rows(response.get("payload"))

        if hasattr(self._client, "execute_open_cypher_query"):
            kwargs: dict[str, Any] = {"openCypherQuery": query}
            if params:
                kwargs["parameters"] = json.dumps(
                    params,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            response = self._client.execute_open_cypher_query(**kwargs)
            return _json_payload_rows(response.get("results"))

        raise RegistrationError(
            "Neptune client must expose execute_open_cypher_query() or "
            "execute_query() with graph_identifier"
        )

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        label_rows = self._execute(
            "MATCH (n) UNWIND labels(n) AS label "
            "RETURN DISTINCT label AS label ORDER BY label LIMIT 1000"
        )
        relationship_rows = self._execute(
            "MATCH ()-[r]->() RETURN DISTINCT type(r) AS relationshipType "
            "ORDER BY relationshipType LIMIT 1000"
        )
        labels = tuple(
            str(row["label"]) for row in label_rows if row.get("label")
        )
        relationships = tuple(
            str(row["relationshipType"])
            for row in relationship_rows
            if row.get("relationshipType")
        )
        self._relationships = relationships
        return (
            GraphSourceSpec(
                name=self._graph_name,
                model="property_graph",
                node_types=tuple(GraphNodeTypeSpec(name=label) for label in labels),
                relationship_types=tuple(
                    GraphRelationshipTypeSpec(name=name)
                    for name in relationships
                ),
                public_metadata={
                    "vendor": "amazon-neptune",
                    "api": (
                        "neptune-graph"
                        if self._graph_identifier is not None
                        else "neptunedata"
                    ),
                },
            ),
        )

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if graph != self._graph_name:
            raise RegistrationError(f"unknown Neptune graph {graph!r}")
        known = self._relationships
        if known is None:
            self.list_graphs()
            known = self._relationships or ()
        unknown = sorted(set(relationship_types) - set(known))
        if unknown:
            raise SchemaValidationError(
                "Neptune traversal requested unknown relationship types: "
                + ", ".join(unknown)
            )
        if not relationship_types:
            return []

        rel_expr = "|".join(_cypher_identifier(value) for value in relationship_types)
        if direction == "out":
            pattern = f"(start)-[rels:{rel_expr}*1..{max_hops}]->(target)"
        elif direction == "in":
            pattern = f"(start)<-[rels:{rel_expr}*1..{max_hops}]-(target)"
        elif direction == "both":
            pattern = f"(start)-[rels:{rel_expr}*1..{max_hops}]-(target)"
        else:
            raise SchemaValidationError("Neptune traversal direction is invalid")

        query = (
            f"MATCH p={pattern} "
            "WHERE id(start) = $start_id "
            "RETURN id(start) AS source_id, "
            "id(target) AS target_id, "
            "type(last(rels)) AS relationship, "
            "size(rels) AS depth, "
            "coalesce(head(labels(start)), '') AS source_type, "
            "coalesce(head(labels(target)), '') AS target_type "
            "LIMIT $limit"
        )
        rows = self._execute(query, {"start_id": start_id, "limit": limit})
        selected = set(include_fields)
        return [
            {key: value for key, value in row.items() if key in selected}
            for row in rows
        ]


class ArangoGraphBackend:
    """Thin adapter over a caller-owned python-arango Database object."""

    def __init__(self, database: Any) -> None:
        self._database = database
        self._definitions: dict[str, tuple[GraphRelationshipTypeSpec, ...]] = {}

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        raw_graphs = self._database.graphs()
        if not isinstance(raw_graphs, Sequence) or isinstance(raw_graphs, (str, bytes)):
            raise SchemaValidationError("ArangoDB graphs() must return a list")

        results: list[GraphSourceSpec] = []
        for raw in raw_graphs:
            if not isinstance(raw, Mapping):
                raise SchemaValidationError("ArangoDB graph descriptor must be an object")
            name = str(raw.get("name") or raw.get("_key") or "")
            if not name:
                continue
            definitions_raw = raw.get("edge_definitions") or raw.get("edgeDefinitions") or ()
            relationships: list[GraphRelationshipTypeSpec] = []
            node_names: set[str] = set()
            for definition in definitions_raw:
                if not isinstance(definition, Mapping):
                    continue
                edge = str(
                    definition.get("edge_collection")
                    or definition.get("collection")
                    or ""
                )
                if not edge:
                    continue
                sources = tuple(
                    str(value)
                    for value in (
                        definition.get("from_vertex_collections")
                        or definition.get("from")
                        or ()
                    )
                )
                targets = tuple(
                    str(value)
                    for value in (
                        definition.get("to_vertex_collections")
                        or definition.get("to")
                        or ()
                    )
                )
                node_names.update(sources)
                node_names.update(targets)
                relationships.append(
                    GraphRelationshipTypeSpec(
                        name=edge,
                        source_types=sources,
                        target_types=targets,
                    )
                )
            orphan = raw.get("orphan_collections") or raw.get("orphanCollections") or ()
            node_names.update(str(value) for value in orphan)
            relation_tuple = tuple(relationships)
            self._definitions[name] = relation_tuple
            results.append(
                GraphSourceSpec(
                    name=name,
                    model="property_graph",
                    node_types=tuple(
                        GraphNodeTypeSpec(name=value)
                        for value in sorted(node_names)
                    ),
                    relationship_types=relation_tuple,
                    public_metadata={"vendor": "arangodb"},
                )
            )
        return tuple(results)

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        definitions = self._definitions.get(graph)
        if definitions is None:
            self.list_graphs()
            definitions = self._definitions.get(graph)
        if definitions is None:
            raise RegistrationError(f"unknown ArangoDB graph {graph!r}")
        known = {value.name for value in definitions}
        unknown = sorted(set(relationship_types) - known)
        if unknown:
            raise SchemaValidationError(
                "ArangoDB traversal requested unknown relationship types: "
                + ", ".join(unknown)
            )
        if not relationship_types:
            return []

        direction_map = {
            "out": "OUTBOUND",
            "in": "INBOUND",
            "both": "ANY",
        }
        aql_direction = direction_map.get(direction)
        if aql_direction is None:
            raise SchemaValidationError("ArangoDB traversal direction is invalid")

        query = (
            f"FOR v, e, p IN 1..{max_hops} {aql_direction} @start_id "
            "GRAPH @graph "
            "FILTER SPLIT(e._id, '/')[0] IN @relationship_types "
            "LIMIT @limit "
            "RETURN {"
            "source_id: @start_id, "
            "target_id: v._id, "
            "relationship: SPLIT(e._id, '/')[0], "
            "depth: LENGTH(p.edges), "
            "source_type: SPLIT(@start_id, '/')[0], "
            "target_type: SPLIT(v._id, '/')[0]"
            "}"
        )
        cursor = self._database.aql.execute(
            query,
            bind_vars={
                "start_id": start_id,
                "graph": graph,
                "relationship_types": list(relationship_types),
                "limit": limit,
            },
        )
        selected = set(include_fields)
        rows: list[dict[str, Any]] = []
        for raw in cursor:
            row = dict(_as_mapping(raw))
            rows.append({key: value for key, value in row.items() if key in selected})
        return rows


class SparqlGraphBackend:
    """Generic SPARQL 1.1 query adapter over a caller-owned HTTP client.

    The adapter performs read-only SELECT queries only. It never exposes arbitrary SPARQL text
    through the model-visible capability surface.
    """

    def __init__(
        self,
        client: Any,
        *,
        endpoint: str,
        graph_name: str = "sparql",
    ) -> None:
        if not endpoint.strip():
            raise ValueError("SPARQL endpoint must be non-empty")
        self._client = client
        self._endpoint = endpoint
        self._graph_name = graph_name
        self._predicates: tuple[str, ...] | None = None

    def _select(self, query: str) -> list[dict[str, Any]]:
        response = self._client.post(
            self._endpoint,
            content=query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        payload = response.json() if hasattr(response, "json") else response
        if not isinstance(payload, Mapping):
            raise SchemaValidationError("SPARQL response must be an object")
        results = payload.get("results", {})
        bindings = results.get("bindings", []) if isinstance(results, Mapping) else []
        if not isinstance(bindings, Sequence):
            raise SchemaValidationError("SPARQL bindings must be a list")

        rows: list[dict[str, Any]] = []
        for binding in bindings:
            if not isinstance(binding, Mapping):
                continue
            row: dict[str, Any] = {}
            for key, value in binding.items():
                if isinstance(value, Mapping) and "value" in value:
                    row[str(key)] = value["value"]
            rows.append(row)
        return rows

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        class_rows = self._select(
            "SELECT DISTINCT ?class WHERE { ?s a ?class . } ORDER BY ?class LIMIT 1000"
        )
        predicate_rows = self._select(
            "SELECT DISTINCT ?predicate WHERE { ?s ?predicate ?o . } "
            "ORDER BY ?predicate LIMIT 1000"
        )
        classes = tuple(
            str(row["class"]) for row in class_rows if row.get("class")
        )
        predicates = tuple(
            str(row["predicate"])
            for row in predicate_rows
            if row.get("predicate")
        )
        self._predicates = predicates
        return (
            GraphSourceSpec(
                name=self._graph_name,
                model="rdf",
                node_types=tuple(GraphNodeTypeSpec(name=value) for value in classes),
                relationship_types=tuple(
                    GraphRelationshipTypeSpec(name=value)
                    for value in predicates
                ),
                public_metadata={
                    "vendor": "sparql",
                    "protocol": "SPARQL 1.1",
                },
            ),
        )

    @staticmethod
    def _direction_pattern(
        direction: str,
        start: str,
        predicate_var: str,
        target_var: str,
    ) -> str:
        if direction == "out":
            return f"{start} {predicate_var} {target_var} ."
        if direction == "in":
            return f"{target_var} {predicate_var} {start} ."
        if direction == "both":
            return (
                "{ "
                f"{start} {predicate_var} {target_var} . "
                "} UNION { "
                f"{target_var} {predicate_var} {start} . "
                "}"
            )
        raise SchemaValidationError("SPARQL traversal direction is invalid")

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        if graph != self._graph_name:
            raise RegistrationError(f"unknown SPARQL graph {graph!r}")
        known = self._predicates
        if known is None:
            self.list_graphs()
            known = self._predicates or ()
        unknown = sorted(set(relationship_types) - set(known))
        if unknown:
            raise SchemaValidationError(
                "SPARQL traversal requested unknown predicates: "
                + ", ".join(unknown)
            )
        if not relationship_types:
            return []
        if max_hops != 1:
            raise SchemaValidationError(
                "generic SPARQL native adapter currently supports max_hops=1"
            )

        start = _absolute_iri(start_id)
        values = " ".join(_absolute_iri(value) for value in relationship_types)
        pattern = self._direction_pattern(direction, start, "?relationship", "?target")
        query = (
            "SELECT ?target ?relationship ?targetType WHERE { "
            f"VALUES ?relationship {{ {values} }} "
            f"{pattern} "
            "OPTIONAL { ?target a ?targetType . } "
            "} "
            f"LIMIT {int(limit)}"
        )
        rows = self._select(query)
        selected = set(include_fields)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            result = {
                "source_id": start_id,
                "target_id": row.get("target", ""),
                "relationship": row.get("relationship", ""),
                "depth": 1,
                "source_type": "",
                "target_type": row.get("targetType", ""),
            }
            normalized.append(
                {key: value for key, value in result.items() if key in selected}
            )
        return normalized

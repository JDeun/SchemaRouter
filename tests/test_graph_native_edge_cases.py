from __future__ import annotations

from typing import Any

import pytest

from schemarouter import RegistrationError, SchemaValidationError
from schemarouter.adapters.graph_native import (
    ArangoGraphBackend,
    Neo4jGraphBackend,
    NeptuneOpenCypherBackend,
    SparqlGraphBackend,
    _absolute_iri,
    _as_mapping,
    _cypher_identifier,
    _json_payload_rows,
    _normalize_neo4j_result,
)


class DataRow:
    def data(self) -> dict[str, Any]:
        return {"value": 1}


class ItemsRow:
    def items(self):
        return [("value", 2)]


def test_graph_native_result_normalizers_cover_supported_and_invalid_shapes() -> None:
    assert _as_mapping({"value": 0}) == {"value": 0}
    assert _as_mapping(DataRow()) == {"value": 1}
    assert _as_mapping(ItemsRow()) == {"value": 2}
    with pytest.raises(SchemaValidationError, match="not mapping-like"):
        _as_mapping(object())

    class Result:
        records = [DataRow()]

    assert _normalize_neo4j_result(Result()) == [{"value": 1}]
    assert _normalize_neo4j_result([{"value": 3}]) == [{"value": 3}]
    with pytest.raises(SchemaValidationError, match="unexpected result"):
        _normalize_neo4j_result(object())

    assert _json_payload_rows('{"value": 4}') == [{"value": 4}]
    assert _json_payload_rows({"value": 5}) == [{"value": 5}]
    with pytest.raises(SchemaValidationError, match="list of rows"):
        _json_payload_rows(42)


@pytest.mark.parametrize("value", ["", "bad" + chr(96) + "name", "bad\x00name"])
def test_cypher_identifier_rejects_unsafe_names(value: str) -> None:
    with pytest.raises(SchemaValidationError, match="unsafe identifier"):
        _cypher_identifier(value)


@pytest.mark.parametrize(
    "value",
    ["relative", "https://example.test/<bad>", "https://example.test/bad\n"],
)
def test_sparql_iri_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(SchemaValidationError, match="absolute safe IRI"):
        _absolute_iri(value)


class DirectionNeo4jDriver:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute_query(self, query: str, **kwargs: Any):
        self.queries.append(query)
        if "db.labels" in query:
            return ([{"label": "Person"}], None, [])
        if "db.relationshipTypes" in query:
            return ([{"relationshipType": "KNOWS"}], None, [])
        return ([], None, [])


def test_neo4j_validation_and_direction_branches() -> None:
    with pytest.raises(ValueError, match="database"):
        Neo4jGraphBackend(DirectionNeo4jDriver(), database=" ")

    driver = DirectionNeo4jDriver()
    backend = Neo4jGraphBackend(driver, database="neo4j", graph_name="social")

    with pytest.raises(RegistrationError, match="unknown Neo4j graph"):
        backend.traverse(
            graph="missing", start_id="p1", relationship_types=("KNOWS",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )

    assert backend.traverse(
        graph="social", start_id="p1", relationship_types=(),
        direction="out", max_hops=1, limit=5, include_fields=("target_id",),
    ) == []

    with pytest.raises(SchemaValidationError, match="unknown relationship"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("OWNS",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )

    for direction in ("in", "both"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("KNOWS",),
            direction=direction, max_hops=1, limit=5, include_fields=("target_id",),
        )

    with pytest.raises(SchemaValidationError, match="direction is invalid"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("KNOWS",),
            direction="sideways", max_hops=1, limit=5, include_fields=("target_id",),
        )


class EmptyNeptuneClient:
    def execute_open_cypher_query(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs["openCypherQuery"]
        if "UNWIND labels" in query:
            return {"results": [{"label": "Person"}]}
        if "DISTINCT type(r)" in query:
            return {"results": [{"relationshipType": "KNOWS"}]}
        return {"results": []}


def test_neptune_validation_and_client_branches() -> None:
    with pytest.raises(ValueError, match="graph_name"):
        NeptuneOpenCypherBackend(EmptyNeptuneClient(), graph_name=" ")

    with pytest.raises(RegistrationError, match="must expose"):
        NeptuneOpenCypherBackend(object()).list_graphs()

    backend = NeptuneOpenCypherBackend(EmptyNeptuneClient(), graph_name="social")
    with pytest.raises(RegistrationError, match="unknown Neptune graph"):
        backend.traverse(
            graph="missing", start_id="p1", relationship_types=("KNOWS",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )

    assert backend.traverse(
        graph="social", start_id="p1", relationship_types=(),
        direction="out", max_hops=1, limit=5, include_fields=("target_id",),
    ) == []

    with pytest.raises(SchemaValidationError, match="unknown relationship"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("OWNS",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )

    for direction in ("in", "both"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("KNOWS",),
            direction=direction, max_hops=1, limit=5, include_fields=("target_id",),
        )

    with pytest.raises(SchemaValidationError, match="direction is invalid"):
        backend.traverse(
            graph="social", start_id="p1", relationship_types=("KNOWS",),
            direction="sideways", max_hops=1, limit=5, include_fields=("target_id",),
        )


class EdgeCaseAQL:
    def execute(self, query: str, *, bind_vars: dict[str, Any]):
        return [DataRow()]


class EdgeCaseArango:
    def __init__(self, graphs: Any) -> None:
        self._graphs = graphs
        self.aql = EdgeCaseAQL()

    def graphs(self) -> Any:
        return self._graphs


def test_arango_schema_and_traversal_defensive_branches() -> None:
    with pytest.raises(SchemaValidationError, match="must return a list"):
        ArangoGraphBackend(EdgeCaseArango("bad")).list_graphs()
    with pytest.raises(SchemaValidationError, match="descriptor must be an object"):
        ArangoGraphBackend(EdgeCaseArango([1])).list_graphs()

    database = EdgeCaseArango([
        {},
        {
            "_key": "org",
            "edgeDefinitions": [
                "skip", {},
                {"collection": "member_of", "from": ["people"], "to": ["teams"]},
            ],
            "orphanCollections": ["orphans"],
        },
    ])
    backend = ArangoGraphBackend(database)
    graph = backend.list_graphs()[0]
    assert graph.name == "org"
    assert {node.name for node in graph.node_types} == {"orphans", "people", "teams"}

    with pytest.raises(RegistrationError, match="unknown ArangoDB graph"):
        backend.traverse(
            graph="missing", start_id="people/alice",
            relationship_types=("member_of",), direction="out",
            max_hops=1, limit=5, include_fields=("target_id",),
        )
    assert backend.traverse(
        graph="org", start_id="people/alice", relationship_types=(),
        direction="out", max_hops=1, limit=5, include_fields=("target_id",),
    ) == []
    with pytest.raises(SchemaValidationError, match="unknown relationship"):
        backend.traverse(
            graph="org", start_id="people/alice", relationship_types=("owns",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )
    with pytest.raises(SchemaValidationError, match="direction is invalid"):
        backend.traverse(
            graph="org", start_id="people/alice", relationship_types=("member_of",),
            direction="sideways", max_hops=1, limit=5, include_fields=("target_id",),
        )


class RawSparqlClient:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def post(self, *args: Any, **kwargs: Any) -> Any:
        return self.payload


def test_sparql_response_and_traversal_defensive_branches() -> None:
    with pytest.raises(ValueError, match="endpoint"):
        SparqlGraphBackend(RawSparqlClient({}), endpoint=" ")
    with pytest.raises(SchemaValidationError, match="response must be an object"):
        SparqlGraphBackend(
            RawSparqlClient([]), endpoint="https://example.test/sparql"
        ).list_graphs()
    backend = SparqlGraphBackend(
        RawSparqlClient({"results": {"bindings": "bad"}}),
        endpoint="https://example.test/sparql",
    )
    with pytest.raises(SchemaValidationError, match="bindings must be a list"):
        backend.list_graphs()

    class DynamicClient:
        def post(self, url: str, *, content: bytes, headers: dict[str, str]):
            query = content.decode()
            if "SELECT DISTINCT ?class" in query:
                return {"results": {"bindings": [
                    "skip",
                    {"class": {"value": "https://example.test/Person"}},
                    {"ignored": {"type": "uri"}},
                ]}}
            if "SELECT DISTINCT ?predicate" in query:
                return {"results": {"bindings": [{
                    "predicate": {"value": "https://example.test/knows"}
                }]}}
            return {"results": {"bindings": []}}

    backend = SparqlGraphBackend(
        DynamicClient(), endpoint="https://example.test/sparql", graph_name="rdf"
    )
    backend.list_graphs()

    for direction in ("in", "both"):
        assert backend.traverse(
            graph="rdf", start_id="https://example.test/alice",
            relationship_types=("https://example.test/knows",),
            direction=direction, max_hops=1, limit=5,
            include_fields=("target_id",),
        ) == []

    with pytest.raises(RegistrationError, match="unknown SPARQL graph"):
        backend.traverse(
            graph="missing", start_id="https://example.test/alice",
            relationship_types=("https://example.test/knows",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )
    assert backend.traverse(
        graph="rdf", start_id="https://example.test/alice", relationship_types=(),
        direction="out", max_hops=1, limit=5, include_fields=("target_id",),
    ) == []
    with pytest.raises(SchemaValidationError, match="unknown predicates"):
        backend.traverse(
            graph="rdf", start_id="https://example.test/alice",
            relationship_types=("https://example.test/owns",),
            direction="out", max_hops=1, limit=5, include_fields=("target_id",),
        )
    with pytest.raises(SchemaValidationError, match="max_hops=1"):
        backend.traverse(
            graph="rdf", start_id="https://example.test/alice",
            relationship_types=("https://example.test/knows",),
            direction="out", max_hops=2, limit=5, include_fields=("target_id",),
        )
    with pytest.raises(SchemaValidationError, match="direction is invalid"):
        backend.traverse(
            graph="rdf", start_id="https://example.test/alice",
            relationship_types=("https://example.test/knows",),
            direction="sideways", max_hops=1, limit=5, include_fields=("target_id",),
        )

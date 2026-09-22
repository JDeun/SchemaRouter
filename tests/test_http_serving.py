import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.serving import HTTPServerPolicy, create_app


def make_router(*, bind: bool = True, counter: dict[str, int] | None = None) -> SchemaRouter:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="weather",
            description="Weather tool",
            endpoints=[
                EndpointSpec(
                    name="current",
                    parameters=[
                        ParameterSpec(name="city", required=True),
                    ],
                    output_fields=[
                        FieldSpec(name="city"),
                        FieldSpec(name="temperature"),
                    ],
                    read_only=True,
                )
            ],
        )
    )

    if bind:

        def invoke(endpoint: str, arguments: dict) -> dict:
            if counter is not None:
                counter["calls"] = counter.get("calls", 0) + 1
            return {
                "city": arguments["city"],
                "temperature": 20,
            }

        router.executor.bind("weather", invoke)

    return router


def payload(city: str = "Seoul") -> dict:
    return {
        "request": {
            "query": "city temperature",
            "arguments": {"city": city},
        }
    }


def test_http_server_policy_rejects_unsafe_execution_configuration() -> None:
    with pytest.raises(ValueError, match="enable_execution requires bearer_token"):
        HTTPServerPolicy(enable_execution=True)

    policy = HTTPServerPolicy(
        enable_execution=True,
        allow_unauthenticated_execution=True,
    )
    assert policy.enable_execution is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bearer_token": ""},
        {"bearer_token": "line\nbreak"},
        {"max_request_bytes": 0},
        {"max_request_bytes": 16 * 1024 * 1024 + 1},
    ],
)
def test_http_server_policy_validates_trusted_configuration(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        HTTPServerPolicy(**kwargs)


def test_default_app_exposes_health_schema_and_plan_but_not_execution() -> None:
    counter: dict[str, int] = {}
    router = make_router(counter=counter)
    app = create_app(router)
    client = TestClient(app)

    assert client.get("/healthz").json() == {"status": "ok"}

    schemas = client.get("/v1/schemas")
    assert schemas.status_code == 200
    body = schemas.json()
    assert body["input"]["title"] == "PlanRequest"
    assert body["output"]["type"] == "array"
    assert "max_concurrency" in body["config"]["properties"]

    planned = client.post("/v1/plan", json=payload())
    assert planned.status_code == 200
    assert planned.json()["calls"][0]["tool"] == "weather"
    assert counter.get("calls", 0) == 0

    assert client.post("/v1/invoke", json=payload()).status_code == 404
    assert "/v1/invoke" not in app.openapi()["paths"]


def test_execution_route_requires_bearer_and_invokes_router() -> None:
    counter: dict[str, int] = {}
    app = create_app(
        make_router(counter=counter),
        policy=HTTPServerPolicy(
            bearer_token="top-secret",
            enable_execution=True,
        ),
    )
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.get("/v1/schemas").status_code == 401
    assert client.get(
        "/v1/schemas",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401

    response = client.post(
        "/v1/invoke",
        json=payload("Busan"),
        headers={"Authorization": "Bearer top-secret"},
    )

    assert response.status_code == 200
    assert response.json()[0]["data"] == {
        "city": "Busan",
        "temperature": 20,
    }
    assert counter["calls"] == 1
    assert "/v1/invoke" in app.openapi()["paths"]


def test_explicit_unauthenticated_execution_is_double_opt_in() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(
            enable_execution=True,
            allow_unauthenticated_execution=True,
        ),
    )

    response = TestClient(app).post("/v1/invoke", json=payload())

    assert response.status_code == 200


def test_bearer_auth_applies_to_plan_and_schema_routes_not_health() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(bearer_token="secret"),
    )
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.post("/v1/plan", json=payload()).status_code == 401
    assert client.get("/v1/schemas").status_code == 401

    headers = {"Authorization": "Bearer secret"}
    assert client.post("/v1/plan", json=payload(), headers=headers).status_code == 200
    assert client.get("/v1/schemas", headers=headers).status_code == 200


def test_request_body_size_is_bounded_before_validation() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(max_request_bytes=64),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/plan",
        content=b"{" + b"x" * 128 + b"}",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"error": "RequestBodyTooLarge"}


def test_invalid_content_length_is_rejected() -> None:
    app = create_app(make_router())
    client = TestClient(app)

    response = client.post(
        "/v1/plan",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": "invalid",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"error": "InvalidContentLength"}


def test_request_validation_errors_are_redacted_by_default() -> None:
    app = create_app(make_router())
    client = TestClient(app)

    response = client.post(
        "/v1/plan",
        json={
            "request": "city temperature",
            "secret": "must-not-be-reflected",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"error": "RequestValidationError"}
    assert "must-not-be-reflected" not in response.text


def test_request_validation_detail_requires_explicit_opt_in() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(expose_error_messages=True),
    )
    client = TestClient(app)

    response = client.post(
        "/v1/plan",
        json={
            "request": "city temperature",
            "unexpected": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "RequestValidationError"
    assert "detail" in response.json()


def test_schemarouter_errors_are_redacted_and_mapped() -> None:
    app = create_app(
        make_router(bind=False),
        policy=HTTPServerPolicy(
            enable_execution=True,
            allow_unauthenticated_execution=True,
        ),
    )
    client = TestClient(app)

    response = client.post("/v1/invoke", json=payload())

    assert response.status_code == 500
    assert response.json() == {"error": "ExecutionError"}


def test_docs_and_openapi_are_disabled_by_default() -> None:
    app = create_app(make_router())
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_can_be_explicitly_enabled() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(expose_docs=True),
    )
    client = TestClient(app)

    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_serving_surface_does_not_expose_mutation_or_ingestion_routes() -> None:
    app = create_app(
        make_router(),
        policy=HTTPServerPolicy(
            enable_execution=True,
            allow_unauthenticated_execution=True,
            expose_docs=True,
        ),
    )

    paths = set(app.openapi()["paths"])
    assert paths == {
        "/healthz",
        "/v1/schemas",
        "/v1/plan",
        "/v1/invoke",
    }


def test_plan_accepts_string_request() -> None:
    app = create_app(make_router())
    response = TestClient(app).post(
        "/v1/plan",
        json={"request": "city temperature"},
    )

    assert response.status_code == 200
    assert response.json()["calls"][0]["tool"] == "weather"


def test_plan_accepts_typed_request_shape() -> None:
    request = PlanRequest(
        query="city temperature",
        arguments={"city": "Seoul"},
    )
    app = create_app(make_router())

    response = TestClient(app).post(
        "/v1/plan",
        json={"request": request.model_dump(mode="json")},
    )

    assert response.status_code == 200

"""Disjoint 0.12-C catalogs for hierarchical capability ontology experiment #354."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    leaf: str
    objects: dict[str, str]
    temporal_scope: str | None = None


def _field(name: str, *, identifier: bool = False, unit: str | None = None) -> FieldSpec:
    return FieldSpec(
        name=name,
        json_schema={"type": "number" if unit else "string"},
        unit=unit,
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    cases_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Case Service", "version": "1.0.0"},
        "paths": {
            "/cases/{case_id}": {
                "get": {
                    "operationId": "c17",
                    "summary": "Retrieve one existing case by identifier",
                    "responses": {"200": {"description": "case"}},
                },
                "patch": {
                    "operationId": "c28",
                    "summary": "Update fields on an existing case",
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "c39",
                    "summary": "Delete an existing case permanently",
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("cases_api", cases_openapi))

    registry.register(
        tool_from_mcp(
            "catalog_ops",
            {
                "tools": [
                    {
                        "name": "k11",
                        "description": "Search catalog entries that match filters or keywords",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "k22",
                        "description": "Retrieve one already-identified catalog entry",
                        "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}},
                    },
                    {
                        "name": "k33",
                        "description": "List all available catalog entries",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="deliveries",
            description="Delivery handoff and access service",
            endpoints=[
                EndpointSpec(
                    name="send",
                    description="Send a delivery packet to a destination",
                    read_only=False,
                    output_fields=[_field("delivery_id", identifier=True)],
                ),
                EndpointSpec(
                    name="share",
                    description="Share access to a delivery packet with another user",
                    read_only=False,
                    output_fields=[_field("delivery_id", identifier=True)],
                ),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="document_ops",
            description="Document transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export a document to an external file", read_only=True),
                EndpointSpec(name="summarize", description="Summarize a document into its main points", read_only=True),
                EndpointSpec(name="compare", description="Compare two documents for similarities and differences", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple documents into one document", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="workers",
            description="Background worker control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing background worker", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered worker operation", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="demand",
            description="Demand observations and prediction service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current demand value", read_only=True, output_fields=[_field("value", unit="unit")]),
                EndpointSpec(name="history", description="Retrieve historical demand values", read_only=True, output_fields=[_field("value", unit="unit")]),
                EndpointSpec(name="forecast", description="Forecast future demand values", read_only=True, output_fields=[_field("value", unit="unit")]),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="membership",
            description="Membership lifecycle service",
            endpoints=[
                EndpointSpec(name="create", description="Create a new membership", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active membership", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid membership charge", read_only=False),
            ],
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    accounts_openapi = {
        "openapi": "3.1.0",
        "info": {"title": "Account Service", "version": "1.0.0"},
        "paths": {
            "/accounts/{account_id}": {
                "get": {
                    "operationId": "a17",
                    "summary": "Retrieve one existing account",
                    "responses": {"200": {"description": "account"}},
                },
                "patch": {
                    "operationId": "a28",
                    "summary": "Update an existing account",
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/accounts": {
                "post": {
                    "operationId": "a39",
                    "summary": "Create a brand-new account",
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("accounts_api", accounts_openapi))

    registry.register(
        tool_from_mcp(
            "library_ops",
            {
                "tools": [
                    {
                        "name": "l10",
                        "description": "Search library items that match a query",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                    {
                        "name": "l20",
                        "description": "Retrieve one already-identified library item",
                        "inputSchema": {"type": "object", "properties": {"item_id": {"type": "string"}}},
                    },
                    {
                        "name": "l30",
                        "description": "List the complete set of library items",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="message_access",
            description="Message delivery and sharing service",
            endpoints=[
                EndpointSpec(name="send", description="Send a message to a destination", read_only=False),
                EndpointSpec(name="share", description="Share access to a message with another user", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="content_ops",
            description="Content transformation service",
            endpoints=[
                EndpointSpec(name="export", description="Export content into an external file", read_only=True),
                EndpointSpec(name="translate", description="Translate content into another human language", read_only=True),
                EndpointSpec(name="summarize", description="Summarize content into a shorter form", read_only=True),
                EndpointSpec(name="merge", description="Merge multiple content items into one", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="runtimes",
            description="Runtime control service",
            endpoints=[
                EndpointSpec(name="restart", description="Restart an existing runtime", read_only=False),
                EndpointSpec(name="execute", description="Execute a registered runtime workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="capacity",
            description="Capacity observations and forecast service",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve current capacity", read_only=True),
                EndpointSpec(name="history", description="Retrieve historical capacity observations", read_only=True),
                EndpointSpec(name="forecast", description="Forecast future capacity", read_only=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="claims",
            description="Claim lifecycle and reimbursement service",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve an existing claim", read_only=True),
                EndpointSpec(name="update", description="Update an existing claim", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active claim", read_only=False),
                EndpointSpec(name="refund", description="Refund a paid claim amount", read_only=False),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("cases_api.c17", "retrieve", {"en":"case C-8","ko":"케이스 C-8","es":"caso C-8","ja":"ケースC-8","de":"fall C-8","mixed":"case C-8"}),
    RouteCaseSpec("cases_api.c28", "update", {"en":"case C-8","ko":"케이스 C-8","es":"caso C-8","ja":"ケースC-8","de":"fall C-8","mixed":"case C-8"}),
    RouteCaseSpec("cases_api.c39", "delete", {"en":"case C-8","ko":"케이스 C-8","es":"caso C-8","ja":"ケースC-8","de":"fall C-8","mixed":"case C-8"}),
    RouteCaseSpec("catalog_ops.k11", "search", {"en":"catalog entries about alloy","ko":"alloy 관련 카탈로그 항목","es":"entradas del catálogo sobre alloy","ja":"alloyに関するカタログ項目","de":"katalogeinträge zu alloy","mixed":"alloy 관련 catalog entries"}),
    RouteCaseSpec("catalog_ops.k22", "retrieve", {"en":"catalog entry K-4","ko":"카탈로그 항목 K-4","es":"entrada de catálogo K-4","ja":"カタログ項目K-4","de":"katalogeintrag K-4","mixed":"catalog entry K-4"}),
    RouteCaseSpec("catalog_ops.k33", "list", {"en":"catalog entries","ko":"카탈로그 항목","es":"entradas del catálogo","ja":"カタログ項目","de":"katalogeinträge","mixed":"catalog entries"}),
    RouteCaseSpec("deliveries.send", "send", {"en":"delivery packet D-5","ko":"배송 패킷 D-5","es":"paquete de entrega D-5","ja":"配送パケットD-5","de":"lieferpaket D-5","mixed":"delivery packet D-5"}),
    RouteCaseSpec("deliveries.share", "share", {"en":"delivery packet D-5","ko":"배송 패킷 D-5","es":"paquete de entrega D-5","ja":"配送パケットD-5","de":"lieferpaket D-5","mixed":"delivery packet D-5"}),
    RouteCaseSpec("document_ops.export", "export", {"en":"document DOC-3","ko":"문서 DOC-3","es":"documento DOC-3","ja":"文書DOC-3","de":"dokument DOC-3","mixed":"document DOC-3"}),
    RouteCaseSpec("document_ops.summarize", "summarize", {"en":"document DOC-3","ko":"문서 DOC-3","es":"documento DOC-3","ja":"文書DOC-3","de":"dokument DOC-3","mixed":"document DOC-3"}),
    RouteCaseSpec("document_ops.compare", "compare", {"en":"documents DOC-3 and DOC-4","ko":"문서 DOC-3과 DOC-4","es":"documentos DOC-3 y DOC-4","ja":"文書DOC-3とDOC-4","de":"dokumente DOC-3 und DOC-4","mixed":"documents DOC-3 DOC-4"}),
    RouteCaseSpec("document_ops.merge", "merge", {"en":"documents DOC-3 and DOC-4","ko":"문서 DOC-3과 DOC-4","es":"documentos DOC-3 y DOC-4","ja":"文書DOC-3とDOC-4","de":"dokumente DOC-3 und DOC-4","mixed":"documents DOC-3 DOC-4"}),
    RouteCaseSpec("workers.restart", "restart", {"en":"worker W-2","ko":"워커 W-2","es":"trabajador W-2","ja":"ワーカーW-2","de":"worker W-2","mixed":"worker W-2"}),
    RouteCaseSpec("workers.execute", "execute", {"en":"worker operation W-2","ko":"워커 작업 W-2","es":"operación de trabajador W-2","ja":"ワーカー操作W-2","de":"worker-operation W-2","mixed":"worker operation W-2"}),
    RouteCaseSpec("demand.current", "retrieve", {"en":"demand value","ko":"수요 값","es":"valor de demanda","ja":"需要値","de":"nachfragewert","mixed":"demand 값"}, temporal_scope="current"),
    RouteCaseSpec("demand.history", "retrieve", {"en":"demand values","ko":"수요 값","es":"valores de demanda","ja":"需要値","de":"nachfragewerte","mixed":"demand 값"}, temporal_scope="historical"),
    RouteCaseSpec("demand.forecast", "forecast", {"en":"demand values","ko":"수요 값","es":"valores de demanda","ja":"需要値","de":"nachfragewerte","mixed":"demand 값"}, temporal_scope="future"),
    RouteCaseSpec("membership.create", "create", {"en":"membership","ko":"멤버십","es":"membresía","ja":"メンバーシップ","de":"mitgliedschaft","mixed":"membership"}),
    RouteCaseSpec("membership.cancel", "cancel", {"en":"membership M-7","ko":"멤버십 M-7","es":"membresía M-7","ja":"メンバーシップM-7","de":"mitgliedschaft M-7","mixed":"membership M-7"}),
    RouteCaseSpec("membership.refund", "refund", {"en":"membership charge M-7","ko":"멤버십 결제 M-7","es":"cargo de membresía M-7","ja":"メンバーシップ料金M-7","de":"mitgliedschaftsgebühr M-7","mixed":"membership charge M-7"}),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("accounts_api.a17", "retrieve", {"en":"account A-6","ko":"계정 A-6","es":"cuenta A-6","ja":"アカウントA-6","de":"konto A-6","mixed":"account A-6"}),
    RouteCaseSpec("accounts_api.a28", "update", {"en":"account A-6","ko":"계정 A-6","es":"cuenta A-6","ja":"アカウントA-6","de":"konto A-6","mixed":"account A-6"}),
    RouteCaseSpec("accounts_api.a39", "create", {"en":"account","ko":"계정","es":"cuenta","ja":"アカウント","de":"konto","mixed":"account"}),
    RouteCaseSpec("library_ops.l10", "search", {"en":"library items about robotics","ko":"robotics 관련 라이브러리 항목","es":"elementos de biblioteca sobre robotics","ja":"roboticsに関するライブラリ項目","de":"bibliothekseinträge zu robotics","mixed":"robotics 관련 library items"}),
    RouteCaseSpec("library_ops.l20", "retrieve", {"en":"library item L-9","ko":"라이브러리 항목 L-9","es":"elemento de biblioteca L-9","ja":"ライブラリ項目L-9","de":"bibliothekseintrag L-9","mixed":"library item L-9"}),
    RouteCaseSpec("library_ops.l30", "list", {"en":"library items","ko":"라이브러리 항목","es":"elementos de biblioteca","ja":"ライブラリ項目","de":"bibliothekseinträge","mixed":"library items"}),
    RouteCaseSpec("message_access.send", "send", {"en":"message MSG-2","ko":"메시지 MSG-2","es":"mensaje MSG-2","ja":"メッセージMSG-2","de":"nachricht MSG-2","mixed":"message MSG-2"}),
    RouteCaseSpec("message_access.share", "share", {"en":"message MSG-2","ko":"메시지 MSG-2","es":"mensaje MSG-2","ja":"メッセージMSG-2","de":"nachricht MSG-2","mixed":"message MSG-2"}),
    RouteCaseSpec("content_ops.export", "export", {"en":"content X-1","ko":"콘텐츠 X-1","es":"contenido X-1","ja":"コンテンツX-1","de":"inhalt X-1","mixed":"content X-1"}),
    RouteCaseSpec("content_ops.translate", "translate", {"en":"content X-1","ko":"콘텐츠 X-1","es":"contenido X-1","ja":"コンテンツX-1","de":"inhalt X-1","mixed":"content X-1"}),
    RouteCaseSpec("content_ops.summarize", "summarize", {"en":"content X-1","ko":"콘텐츠 X-1","es":"contenido X-1","ja":"コンテンツX-1","de":"inhalt X-1","mixed":"content X-1"}),
    RouteCaseSpec("content_ops.merge", "merge", {"en":"content X-1 and X-2","ko":"콘텐츠 X-1과 X-2","es":"contenidos X-1 y X-2","ja":"コンテンツX-1とX-2","de":"inhalte X-1 und X-2","mixed":"content X-1 X-2"}),
    RouteCaseSpec("runtimes.restart", "restart", {"en":"runtime R-5","ko":"런타임 R-5","es":"runtime R-5","ja":"ランタイムR-5","de":"runtime R-5","mixed":"runtime R-5"}),
    RouteCaseSpec("runtimes.execute", "execute", {"en":"runtime workflow R-5","ko":"런타임 워크플로 R-5","es":"flujo de runtime R-5","ja":"ランタイムワークフローR-5","de":"runtime-workflow R-5","mixed":"runtime workflow R-5"}),
    RouteCaseSpec("capacity.current", "retrieve", {"en":"capacity value","ko":"용량 값","es":"valor de capacidad","ja":"容量値","de":"kapazitätswert","mixed":"capacity 값"}, temporal_scope="current"),
    RouteCaseSpec("capacity.history", "retrieve", {"en":"capacity values","ko":"용량 값","es":"valores de capacidad","ja":"容量値","de":"kapazitätswerte","mixed":"capacity 값"}, temporal_scope="historical"),
    RouteCaseSpec("capacity.forecast", "forecast", {"en":"capacity values","ko":"용량 값","es":"valores de capacidad","ja":"容量値","de":"kapazitätswerte","mixed":"capacity 값"}, temporal_scope="future"),
    RouteCaseSpec("claims.retrieve", "retrieve", {"en":"claim CL-4","ko":"클레임 CL-4","es":"reclamación CL-4","ja":"クレームCL-4","de":"anspruch CL-4","mixed":"claim CL-4"}),
    RouteCaseSpec("claims.update", "update", {"en":"claim CL-4","ko":"클레임 CL-4","es":"reclamación CL-4","ja":"クレームCL-4","de":"anspruch CL-4","mixed":"claim CL-4"}),
    RouteCaseSpec("claims.cancel", "cancel", {"en":"claim CL-4","ko":"클레임 CL-4","es":"reclamación CL-4","ja":"クレームCL-4","de":"anspruch CL-4","mixed":"claim CL-4"}),
    RouteCaseSpec("claims.refund", "refund", {"en":"claim payment CL-4","ko":"클레임 결제 CL-4","es":"pago de reclamación CL-4","ja":"クレーム支払いCL-4","de":"anspruchszahlung CL-4","mixed":"claim payment CL-4"}),
)

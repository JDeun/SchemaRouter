# ruff: noqa: E501
"""Disjoint 0.12-C catalogs for factorized resource-action experiment #355."""

from __future__ import annotations

from dataclasses import dataclass

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")


@dataclass(frozen=True)
class RouteCaseSpec:
    route_id: str
    action: str
    objects: dict[str, str]
    temporal_scope: str | None = None


def _text(name: str, *, identifier: bool = False, description: str = "") -> FieldSpec:
    return FieldSpec(
        name=name,
        description=description,
        json_schema={"type": "string"},
        identifier=identifier,
    )


def development_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    specimens_openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Specimen Registry",
            "version": "1.0.0",
            "description": "Laboratory specimen records with identifiers, labels and storage metadata",
        },
        "paths": {
            "/specimens/{specimen_id}": {
                "get": {
                    "operationId": "s17",
                    "summary": "Retrieve one laboratory specimen record",
                    "parameters": [{"name": "specimen_id", "in": "path", "required": True, "description": "laboratory specimen identifier", "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "specimen", "content": {"application/json": {"schema": {"type": "object", "properties": {"specimen_id": {"type": "string"}, "label": {"type": "string"}, "storage_temperature": {"type": "number", "x-unit": "K"}}}}}},
                },
                "patch": {
                    "operationId": "s28",
                    "summary": "Update storage metadata for an existing laboratory specimen",
                    "parameters": [{"name": "specimen_id", "in": "path", "required": True, "description": "laboratory specimen identifier", "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "updated"}},
                },
                "delete": {
                    "operationId": "s39",
                    "summary": "Delete an existing laboratory specimen record",
                    "parameters": [{"name": "specimen_id", "in": "path", "required": True, "description": "laboratory specimen identifier", "schema": {"type": "string"}}],
                    "responses": {"204": {"description": "deleted"}},
                },
            }
        },
    }
    registry.register(tool_from_openapi("specimens_api", specimens_openapi))

    registry.register(
        tool_from_mcp(
            "notebook_ops",
            {
                "tools": [
                    {"name": "n01", "description": "Search laboratory notebook entries by phrase", "inputSchema": {"type": "object", "properties": {"phrase": {"type": "string", "description": "notebook phrase"}}}},
                    {"name": "n02", "description": "Retrieve one laboratory notebook entry", "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string", "description": "notebook entry identifier"}}}, "outputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}}},
                    {"name": "n03", "description": "Send a laboratory notebook entry to a reviewer", "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}, "reviewer": {"type": "string"}}}},
                    {"name": "n04", "description": "Delete a laboratory notebook entry permanently", "inputSchema": {"type": "object", "properties": {"entry_id": {"type": "string"}}}},
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="datasets",
            description="Scientific dataset catalog with dataset identifiers, titles and file formats",
            endpoints=[
                EndpointSpec(name="list", description="List available scientific datasets", read_only=True, output_fields=[_text("dataset_id", identifier=True), _text("title"), _text("format")]),
                EndpointSpec(name="export", description="Export a scientific dataset to an external file", read_only=True, output_fields=[_text("dataset_id", identifier=True), _text("download_url")]),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="credits",
            description="Account credit transactions and monetary credit balances",
            endpoints=[
                EndpointSpec(
                    name="retrieve",
                    description="Retrieve an existing account credit transaction",
                    read_only=True,
                    output_fields=[
                        _text("credit_id", identifier=True),
                        FieldSpec(name="amount", description="credit transaction amount", json_schema={"type": "number"}, unit="USD"),
                    ],
                ),
                EndpointSpec(name="refund", description="Refund an existing account credit transaction", read_only=False, output_fields=[_text("credit_id", identifier=True)]),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="nodes",
            description="Compute node inventory with node identifiers, status and runtime state",
            endpoints=[
                EndpointSpec(name="status", description="Retrieve the current status of a compute node", read_only=True, output_fields=[_text("node_id", identifier=True), _text("status")]),
                EndpointSpec(name="restart", description="Restart a compute node", read_only=False, output_fields=[_text("node_id", identifier=True)]),
            ],
        )
    )

    registry.register(
        tool_from_mcp(
            "pipelines_ops",
            {
                "tools": [
                    {"name": "p01", "description": "List data processing pipelines", "inputSchema": {"type": "object", "properties": {}}},
                    {"name": "p02", "description": "Create a new data processing pipeline", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "source": {"type": "string"}}}},
                    {"name": "p03", "description": "Update an existing data processing pipeline", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "string"}}}},
                    {"name": "p04", "description": "Cancel an active data processing pipeline", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "string"}}}},
                    {"name": "p05", "description": "Execute a data processing pipeline", "inputSchema": {"type": "object", "properties": {"pipeline_id": {"type": "string"}}}},
                ]
            },
        )
    )
    return registry


def confirmation_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    reservations_openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Facility Reservation Service",
            "version": "1.0.0",
            "description": "Facility reservation records with rooms, times and attendees",
        },
        "paths": {
            "/reservations/{reservation_id}": {
                "get": {"operationId": "r11", "summary": "Retrieve an existing facility reservation", "responses": {"200": {"description": "reservation"}}},
                "patch": {"operationId": "r22", "summary": "Update an existing facility reservation", "responses": {"200": {"description": "updated"}}},
            },
            "/reservations/{reservation_id}/cancel": {
                "post": {"operationId": "r33", "summary": "Cancel an existing facility reservation", "responses": {"200": {"description": "cancelled"}}}
            },
        },
    }
    registry.register(tool_from_openapi("reservations_api", reservations_openapi))

    registry.register(
        tool_from_mcp(
            "records_ops",
            {
                "tools": [
                    {"name": "q01", "description": "Search compliance records by phrase", "inputSchema": {"type": "object", "properties": {"phrase": {"type": "string"}}}},
                    {"name": "q02", "description": "Retrieve one compliance record", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}}},
                    {"name": "q03", "description": "Export a compliance record to a file", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}}},
                    {"name": "q04", "description": "Share a compliance record with another user", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}}},
                    {"name": "q05", "description": "Translate a compliance record into another language", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "string"}}}},
                ]
            },
        )
    )

    registry.register(
        ToolSpec(
            name="memos",
            description="Team memo collection with memo identifiers, titles and text",
            endpoints=[
                EndpointSpec(name="list", description="List existing team memos", read_only=True),
                EndpointSpec(name="create", description="Create a new team memo", read_only=False),
                EndpointSpec(name="update", description="Update an existing team memo", read_only=False),
                EndpointSpec(name="delete", description="Delete an existing team memo", read_only=False, destructive=True),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="services",
            description="Managed service inventory with service identifiers, deployment state and runtime status",
            endpoints=[
                EndpointSpec(name="list", description="List managed services", read_only=True),
                EndpointSpec(name="restart", description="Restart a managed service", read_only=False),
                EndpointSpec(name="cancel", description="Cancel an active service operation", read_only=False),
                EndpointSpec(name="execute", description="Execute a managed service workflow", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="bills",
            description="Billing document records with bill identifiers, recipients and monetary amounts",
            endpoints=[
                EndpointSpec(name="retrieve", description="Retrieve an existing bill", read_only=True),
                EndpointSpec(name="refund", description="Refund a paid bill", read_only=False),
                EndpointSpec(name="send", description="Send a bill to a recipient", read_only=False),
            ],
        )
    )

    registry.register(
        ToolSpec(
            name="metrics",
            description="Operational metric observations with metric identifiers, timestamps and numeric values",
            endpoints=[
                EndpointSpec(name="current", description="Retrieve the current metric value", read_only=True),
                EndpointSpec(name="history", description="Retrieve historical metric values", read_only=True),
                EndpointSpec(name="forecast", description="Forecast future metric values", read_only=True),
            ],
        )
    )
    return registry


DEV_ROUTE_SPECS = (
    RouteCaseSpec("specimens_api.s17", "read", {"en":"specimen S-8","ko":"시료 S-8","es":"muestra S-8","ja":"試料S-8","de":"probe S-8","mixed":"specimen S-8"}),
    RouteCaseSpec("specimens_api.s28", "update", {"en":"specimen S-8 storage metadata","ko":"시료 S-8 보관 정보","es":"metadatos de almacenamiento de muestra S-8","ja":"試料S-8の保管情報","de":"lagerdaten der probe S-8","mixed":"specimen S-8 보관 정보"}),
    RouteCaseSpec("specimens_api.s39", "delete", {"en":"specimen S-8","ko":"시료 S-8","es":"muestra S-8","ja":"試料S-8","de":"probe S-8","mixed":"specimen S-8"}),
    RouteCaseSpec("notebook_ops.n01", "read", {"en":"laboratory notebook entries about catalyst","ko":"catalyst 관련 실험 노트","es":"entradas de cuaderno sobre catalyst","ja":"catalystに関する実験ノート","de":"labornotizen über catalyst","mixed":"catalyst 관련 notebook entries"}),
    RouteCaseSpec("notebook_ops.n02", "read", {"en":"notebook entry N-4","ko":"실험 노트 N-4","es":"entrada N-4 del cuaderno","ja":"ノートN-4","de":"notizeintrag N-4","mixed":"notebook entry N-4"}),
    RouteCaseSpec("notebook_ops.n03", "send", {"en":"notebook entry N-4","ko":"실험 노트 N-4","es":"entrada N-4 del cuaderno","ja":"ノートN-4","de":"notizeintrag N-4","mixed":"notebook entry N-4"}),
    RouteCaseSpec("notebook_ops.n04", "delete", {"en":"notebook entry N-4","ko":"실험 노트 N-4","es":"entrada N-4 del cuaderno","ja":"ノートN-4","de":"notizeintrag N-4","mixed":"notebook entry N-4"}),
    RouteCaseSpec("datasets.list", "read", {"en":"scientific datasets","ko":"과학 데이터셋","es":"conjuntos de datos científicos","ja":"科学データセット","de":"wissenschaftliche datensätze","mixed":"scientific 데이터셋"}),
    RouteCaseSpec("datasets.export", "export", {"en":"dataset D-2","ko":"데이터셋 D-2","es":"conjunto de datos D-2","ja":"データセットD-2","de":"datensatz D-2","mixed":"dataset D-2"}),
    RouteCaseSpec("credits.retrieve", "read", {"en":"credit transaction C-7","ko":"크레딧 거래 C-7","es":"transacción de crédito C-7","ja":"クレジット取引C-7","de":"gutschrift C-7","mixed":"credit transaction C-7"}),
    RouteCaseSpec("credits.refund", "refund", {"en":"credit transaction C-7","ko":"크레딧 거래 C-7","es":"transacción de crédito C-7","ja":"クレジット取引C-7","de":"gutschrift C-7","mixed":"credit transaction C-7"}),
    RouteCaseSpec("nodes.status", "read", {"en":"compute node X-3 status","ko":"컴퓨트 노드 X-3 상태","es":"estado del nodo X-3","ja":"計算ノードX-3の状態","de":"status des rechenknotens X-3","mixed":"compute node X-3 상태"}, temporal_scope="current"),
    RouteCaseSpec("nodes.restart", "restart", {"en":"compute node X-3","ko":"컴퓨트 노드 X-3","es":"nodo X-3","ja":"計算ノードX-3","de":"rechenknoten X-3","mixed":"compute node X-3"}),
    RouteCaseSpec("pipelines_ops.p01", "read", {"en":"data pipelines","ko":"데이터 파이프라인","es":"canales de datos","ja":"データパイプライン","de":"datenpipelines","mixed":"data 파이프라인"}),
    RouteCaseSpec("pipelines_ops.p02", "create", {"en":"data pipeline","ko":"데이터 파이프라인","es":"canal de datos","ja":"データパイプライン","de":"datenpipeline","mixed":"data 파이프라인"}),
    RouteCaseSpec("pipelines_ops.p03", "update", {"en":"pipeline P-9","ko":"파이프라인 P-9","es":"canal P-9","ja":"パイプラインP-9","de":"pipeline P-9","mixed":"pipeline P-9"}),
    RouteCaseSpec("pipelines_ops.p04", "cancel", {"en":"pipeline P-9","ko":"파이프라인 P-9","es":"canal P-9","ja":"パイプラインP-9","de":"pipeline P-9","mixed":"pipeline P-9"}),
    RouteCaseSpec("pipelines_ops.p05", "execute", {"en":"pipeline P-9","ko":"파이프라인 P-9","es":"canal P-9","ja":"パイプラインP-9","de":"pipeline P-9","mixed":"pipeline P-9"}),
)

CONFIRM_ROUTE_SPECS = (
    RouteCaseSpec("reservations_api.r11", "read", {"en":"facility reservation R-6","ko":"시설 예약 R-6","es":"reserva de instalación R-6","ja":"施設予約R-6","de":"raumreservierung R-6","mixed":"facility 예약 R-6"}),
    RouteCaseSpec("reservations_api.r22", "update", {"en":"facility reservation R-6","ko":"시설 예약 R-6","es":"reserva de instalación R-6","ja":"施設予約R-6","de":"raumreservierung R-6","mixed":"facility 예약 R-6"}),
    RouteCaseSpec("reservations_api.r33", "cancel", {"en":"facility reservation R-6","ko":"시설 예약 R-6","es":"reserva de instalación R-6","ja":"施設予約R-6","de":"raumreservierung R-6","mixed":"facility 예약 R-6"}),
    RouteCaseSpec("records_ops.q01", "read", {"en":"compliance records about audit","ko":"audit 관련 준수 기록","es":"registros de cumplimiento sobre audit","ja":"auditに関するコンプライアンス記録","de":"compliance-datensätze über audit","mixed":"audit 관련 compliance records"}),
    RouteCaseSpec("records_ops.q02", "read", {"en":"compliance record Q-4","ko":"준수 기록 Q-4","es":"registro de cumplimiento Q-4","ja":"コンプライアンス記録Q-4","de":"compliance-datensatz Q-4","mixed":"compliance record Q-4"}),
    RouteCaseSpec("records_ops.q03", "export", {"en":"compliance record Q-4","ko":"준수 기록 Q-4","es":"registro de cumplimiento Q-4","ja":"コンプライアンス記録Q-4","de":"compliance-datensatz Q-4","mixed":"compliance record Q-4"}),
    RouteCaseSpec("records_ops.q04", "share", {"en":"compliance record Q-4","ko":"준수 기록 Q-4","es":"registro de cumplimiento Q-4","ja":"コンプライアンス記録Q-4","de":"compliance-datensatz Q-4","mixed":"compliance record Q-4"}),
    RouteCaseSpec("records_ops.q05", "translate", {"en":"compliance record Q-4","ko":"준수 기록 Q-4","es":"registro de cumplimiento Q-4","ja":"コンプライアンス記録Q-4","de":"compliance-datensatz Q-4","mixed":"compliance record Q-4"}),
    RouteCaseSpec("memos.list", "read", {"en":"team memos","ko":"팀 메모","es":"memos de equipo","ja":"チームメモ","de":"team-memos","mixed":"team 메모"}),
    RouteCaseSpec("memos.create", "create", {"en":"team memo","ko":"팀 메모","es":"memo de equipo","ja":"チームメモ","de":"team-memo","mixed":"team 메모"}),
    RouteCaseSpec("memos.update", "update", {"en":"team memo M-3","ko":"팀 메모 M-3","es":"memo de equipo M-3","ja":"チームメモM-3","de":"team-memo M-3","mixed":"team memo M-3"}),
    RouteCaseSpec("memos.delete", "delete", {"en":"team memo M-3","ko":"팀 메모 M-3","es":"memo de equipo M-3","ja":"チームメモM-3","de":"team-memo M-3","mixed":"team memo M-3"}),
    RouteCaseSpec("services.list", "read", {"en":"managed services","ko":"관리 서비스","es":"servicios gestionados","ja":"管理サービス","de":"verwaltete dienste","mixed":"managed 서비스"}),
    RouteCaseSpec("services.restart", "restart", {"en":"service V-5","ko":"서비스 V-5","es":"servicio V-5","ja":"サービスV-5","de":"dienst V-5","mixed":"service V-5"}),
    RouteCaseSpec("services.cancel", "cancel", {"en":"service operation V-5","ko":"서비스 작업 V-5","es":"operación de servicio V-5","ja":"サービス操作V-5","de":"dienstvorgang V-5","mixed":"service operation V-5"}),
    RouteCaseSpec("services.execute", "execute", {"en":"service workflow V-5","ko":"서비스 워크플로 V-5","es":"flujo de servicio V-5","ja":"サービスワークフローV-5","de":"dienst-workflow V-5","mixed":"service workflow V-5"}),
    RouteCaseSpec("bills.retrieve", "read", {"en":"bill B-8","ko":"청구 문서 B-8","es":"factura B-8","ja":"請求書B-8","de":"rechnung B-8","mixed":"bill B-8"}),
    RouteCaseSpec("bills.refund", "refund", {"en":"bill B-8","ko":"청구 문서 B-8","es":"factura B-8","ja":"請求書B-8","de":"rechnung B-8","mixed":"bill B-8"}),
    RouteCaseSpec("bills.send", "send", {"en":"bill B-8","ko":"청구 문서 B-8","es":"factura B-8","ja":"請求書B-8","de":"rechnung B-8","mixed":"bill B-8"}),
    RouteCaseSpec("metrics.current", "read", {"en":"metric K-2 value","ko":"메트릭 K-2 값","es":"valor de métrica K-2","ja":"メトリックK-2の値","de":"metrikwert K-2","mixed":"metric K-2 값"}, temporal_scope="current"),
    RouteCaseSpec("metrics.history", "read", {"en":"metric K-2 values","ko":"메트릭 K-2 값","es":"valores de métrica K-2","ja":"メトリックK-2の値","de":"metrikwerte K-2","mixed":"metric K-2 값"}, temporal_scope="historical"),
    RouteCaseSpec("metrics.forecast", "forecast", {"en":"metric K-2 value","ko":"메트릭 K-2 값","es":"valor de métrica K-2","ja":"メトリックK-2の値","de":"metrikwert K-2","mixed":"metric K-2 값"}, temporal_scope="future"),
)

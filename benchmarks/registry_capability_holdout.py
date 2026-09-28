# ruff: noqa: E501 -- multilingual holdout fixtures are intentionally literal.
"""Registration-generalization holdout for experiment #338.

All route identities are absent from the canonical reference registry and from generic-head
training.  The suite exercises native ToolSpec, OpenAPI import, MCP import, opaque endpoint
names, empty operation aliases, and variable endpoint counts.
"""

from __future__ import annotations

from typing import Any

from schemarouter import EndpointSpec, FieldSpec, InMemoryRegistry, ToolSpec
from schemarouter.adapters.mcp import tool_from_mcp
from schemarouter.adapters.openapi import tool_from_openapi

LANGUAGES = ("en", "ko", "es", "ja", "de", "mixed")

_WRAPPERS: dict[str, tuple[str, str]] = {
    "en": ("{core}.", "Please {core}."),
    "ko": ("{core}.", "부탁인데 {core}."),
    "es": ("{core}.", "Por favor, {core}."),
    "ja": ("{core}。", "お願い、{core}。"),
    "de": ("{core}.", "Bitte {core}."),
    "mixed": ("{core}.", "please {core}."),
}


def build_registry() -> InMemoryRegistry:
    registry = InMemoryRegistry()

    # Native one-endpoint tool.  No operation_aliases are supplied.
    registry.register(
        ToolSpec(
            name="parcel_hub",
            description="Parcel delivery timing service",
            endpoints=[
                EndpointSpec(
                    name="eta_probe",
                    description="Estimate the future delivery arrival time for a parcel",
                    read_only=True,
                    output_fields=[
                        FieldSpec(name="parcel_code", identifier=True),
                        FieldSpec(name="estimated_arrival"),
                    ],
                )
            ],
        )
    )

    # OpenAPI three-endpoint tool with intentionally opaque operation IDs.
    contacts_openapi = {
        "openapi": "3.1.0",
        "info": {
            "title": "Contact Profile API",
            "version": "1.0.0",
            "description": "Contact profile lookup and editing service",
        },
        "paths": {
            "/contacts/{contact_id}": {
                "get": {
                    "operationId": "alpha_17",
                    "summary": "Fetch one contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "contact",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "contact_id": {"type": "string"},
                                            "display_name": {"type": "string"},
                                            "phone": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "patch": {
                    "operationId": "gamma_41",
                    "summary": "Update fields on an existing contact profile",
                    "parameters": [
                        {
                            "name": "contact_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "display_name": {"type": "string"},
                                        "phone": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "updated"}},
                },
            },
            "/contacts": {
                "post": {
                    "operationId": "beta_23",
                    "summary": "Register a new contact profile",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "display_name": {"type": "string"},
                                        "phone": {"type": "string"},
                                    },
                                    "required": ["display_name"],
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "created"}},
                }
            },
        },
    }
    registry.register(tool_from_openapi("contacts_api", contacts_openapi))

    # MCP five-endpoint tool.  Names are opaque; descriptions carry operation semantics.
    registry.register(
        tool_from_mcp(
            "media_ops",
            {
                "tools": [
                    {
                        "name": "x17",
                        "description": "Search media assets by owner or tag",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "owner": {"type": "string"},
                                "tag": {"type": "string"},
                            },
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                            },
                        },
                    },
                    {
                        "name": "q9",
                        "description": "Fetch one media asset and its metadata",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                                "labels": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    {
                        "name": "r2",
                        "description": "Update the title and labels of an existing media asset",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "asset_id": {"type": "string"},
                                "title": {"type": "string"},
                                "labels": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["asset_id"],
                        },
                    },
                    {
                        "name": "m4",
                        "description": "Send a media asset to the review queue",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                    },
                    {
                        "name": "z8",
                        "description": "Delete a media asset permanently",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"asset_id": {"type": "string"}},
                            "required": ["asset_id"],
                        },
                    },
                ]
            },
        )
    )

    # Native three-endpoint tool with opaque names and empty aliases.
    registry.register(
        ToolSpec(
            name="vault_docs",
            description="Secure document vault",
            endpoints=[
                EndpointSpec(
                    name="alpha",
                    description="List all stored secure documents",
                    read_only=True,
                ),
                EndpointSpec(
                    name="beta",
                    description="Create a new secure document",
                    read_only=False,
                ),
                EndpointSpec(
                    name="gamma",
                    description="Retrieve one secure document by document ID",
                    read_only=True,
                ),
            ],
        )
    )
    return registry


_SUPPORTED: dict[str, dict[str, str]] = {
    "parcel_hub.eta_probe": {
        "en": "tell me when parcel ZX-42 is expected to arrive",
        "ko": "택배 ZX-42가 언제 도착할 예정인지 알려줘",
        "es": "dime cuándo se espera que llegue el paquete ZX-42",
        "ja": "荷物ZX-42がいつ到着する予定か教えて",
        "de": "sag mir wann Paket ZX-42 voraussichtlich ankommt",
        "mixed": "parcel ZX-42가 언제 arrive할 예정인지 알려줘",
    },
    "contacts_api.alpha_17": {
        "en": "pull up the profile for contact C-17",
        "ko": "연락처 C-17의 프로필을 불러와줘",
        "es": "abre el perfil del contacto C-17",
        "ja": "連絡先C-17のプロフィールを取得して",
        "de": "rufe das Profil von Kontakt C-17 ab",
        "mixed": "contact C-17 profile을 fetch해줘",
    },
    "contacts_api.beta_23": {
        "en": "add Minji Kim as a new contact",
        "ko": "김민지를 새 연락처로 등록해줘",
        "es": "registra a Minji Kim como contacto nuevo",
        "ja": "Minji Kimを新しい連絡先として登録して",
        "de": "lege Minji Kim als neuen Kontakt an",
        "mixed": "Minji Kim을 new contact로 register해줘",
    },
    "contacts_api.gamma_41": {
        "en": "change the phone number on contact C-17",
        "ko": "연락처 C-17의 전화번호를 수정해줘",
        "es": "cambia el número de teléfono del contacto C-17",
        "ja": "連絡先C-17の電話番号を更新して",
        "de": "ändere die Telefonnummer von Kontakt C-17",
        "mixed": "contact C-17 phone number를 update해줘",
    },
    "media_ops.x17": {
        "en": "find media assets tagged launch",
        "ko": "launch 태그가 붙은 미디어 자산을 찾아줘",
        "es": "busca recursos multimedia con la etiqueta launch",
        "ja": "launchタグのメディア資産を探して",
        "de": "suche Medienobjekte mit dem Tag launch",
        "mixed": "launch tag media assets 찾아줘",
    },
    "media_ops.q9": {
        "en": "show the metadata for media asset A-88",
        "ko": "미디어 자산 A-88의 메타데이터를 보여줘",
        "es": "muestra los metadatos del recurso multimedia A-88",
        "ja": "メディア資産A-88のメタデータを見せて",
        "de": "zeige die Metadaten des Medienobjekts A-88",
        "mixed": "media asset A-88 metadata 보여줘",
    },
    "media_ops.r2": {
        "en": "rename media asset A-88 to final cut",
        "ko": "미디어 자산 A-88의 제목을 final cut으로 바꿔줘",
        "es": "cambia el título del recurso A-88 a final cut",
        "ja": "メディア資産A-88のタイトルをfinal cutに変更して",
        "de": "ändere den Titel von Medienobjekt A-88 in final cut",
        "mixed": "media asset A-88 title을 final cut으로 update해줘",
    },
    "media_ops.m4": {
        "en": "send media asset A-88 to the review queue",
        "ko": "미디어 자산 A-88을 검토 대기열로 보내줘",
        "es": "envía el recurso multimedia A-88 a la cola de revisión",
        "ja": "メディア資産A-88をレビューキューに送って",
        "de": "sende Medienobjekt A-88 an die Prüfwarteschlange",
        "mixed": "media asset A-88을 review queue로 send해줘",
    },
    "media_ops.z8": {
        "en": "permanently remove media asset A-88",
        "ko": "미디어 자산 A-88을 영구 삭제해줘",
        "es": "elimina permanentemente el recurso multimedia A-88",
        "ja": "メディア資産A-88を完全に削除して",
        "de": "lösche Medienobjekt A-88 dauerhaft",
        "mixed": "media asset A-88을 permanently delete해줘",
    },
    "vault_docs.alpha": {
        "en": "show every document stored in the secure vault",
        "ko": "보안 문서함에 저장된 문서를 전부 목록으로 보여줘",
        "es": "muestra todos los documentos guardados en la bóveda segura",
        "ja": "安全な保管庫にある文書をすべて一覧表示して",
        "de": "liste alle Dokumente im sicheren Tresor auf",
        "mixed": "secure vault documents 전부 list해줘",
    },
    "vault_docs.beta": {
        "en": "make a new secure document named NDA",
        "ko": "NDA라는 새 보안 문서를 만들어줘",
        "es": "crea un documento seguro nuevo llamado NDA",
        "ja": "NDAという新しい安全な文書を作成して",
        "de": "erstelle ein neues sicheres Dokument namens NDA",
        "mixed": "NDA라는 secure document를 create해줘",
    },
    "vault_docs.gamma": {
        "en": "open secure document D-7 for me",
        "ko": "보안 문서 D-7을 불러와줘",
        "es": "recupera el documento seguro D-7",
        "ja": "安全な文書D-7を取得して",
        "de": "rufe das sichere Dokument D-7 ab",
        "mixed": "secure document D-7을 retrieve해줘",
    },
}

_NEAR: dict[str, dict[str, tuple[str, str, str]]] = {
    "parcel_hub": {
        "en": ("cancel parcel ZX-42", "change the address for parcel ZX-42", "delete parcel ZX-42"),
        "ko": ("택배 ZX-42 배송을 취소해줘", "택배 ZX-42 배송 주소를 변경해줘", "택배 ZX-42를 삭제해줘"),
        "es": ("cancela el paquete ZX-42", "cambia la dirección del paquete ZX-42", "elimina el paquete ZX-42"),
        "ja": ("荷物ZX-42をキャンセルして", "荷物ZX-42の配送先を変更して", "荷物ZX-42を削除して"),
        "de": ("storniere Paket ZX-42", "ändere die Adresse für Paket ZX-42", "lösche Paket ZX-42"),
        "mixed": ("parcel ZX-42를 cancel해줘", "parcel ZX-42 address를 change해줘", "parcel ZX-42를 delete해줘"),
    },
    "contacts_api": {
        "en": ("delete contact C-17", "export all contacts", "merge contact C-17 with C-18"),
        "ko": ("연락처 C-17을 삭제해줘", "모든 연락처를 내보내줘", "연락처 C-17과 C-18을 병합해줘"),
        "es": ("elimina el contacto C-17", "exporta todos los contactos", "fusiona el contacto C-17 con C-18"),
        "ja": ("連絡先C-17を削除して", "すべての連絡先をエクスポートして", "連絡先C-17とC-18を統合して"),
        "de": ("lösche Kontakt C-17", "exportiere alle Kontakte", "führe Kontakt C-17 mit C-18 zusammen"),
        "mixed": ("contact C-17을 delete해줘", "all contacts를 export해줘", "contact C-17과 C-18을 merge해줘"),
    },
    "media_ops": {
        "en": ("translate media asset A-88 into Korean", "summarize media asset A-88", "export media asset A-88 as a zip file"),
        "ko": ("미디어 자산 A-88을 한국어로 번역해줘", "미디어 자산 A-88을 요약해줘", "미디어 자산 A-88을 zip으로 내보내줘"),
        "es": ("traduce el recurso A-88 al coreano", "resume el recurso A-88", "exporta el recurso A-88 como zip"),
        "ja": ("メディア資産A-88を韓国語に翻訳して", "メディア資産A-88を要約して", "メディア資産A-88をzipでエクスポートして"),
        "de": ("übersetze Medienobjekt A-88 ins Koreanische", "fasse Medienobjekt A-88 zusammen", "exportiere Medienobjekt A-88 als zip"),
        "mixed": ("media asset A-88을 Korean으로 translate해줘", "media asset A-88 summarize해줘", "media asset A-88을 zip으로 export해줘"),
    },
    "vault_docs": {
        "en": ("delete secure document D-7", "share secure document D-7 with Alex", "translate secure document D-7 into Spanish"),
        "ko": ("보안 문서 D-7을 삭제해줘", "보안 문서 D-7을 Alex와 공유해줘", "보안 문서 D-7을 스페인어로 번역해줘"),
        "es": ("elimina el documento seguro D-7", "comparte el documento seguro D-7 con Alex", "traduce el documento seguro D-7 al español"),
        "ja": ("安全な文書D-7を削除して", "安全な文書D-7をAlexと共有して", "安全な文書D-7をスペイン語に翻訳して"),
        "de": ("lösche das sichere Dokument D-7", "teile das sichere Dokument D-7 mit Alex", "übersetze das sichere Dokument D-7 ins Spanische"),
        "mixed": ("secure document D-7을 delete해줘", "secure document D-7을 Alex와 share해줘", "secure document D-7을 Spanish로 translate해줘"),
    },
}

_OOD: dict[str, tuple[str, str]] = {
    "en": ("write a limerick about moonlight", "what is the square root of 144"),
    "ko": ("달빛에 대한 짧은 시를 써줘", "144의 제곱근이 뭐야"),
    "es": ("escribe un poema corto sobre la luna", "cuál es la raíz cuadrada de 144"),
    "ja": ("月明かりについて短い詩を書いて", "144の平方根は何"),
    "de": ("schreibe ein kurzes Gedicht über Mondlicht", "was ist die Quadratwurzel von 144"),
    "mixed": ("moonlight에 대한 짧은 poem 써줘", "144 square root가 뭐야"),
}


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route, language_map in _SUPPORTED.items():
        route_id = route.replace(".", "-").replace("_", "-")
        for language in LANGUAGES:
            core = language_map[language]
            for index, wrapper in enumerate(_WRAPPERS[language], start=1):
                rows.append(
                    {
                        "id": f"reg-holdout-supported-{route_id}-{language}-{index}",
                        "query": wrapper.format(core=core),
                        "expected": route,
                        "category": "registration_supported",
                        "language": language,
                    }
                )

    for tool, language_map in _NEAR.items():
        for language in LANGUAGES:
            for index, query in enumerate(language_map[language], start=1):
                rows.append(
                    {
                        "id": f"reg-holdout-near-{tool}-{language}-{index}",
                        "query": query,
                        "expected": None,
                        "category": "registration_near_unsupported",
                        "language": language,
                        "unsupported_family": f"{tool}.unsupported_{index}",
                    }
                )

    for language in LANGUAGES:
        for index, query in enumerate(_OOD[language], start=1):
            rows.append(
                {
                    "id": f"reg-holdout-ood-{language}-{index}",
                    "query": query,
                    "expected": None,
                    "category": "registration_ood",
                    "language": language,
                }
            )
    return rows


def manifest() -> dict[str, Any]:
    registry = build_registry()
    rows = cases()
    endpoint_counts = sorted(len(tool.endpoints) for tool in registry.tools())
    supported = [row for row in rows if row["expected"] is not None]
    near = [row for row in rows if row["category"] == "registration_near_unsupported"]
    ood = [row for row in rows if row["category"] == "registration_ood"]
    return {
        "role": "registration_generalization_holdout",
        "case_count": len(rows),
        "supported_cases": len(supported),
        "near_domain_cases": len(near),
        "out_of_domain_cases": len(ood),
        "tool_count": len(registry.tools()),
        "route_count": sum(len(tool.endpoints) for tool in registry.tools()),
        "endpoint_counts": endpoint_counts,
        "adapters": sorted(
            {
                str(tool.execution_metadata.get("adapter", "native"))
                for tool in registry.tools()
            }
        ),
        "languages": list(LANGUAGES),
        "operation_aliases_required": False,
    }

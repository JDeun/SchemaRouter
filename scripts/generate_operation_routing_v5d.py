# ruff: noqa: E501
"""Generate disjoint 0.12-D corpora for asymmetric ontology-veto experiment #358."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asymmetric_ontology_veto import compile_registry_contracts  # noqa: E402
from benchmarks.operation_routing_v5d_catalog import (  # noqa: E402
    CONFIRM_ROUTE_SPECS,
    DEV_ROUTE_SPECS,
    LANGUAGES,
    RouteCaseSpec,
    confirmation_registry,
    development_registry,
)

SURFACES: dict[str, dict[str, tuple[str, str]]] = {
    "search": {
        "en": ("search {obj} by criteria", "find any {obj} that match"),
        "ko": ("조건으로 {obj} 검색해줘", "맞는 {obj} 찾아줘"),
        "es": ("busca {obj} por criterios", "encuentra {obj} que coincidan"),
        "ja": ("条件で{obj}を検索して", "一致する{obj}を探して"),
        "de": ("suche {obj} nach Kriterien", "finde passende {obj}"),
        "mixed": ("criteria로 {obj} search해줘", "matching {obj} 찾아줘"),
    },
    "retrieve": {
        "en": ("retrieve {obj}", "get the details of {obj}"),
        "ko": ("{obj} 조회해줘", "{obj} 상세정보 가져와줘"),
        "es": ("obtén {obj}", "recupera los detalles de {obj}"),
        "ja": ("{obj}を取得して", "{obj}の詳細を表示して"),
        "de": ("ruf {obj} ab", "hole die Details von {obj}"),
        "mixed": ("retrieve {obj}", "{obj} details 가져와줘"),
    },
    "list": {
        "en": ("list every {obj}", "show all {obj}"),
        "ko": ("모든 {obj} 목록 보여줘", "{obj} 전부 나열해줘"),
        "es": ("lista todos los {obj}", "muestra todos los {obj}"),
        "ja": ("すべての{obj}を一覧表示して", "{obj}を全部見せて"),
        "de": ("liste alle {obj} auf", "zeige alle {obj}"),
        "mixed": ("all {obj} list해줘", "{obj} 전부 보여줘"),
    },
    "create": {
        "en": ("create {obj}", "register a new {obj}"),
        "ko": ("{obj} 생성해줘", "새 {obj} 등록해줘"),
        "es": ("crea {obj}", "registra un nuevo {obj}"),
        "ja": ("{obj}を作成して", "新しい{obj}を登録して"),
        "de": ("erstelle {obj}", "registriere ein neues {obj}"),
        "mixed": ("create {obj}", "새 {obj} 등록해줘"),
    },
    "update": {
        "en": ("update {obj}", "modify {obj}"),
        "ko": ("{obj} 업데이트해줘", "{obj} 수정해줘"),
        "es": ("actualiza {obj}", "modifica {obj}"),
        "ja": ("{obj}を更新して", "{obj}を修正して"),
        "de": ("aktualisiere {obj}", "ändere {obj}"),
        "mixed": ("update {obj}", "{obj} 수정해줘"),
    },
    "delete": {
        "en": ("delete {obj}", "erase {obj} permanently"),
        "ko": ("{obj} 삭제해줘", "{obj} 영구적으로 지워줘"),
        "es": ("elimina {obj}", "borra {obj} permanentemente"),
        "ja": ("{obj}を削除して", "{obj}を永久に消して"),
        "de": ("lösche {obj}", "entferne {obj} dauerhaft"),
        "mixed": ("delete {obj}", "{obj} 영구 삭제해줘"),
    },
    "cancel": {
        "en": ("cancel {obj}", "abort {obj}"),
        "ko": ("{obj} 취소해줘", "{obj} 중단해줘"),
        "es": ("cancela {obj}", "anula {obj}"),
        "ja": ("{obj}をキャンセルして", "{obj}を中止して"),
        "de": ("storniere {obj}", "brich {obj} ab"),
        "mixed": ("cancel {obj}", "{obj} 중단해줘"),
    },
    "refund": {
        "en": ("refund {obj}", "return the money for {obj}"),
        "ko": ("{obj} 환불해줘", "{obj} 돈 돌려줘"),
        "es": ("reembolsa {obj}", "devuelve el dinero de {obj}"),
        "ja": ("{obj}を返金して", "{obj}のお金を返して"),
        "de": ("erstatte {obj}", "zahle das Geld für {obj} zurück"),
        "mixed": ("refund {obj}", "{obj} money 돌려줘"),
    },
    "send": {
        "en": ("send {obj}", "forward {obj}"),
        "ko": ("{obj} 보내줘", "{obj} 전송해줘"),
        "es": ("envía {obj}", "reenvía {obj}"),
        "ja": ("{obj}を送って", "{obj}を転送して"),
        "de": ("sende {obj}", "leite {obj} weiter"),
        "mixed": ("send {obj}", "{obj} 보내줘"),
    },
    "share": {
        "en": ("share {obj}", "grant another user access to {obj}"),
        "ko": ("{obj} 공유해줘", "다른 사용자에게 {obj} 접근권 줘"),
        "es": ("comparte {obj}", "da acceso a {obj} a otro usuario"),
        "ja": ("{obj}を共有して", "別のユーザーに{obj}へのアクセスを与えて"),
        "de": ("teile {obj}", "gib einem anderen Nutzer Zugriff auf {obj}"),
        "mixed": ("share {obj}", "{obj} access 공유해줘"),
    },
    "export": {
        "en": ("export {obj}", "download {obj} as a file"),
        "ko": ("{obj} 내보내줘", "{obj} 파일로 다운로드해줘"),
        "es": ("exporta {obj}", "descarga {obj} como archivo"),
        "ja": ("{obj}をエクスポートして", "{obj}をファイルでダウンロードして"),
        "de": ("exportiere {obj}", "lade {obj} als Datei herunter"),
        "mixed": ("export {obj}", "{obj} file로 다운로드해줘"),
    },
    "translate": {
        "en": ("translate {obj}", "convert {obj} to another language"),
        "ko": ("{obj} 번역해줘", "{obj} 다른 언어로 바꿔줘"),
        "es": ("traduce {obj}", "pasa {obj} a otro idioma"),
        "ja": ("{obj}を翻訳して", "{obj}を別の言語にして"),
        "de": ("übersetze {obj}", "übertrage {obj} in eine andere Sprache"),
        "mixed": ("translate {obj}", "{obj} 다른 language로 바꿔줘"),
    },
    "summarize": {
        "en": ("summarize {obj}", "give the key points of {obj}"),
        "ko": ("{obj} 요약해줘", "{obj} 핵심만 정리해줘"),
        "es": ("resume {obj}", "dame los puntos clave de {obj}"),
        "ja": ("{obj}を要約して", "{obj}の要点を教えて"),
        "de": ("fasse {obj} zusammen", "gib die Kernaussagen von {obj}"),
        "mixed": ("summarize {obj}", "{obj} 핵심 정리해줘"),
    },
    "compare": {
        "en": ("compare {obj}", "show the differences in {obj}"),
        "ko": ("{obj} 비교해줘", "{obj} 차이점 보여줘"),
        "es": ("compara {obj}", "muestra las diferencias de {obj}"),
        "ja": ("{obj}を比較して", "{obj}の違いを見せて"),
        "de": ("vergleiche {obj}", "zeige die Unterschiede bei {obj}"),
        "mixed": ("compare {obj}", "{obj} 차이 보여줘"),
    },
    "merge": {
        "en": ("merge {obj}", "combine {obj} into one"),
        "ko": ("{obj} 병합해줘", "{obj} 하나로 합쳐줘"),
        "es": ("fusiona {obj}", "combina {obj} en uno"),
        "ja": ("{obj}を統合して", "{obj}を一つにまとめて"),
        "de": ("führe {obj} zusammen", "kombiniere {obj} zu einem"),
        "mixed": ("merge {obj}", "{obj} 하나로 합쳐줘"),
    },
    "restart": {
        "en": ("restart {obj}", "reboot {obj}"),
        "ko": ("{obj} 재시작해줘", "{obj} 재부팅해줘"),
        "es": ("reinicia {obj}", "vuelve a iniciar {obj}"),
        "ja": ("{obj}を再起動して", "{obj}をもう一度起動して"),
        "de": ("starte {obj} neu", "reboote {obj}"),
        "mixed": ("restart {obj}", "{obj} 재부팅해줘"),
    },
    "execute": {
        "en": ("execute {obj}", "run {obj}"),
        "ko": ("{obj} 실행해줘", "{obj} 돌려줘"),
        "es": ("ejecuta {obj}", "lanza {obj}"),
        "ja": ("{obj}を実行して", "{obj}を起動して"),
        "de": ("führe {obj} aus", "starte {obj}"),
        "mixed": ("execute {obj}", "{obj} 실행해줘"),
    },
    "forecast": {
        "en": ("forecast {obj}", "predict future {obj}"),
        "ko": ("{obj} 예측해줘", "미래 {obj} 전망해줘"),
        "es": ("pronostica {obj}", "predice {obj} futuro"),
        "ja": ("{obj}を予測して", "将来の{obj}を予測して"),
        "de": ("prognostiziere {obj}", "sage zukünftige {obj} voraus"),
        "mixed": ("forecast {obj}", "future {obj} 예측해줘"),
    },
}

TEMPORAL = {
    "current":{"en":"current","ko":"현재","es":"actual","ja":"現在の","de":"aktuell","mixed":"현재"},
    "future":{"en":"future","ko":"향후","es":"futuro","ja":"将来の","de":"zukünftig","mixed":"future"},
    "historical":{"en":"historical","ko":"과거","es":"histórico","ja":"過去の","de":"historisch","mixed":"historical"},
}

ALL_TOOL_LEAVES = (
    "search","retrieve","list","create","update","delete","cancel","refund",
    "send","share","export","translate","summarize","compare","merge",
    "restart","execute","forecast",
)

OOD = {
    "en":("write a poem about a forest","invent a science fiction scene","explain why metal rusts","explain the water cycle","calculate 225 divided by 15","solve 31 plus 48","tell me a knock-knock joke","say a cheerful greeting","compose a piano motif","write a tiny parable","calculate the fifth root of 32","explain DNA replication"),
    "ko":("숲에 대한 시 써줘","공상과학 장면 지어줘","금속이 녹스는 이유 설명해줘","물의 순환 설명해줘","225 나누기 15 계산해줘","31 더하기 48 풀어줘","노크노크 농담 해줘","밝게 인사해줘","피아노 모티프 작곡해줘","짧은 우화 써줘","32의 5제곱근 계산해줘","DNA 복제를 설명해줘"),
    "es":("escribe un poema sobre un bosque","inventa una escena de ciencia ficción","explica por qué se oxida el metal","explica el ciclo del agua","calcula 225 dividido entre 15","resuelve 31 más 48","cuéntame un chiste toc toc","haz un saludo alegre","compón un motivo de piano","escribe una parábola pequeña","calcula la quinta raíz de 32","explica la replicación del ADN"),
    "ja":("森について詩を書いて","SFの場面を作って","金属が錆びる理由を説明して","水の循環を説明して","225割る15を計算して","31足す48を解いて","ノックノックジョークを言って","明るく挨拶して","ピアノのモチーフを作曲して","短い寓話を書いて","32の5乗根を計算して","DNA複製を説明して"),
    "de":("schreibe ein gedicht über einen wald","erfinde eine science-fiction-szene","erkläre warum metall rostet","erkläre den wasserkreislauf","berechne 225 geteilt durch 15","löse 31 plus 48","erzähl einen klopf-klopf-witz","begrüße mich fröhlich","komponiere ein klaviermotiv","schreibe eine kleine parabel","berechne die fünfte wurzel aus 32","erkläre DNA-replikation"),
    "mixed":("forest에 대한 poem 써줘","science fiction scene 지어줘","metal이 rust하는 이유 explain해줘","water cycle 설명해줘","225 divided by 15 계산해줘","31 plus 48 풀어줘","knock-knock joke 해줘","cheerful greeting 해줘","piano motif 작곡해줘","tiny parable 써줘","32 fifth root 계산해줘","DNA replication 설명해줘"),
}


def _canonical(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()


def _object(spec: RouteCaseSpec, language: str) -> str:
    obj=spec.objects[language]
    return f"{TEMPORAL[spec.temporal_scope][language]} {obj}" if spec.temporal_scope else obj


def _supported(specs: tuple[RouteCaseSpec,...], prefix: str) -> list[dict[str,Any]]:
    rows=[]
    for spec in specs:
        slug=spec.route_id.replace(".","-").replace("_","-")
        for language in LANGUAGES:
            obj=_object(spec,language)
            for index,template in enumerate(SURFACES[spec.leaf][language],start=1):
                rows.append({"id":f"{prefix}-supported-{slug}-{language}-{index}","query":template.format(obj=obj),"expected":spec.route_id,"category":"supported","language":language})
    return rows


def _by_tool(specs: tuple[RouteCaseSpec,...]) -> dict[str,list[RouteCaseSpec]]:
    result={}
    for spec in specs:
        result.setdefault(spec.route_id.split(".",1)[0],[]).append(spec)
    return result


def _near(specs: tuple[RouteCaseSpec,...], prefix: str) -> list[dict[str,Any]]:
    rows=[]
    for tool,tool_specs in sorted(_by_tool(specs).items()):
        supported={spec.leaf for spec in tool_specs}
        unsupported=[leaf for leaf in ALL_TOOL_LEAVES if leaf not in supported][:6]
        anchor=tool_specs[0]
        for language in LANGUAGES:
            obj=anchor.objects[language]
            for index,leaf in enumerate(unsupported,start=1):
                template=SURFACES[leaf][language][index % 2]
                rows.append({"id":f"{prefix}-near-{tool}-{language}-{index}","query":template.format(obj=obj),"expected":None,"category":"near_domain_unsupported_operation","language":language,"unsupported_action":leaf,"unsupported_family":f"{tool}.{leaf}"})
    return rows


def _ood(prefix: str) -> list[dict[str,Any]]:
    return [{"id":f"{prefix}-ood-{language}-{index}","query":query,"expected":None,"category":"out_of_domain","language":language} for language in LANGUAGES for index,query in enumerate(OOD[language],start=1)]


def build(role: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if role == "development":
        registry = development_registry()
        specs = DEV_ROUTE_SPECS
        prefix = "v5d-dev"
    elif role == "confirmation":
        registry = confirmation_registry()
        specs = CONFIRM_ROUTE_SPECS
        prefix = "v5d-confirm"
    else:
        raise ValueError("role must be development or confirmation")

    contracts=compile_registry_contracts(registry)
    expected={spec.route_id for spec in specs}
    if set(contracts)!=expected:
        raise ValueError(f"route fixture mismatch missing={sorted(expected-set(contracts))} extra={sorted(set(contracts)-expected)}")
    if any(contract.leaf is None for contract in contracts.values()):
        unknown=sorted(route for route,contract in contracts.items() if contract.leaf is None)
        raise ValueError(f"all evaluation endpoint leaves must be known before freeze: {unknown}")

    rows=[*_supported(specs,prefix),*_near(specs,prefix),*_ood(prefix)]
    if len({row["id"] for row in rows})!=len(rows):
        raise ValueError("duplicate IDs")
    supported=[row for row in rows if row["expected"] is not None]
    near=[row for row in rows if row["category"]=="near_domain_unsupported_operation"]
    ood=[row for row in rows if row["category"]=="out_of_domain"]
    manifest={
        "role":role,
        "case_count":len(rows),
        "supported_cases":len(supported),
        "near_domain_cases":len(near),
        "out_of_domain_cases":len(ood),
        "route_count":len(contracts),
        "tool_count":len(registry.tools()),
        "endpoint_counts":sorted(len(tool.endpoints) for tool in registry.tools()),
        "languages":list(LANGUAGES),
        "adapters":sorted({contract.adapter or "native" for contract in contracts.values()}),
        "corpus_sha256":hashlib.sha256(_canonical(rows)).hexdigest(),
    }
    return rows,manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    freeze = {}
    for role in ("development","confirmation"):
        rows,manifest=build(role)
        (args.out_dir/f"{role}.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (args.out_dir/f"{role}-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        freeze[role]=manifest
    (args.out_dir/"freeze-manifest.json").write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(freeze,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()

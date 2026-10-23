"""Research-only Qwen3.5 native XML -> unchanged strict SchemaRouter tool grammar.

Qwen3.5 emits <tool_call><function=name><parameter=key>value...</parameter>
instead of the legacy Qwen3 JSON body. Never interpret XML as permission,
invent routes, fill missing arguments, or execute source callbacks here.
Only the existing original host parser, source binding and executor can run.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action

# Exact, single, balanced call. No unparsed prefix/suffix/multicall tolerance.
_CALL = re.compile(
    r"<tool_call>\s*<function=([a-z][a-z0-9_]*__[a-z][a-z0-9_]*)>"
    r"(?P<params>.*?)</function>\s*</tool_call>", re.DOTALL,
)
_PARAMETER = re.compile(
    r"\s*<parameter=([A-Za-z][A-Za-z0-9_]*)>\s*(.*?)\s*</parameter>",
    re.DOTALL,
)
_RESERVED_SCHEMA_REQUEST = "research__request_scoped_source_schema"


def _scalar_from_xml(raw: str, field_schema: Mapping[str, Any]) -> Any:
    """Use the offered native argument type; never infer a value from a name."""
    if type(field_schema) is not dict:
        raise ValueError("original offered property schema required")
    kind = field_schema.get("type")
    raw = raw.strip()
    if any(mark in raw for mark in ("<", ">")):
        raise ValueError("nested markup in native argument")
    if kind == "string":
        return raw
    if kind not in ("integer", "number", "boolean", "array"):
        raise ValueError("unhandled native argument type")
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite JSON token")
        ))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise ValueError("native argument JSON value rejected") from exc
    if kind == "integer" and type(value) is not int:
        raise ValueError("integer argument type mismatch")
    if kind == "number" and (
        type(value) not in (float, int) or not math.isfinite(value)
    ):
        raise ValueError("number argument type mismatch")
    if kind == "boolean" and type(value) is not bool:
        raise ValueError("boolean argument type mismatch")
    if kind == "array":
        if type(value) is not list or field_schema.get("items", {}).get("type") != "string":
            raise ValueError("unsupported array argument")
        if any(type(item) is not str for item in value):
            raise ValueError("string-array type mismatch")
    return value


def normalize_qwen35_xml_action(
    text: str, *, offered_tools: Sequence[dict[str, Any]],
) -> tuple[str, bool]:
    """Return (canonical text, normalized), not an authorized tool call.

    A final answer passes through as-is. Every XML tool call must be complete,
    offered by the trusted host and accepted by the pre-existing strict parser.
    The one non-executing research schema-request action supports an array
    only through the pre-existing surgical schema-request validator.
    """
    if type(text) is not str or type(offered_tools) not in (list, tuple):
        raise ValueError("model text and trusted tool definitions required")
    if not text.lstrip().startswith("<tool_call>"):
        if "<tool_call" in text or "</tool_call>" in text or "<function=" in text:
            raise ValueError("malformed or partial Qwen3.5 native action")
        return text, False
    match = _CALL.fullmatch(text.strip())
    if match is None:
        raise ValueError("native tool call must be exactly one balanced XML action")
    tool_name = match.group(1)
    offered = [tool for tool in offered_tools if tool.get("name") == tool_name]
    if len(offered) != 1:
        raise ValueError("native tool was not uniquely offered")
    schema = offered[0].get("parameters")
    if type(schema) is not dict or type(schema.get("properties")) is not dict:
        raise ValueError("original native schema unavailable")
    props = schema["properties"]
    args: dict[str, Any] = {}
    params = match.group("params")
    position = 0
    while position < len(params):
        item = _PARAMETER.match(params, position)
        if item is None:
            if params[position:].strip():
                raise ValueError("malformed or unconsumed native argument XML")
            break
        key, raw = item.group(1), item.group(2)
        if key in args or key not in props:
            raise ValueError("duplicate or unoffered native argument")
        args[key] = _scalar_from_xml(raw, props[key])
        position = item.end()
    if not set(schema.get("required", [])).issubset(args):
        raise ValueError("missing required native argument")
    payload = json.dumps(
        {"name": tool_name, "arguments": args},
        ensure_ascii=False, allow_nan=False, separators=(",", ":"),
    )
    canonical = "<tool_call>" + payload + "</tool_call>"
    if tool_name != _RESERVED_SCHEMA_REQUEST:
        kind, value = parse_one_model_action(canonical)
        if kind != "tool" or value["route"] != tool_name.replace("__", ".", 1):
            raise ValueError("canonical strict grammar refused native call")
    return canonical, True


def canonical_to_qwen35_xml(text: str) -> str:
    """Restore assistant-native wire format for multi-turn model history only."""
    kind, value = parse_one_model_action(text)
    if kind != "tool":
        return text
    name = value["route"].replace(".", "__", 1)
    args = value["arguments"]
    lines = [f"<tool_call>\n<function={name}>"]
    for key, item in args.items():
        if type(item) is str:
            if "<" in item or ">" in item:
                raise ValueError("unrenderable native assistant history")
            representation = item
        else:
            representation = json.dumps(item, ensure_ascii=False, allow_nan=False)
        lines.extend((f"<parameter={key}>", representation, "</parameter>"))
    lines.extend(("</function>", "</tool_call>"))
    return "\n".join(lines)


class Qwen35XMLAdapter:
    """Optional E1 model-facing adapter. Source executor remains untouched."""

    def __init__(self, native_agent: Any) -> None:
        if not callable(getattr(native_agent, "generate", None)):
            raise ValueError("native model generator required")
        self.native_agent = native_agent

    def generate(
        self, messages: list[dict[str, str]], tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        native_messages = [
            {**row, "content": (
                canonical_to_qwen35_xml(row["content"])
                if row["role"] == "assistant" else row["content"]
            )}
            for row in messages
        ]
        result = self.native_agent.generate(native_messages, tools)
        if type(result) is not dict or type(result.get("text")) is not str:
            raise ValueError("invalid native generation envelope")
        normalized, _ = normalize_qwen35_xml_action(
            result["text"], offered_tools=tools,
        )
        return {**result, "text": normalized}

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersistedDocumentLimits:
    """Safety envelope for one persisted JSON document before model decoding."""

    max_bytes: int = 8 * 1024 * 1024
    max_depth: int = 128
    max_nodes: int = 200_000

    def __post_init__(self) -> None:
        for name, value in (
            ("max_bytes", self.max_bytes),
            ("max_depth", self.max_depth),
            ("max_nodes", self.max_nodes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


class PersistedDocumentLimitError(ValueError):
    """Raised when persisted JSON exceeds its pre-decode safety envelope."""


def _utf8_width(character: str) -> int:
    codepoint = ord(character)
    if codepoint <= 0x7F:
        return 1
    if codepoint <= 0x7FF:
        return 2
    if codepoint <= 0xFFFF:
        return 3
    return 4


def validate_persisted_json_document(
    document: str,
    limits: PersistedDocumentLimits,
) -> None:
    """Bound encoded size and structural work without materializing parsed JSON.

    The scanner is intentionally not a JSON validator. Its only job is to reject
    documents whose raw size, nesting depth, or coarse structural token count would
    make subsequent JSON/Pydantic decoding disproportionately expensive. Malformed
    syntax that remains inside the budget is left to the normal decoder so existing
    domain-specific error handling stays intact.
    """

    encoded_bytes = 0
    depth = 0
    nodes = 0
    in_string = False
    escaped = False
    in_primitive = False

    for character in document:
        encoded_bytes += _utf8_width(character)
        if encoded_bytes > limits.max_bytes:
            raise PersistedDocumentLimitError(
                "persisted JSON exceeds the encoded byte limit"
            )

        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if in_primitive:
            if not character.isspace() and character not in ",]}:":
                continue
            in_primitive = False

        if character.isspace():
            continue
        if character == '"':
            nodes += 1
            if nodes > limits.max_nodes:
                raise PersistedDocumentLimitError(
                    "persisted JSON exceeds the structural node limit"
                )
            in_string = True
            continue
        if character in "[{":
            nodes += 1
            if nodes > limits.max_nodes:
                raise PersistedDocumentLimitError(
                    "persisted JSON exceeds the structural node limit"
                )
            depth += 1
            if depth > limits.max_depth:
                raise PersistedDocumentLimitError(
                    "persisted JSON exceeds the nesting depth limit"
                )
            continue
        if character in "]}":
            if depth > 0:
                depth -= 1
            continue
        if character in ",:":
            continue

        nodes += 1
        if nodes > limits.max_nodes:
            raise PersistedDocumentLimitError(
                "persisted JSON exceeds the structural node limit"
            )
        in_primitive = True

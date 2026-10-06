from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from .models import StrictModel

if TYPE_CHECKING:
    from .runs import RunEvent

_REDACTED = "[REDACTED]"
_DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "card_number",
        "client_secret",
        "cookie",
        "credit_card",
        "cvv",
        "password",
        "passwd",
        "private_key",
        "refresh_token",
        "secret",
        "session_id",
        "set_cookie",
        "social_security_number",
        "ssn",
        "token",
    }
)
_MAX_REDACTION_DEPTH = 48
_MAX_REDACTION_NODES = 20_000
_MAX_SECRET_LITERALS = 256
_MAX_SECRET_LITERAL_BYTES = 32 * 1024

_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"access[_-]?token|api[_-]?key|authorization|client[_-]?secret|"
    r"cookie|password|passwd|private[_-]?key|refresh[_-]?token|secret|token"
    r")(\s*[:=]\s*)([^\s,;]+)"
)


def _normalize_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _normalize_path(value: str) -> str:
    return ".".join(part.strip().casefold() for part in value.split(".") if part.strip())


def _path_text(parts: Sequence[str]) -> str:
    return ".".join(parts).casefold()


class TraceRedactionConfig(StrictModel):
    """Structured redaction policy applied before run events reach consumers or sinks."""

    sensitive_keys: set[str] = Field(
        default_factory=lambda: set(_DEFAULT_SENSITIVE_KEYS),
        max_length=128,
    )
    sensitive_paths: set[str] = Field(default_factory=set, max_length=256)
    replacement: str = Field(default=_REDACTED, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_redaction_config(self) -> TraceRedactionConfig:
        if any(not key.strip() or len(key) > 128 for key in self.sensitive_keys):
            raise ValueError("trace redaction keys must be non-empty and at most 128 characters")
        if any(not path.strip() or len(path) > 512 for path in self.sensitive_paths):
            raise ValueError("trace redaction paths must be non-empty and at most 512 characters")
        return self


class TraceRedactor:
    """Run-scoped deterministic redactor with bounded secret-value carryover."""

    def __init__(self, config: TraceRedactionConfig) -> None:
        self.config = config
        self._sensitive_keys = tuple(
            sorted(
                {
                    _normalize_key(key)
                    for key in config.sensitive_keys
                    if _normalize_key(key)
                },
                key=len,
                reverse=True,
            )
        )
        self._sensitive_paths = frozenset(
            normalized
            for path in config.sensitive_paths
            if (normalized := _normalize_path(path))
        )
        self._secret_literals: set[str] = set()
        self._secret_literal_bytes = 0

    def _matches_key(self, key: str) -> bool:
        normalized = _normalize_key(key)
        if not normalized:
            return False
        return any(
            normalized == sensitive or normalized.endswith(sensitive)
            for sensitive in self._sensitive_keys
        )

    def _matches_path(self, path: Sequence[str]) -> bool:
        return _path_text(path) in self._sensitive_paths

    @staticmethod
    def _consume_node(budget: list[int]) -> bool:
        if budget[0] <= 0:
            return False
        budget[0] -= 1
        return True

    def _remember_literal(self, value: str) -> None:
        if not 4 <= len(value) <= 4096 or value in self._secret_literals:
            return
        encoded_size = len(value.encode("utf-8", errors="ignore"))
        if (
            len(self._secret_literals) >= _MAX_SECRET_LITERALS
            or self._secret_literal_bytes + encoded_size > _MAX_SECRET_LITERAL_BYTES
        ):
            return
        self._secret_literals.add(value)
        self._secret_literal_bytes += encoded_size

    def _remember_scalars(
        self,
        value: Any,
        *,
        depth: int,
        budget: list[int],
    ) -> None:
        if depth >= _MAX_REDACTION_DEPTH or not self._consume_node(budget):
            return
        if isinstance(value, str):
            self._remember_literal(value)
            return
        if isinstance(value, Mapping):
            for nested in value.values():
                self._remember_scalars(
                    nested,
                    depth=depth + 1,
                    budget=budget,
                )
            return
        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
        ):
            for nested in value:
                self._remember_scalars(
                    nested,
                    depth=depth + 1,
                    budget=budget,
                )

    def _collect_sensitive_values(
        self,
        value: Any,
        *,
        path: tuple[str, ...],
        depth: int,
        budget: list[int],
    ) -> None:
        if depth >= _MAX_REDACTION_DEPTH or not self._consume_node(budget):
            return
        if self._matches_path(path):
            self._remember_scalars(
                value,
                depth=depth,
                budget=budget,
            )
            return

        if isinstance(value, Mapping):
            for raw_key, nested in value.items():
                key = str(raw_key)
                child_path = (*path, key)
                if self._matches_key(key) or self._matches_path(child_path):
                    self._remember_scalars(
                        nested,
                        depth=depth + 1,
                        budget=budget,
                    )
                else:
                    self._collect_sensitive_values(
                        nested,
                        path=child_path,
                        depth=depth + 1,
                        budget=budget,
                    )
            return

        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
        ):
            child_path = (*path, "[]")
            for nested in value:
                self._collect_sensitive_values(
                    nested,
                    path=child_path,
                    depth=depth + 1,
                    budget=budget,
                )

    def _redact_string(self, value: str) -> str:
        redacted = value
        for secret in sorted(self._secret_literals, key=len, reverse=True):
            if secret in redacted:
                redacted = redacted.replace(secret, self.config.replacement)

        redacted = _BEARER_RE.sub(
            lambda match: match.group(0).split(None, 1)[0]
            + " "
            + self.config.replacement,
            redacted,
        )
        redacted = _ASSIGNMENT_RE.sub(
            lambda match: (
                match.group(1)
                + match.group(2)
                + self.config.replacement
            ),
            redacted,
        )
        return redacted

    def _redact(
        self,
        value: Any,
        *,
        path: tuple[str, ...],
        depth: int,
        budget: list[int],
    ) -> Any:
        if self._matches_path(path):
            return self.config.replacement
        if depth >= _MAX_REDACTION_DEPTH or not self._consume_node(budget):
            return self.config.replacement

        if isinstance(value, Mapping):
            redacted: dict[str, Any] = {}
            for raw_key, nested in value.items():
                key = str(raw_key)
                child_path = (*path, key)
                if self._matches_key(key) or self._matches_path(child_path):
                    redacted[key] = self.config.replacement
                else:
                    redacted[key] = self._redact(
                        nested,
                        path=child_path,
                        depth=depth + 1,
                        budget=budget,
                    )
            return redacted

        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
        ):
            child_path = (*path, "[]")
            return [
                self._redact(
                    nested,
                    path=child_path,
                    depth=depth + 1,
                    budget=budget,
                )
                for nested in value
            ]

        if isinstance(value, str):
            return self._redact_string(value)

        return value

    def redact_event(self, event: RunEvent) -> RunEvent:
        """Return a detached event redacted before it is emitted or persisted."""

        collection_budget = [_MAX_REDACTION_NODES]
        self._collect_sensitive_values(
            event.metadata,
            path=("metadata",),
            depth=0,
            budget=collection_budget,
        )
        self._collect_sensitive_values(
            event.data,
            path=("data",),
            depth=0,
            budget=collection_budget,
        )

        redaction_budget = [_MAX_REDACTION_NODES]
        return event.model_copy(
            update={
                "metadata": self._redact(
                    event.metadata,
                    path=("metadata",),
                    depth=0,
                    budget=redaction_budget,
                ),
                "data": self._redact(
                    event.data,
                    path=("data",),
                    depth=0,
                    budget=redaction_budget,
                ),
            },
            deep=True,
        )

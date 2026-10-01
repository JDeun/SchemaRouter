from __future__ import annotations

from collections.abc import Mapping

_SCHEMA_HTTP_VALIDATORS_KEY = "schema_http_validators"
_SCHEMA_HTTP_VALIDATOR_SOURCE_KEY = "schema_http_validator_source"
_MAX_ETAG_CHARS = 1024
_MAX_LAST_MODIFIED_CHARS = 256


def _safe_header_value(value: object, *, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > max_chars:
        return None
    if "\r" in stripped or "\n" in stripped:
        return None
    return stripped


def normalize_schema_http_validators(
    value: object,
) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}

    result: dict[str, str] = {}
    etag = _safe_header_value(value.get("etag"), max_chars=_MAX_ETAG_CHARS)
    if etag is not None:
        result["etag"] = etag

    last_modified = _safe_header_value(
        value.get("last_modified"),
        max_chars=_MAX_LAST_MODIFIED_CHARS,
    )
    if last_modified is not None:
        result["last_modified"] = last_modified
    return result


def schema_http_validators_from_headers(
    headers: Mapping[str, str],
    *,
    fallback: object = None,
) -> dict[str, str]:
    result = normalize_schema_http_validators(fallback)

    etag = _safe_header_value(headers.get("etag"), max_chars=_MAX_ETAG_CHARS)
    if etag is not None:
        result["etag"] = etag

    last_modified = _safe_header_value(
        headers.get("last-modified"),
        max_chars=_MAX_LAST_MODIFIED_CHARS,
    )
    if last_modified is not None:
        result["last_modified"] = last_modified
    return result


def conditional_schema_headers(
    headers: Mapping[str, str] | None,
    validators: object,
) -> dict[str, str] | None:
    output = {
        key: value
        for key, value in dict(headers or {}).items()
        if key.lower() not in {"if-none-match", "if-modified-since"}
    }
    normalized = normalize_schema_http_validators(validators)

    etag = normalized.get("etag")
    if etag is not None:
        output["If-None-Match"] = etag
        return output

    last_modified = normalized.get("last_modified")
    if last_modified is not None:
        output["If-Modified-Since"] = last_modified

    return output or None


def _normalize_source_identity_digest(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 64:
        return None
    normalized = value.lower()
    if any(character not in "0123456789abcdef" for character in normalized):
        return None
    return normalized


def attach_schema_http_validators(
    metadata: dict[str, object],
    validators: object,
    *,
    source_identity_digest: str | None = None,
) -> None:
    normalized = normalize_schema_http_validators(validators)
    source_digest = _normalize_source_identity_digest(source_identity_digest)
    if normalized:
        metadata[_SCHEMA_HTTP_VALIDATORS_KEY] = normalized
        if source_digest is not None:
            metadata[_SCHEMA_HTTP_VALIDATOR_SOURCE_KEY] = source_digest
        else:
            metadata.pop(_SCHEMA_HTTP_VALIDATOR_SOURCE_KEY, None)
    else:
        metadata.pop(_SCHEMA_HTTP_VALIDATORS_KEY, None)
        metadata.pop(_SCHEMA_HTTP_VALIDATOR_SOURCE_KEY, None)


def schema_http_validators_from_metadata(
    metadata: Mapping[str, object],
) -> dict[str, str]:
    return normalize_schema_http_validators(
        metadata.get(_SCHEMA_HTTP_VALIDATORS_KEY)
    )


def schema_http_validator_source_from_metadata(
    metadata: Mapping[str, object],
) -> str | None:
    return _normalize_source_identity_digest(
        metadata.get(_SCHEMA_HTTP_VALIDATOR_SOURCE_KEY)
    )

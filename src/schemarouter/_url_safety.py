from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

_REDACTED_INVALID_URL = "<redacted-invalid-url>"


def safe_provenance_url(value: str) -> str:
    """Return a credential-free http(s) URL suitable for logs and persisted provenance."""

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return _REDACTED_INVALID_URL

    if parsed.scheme not in {"http", "https"} or not hostname:
        return _REDACTED_INVALID_URL

    safe_host = f"[{hostname}]" if ":" in hostname else hostname
    safe_netloc = f"{safe_host}:{port}" if port is not None else safe_host
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))

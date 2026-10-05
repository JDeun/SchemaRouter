from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .errors import SchemaSourceError

NetworkResolver = Callable[[str, int], Awaitable[Iterable[str]]]

_DEFAULT_SCHEMES = frozenset({"http", "https"})
_METADATA_HOSTS = frozenset(
    {
        "instance-data.ec2.internal",
        "metadata.google.internal",
    }
)


class NetworkPolicyError(SchemaSourceError):
    """Raised when a remote destination violates the configured network policy."""


def _normalize_host(host: str) -> str:
    value = host.strip().rstrip(".")
    if not value:
        raise NetworkPolicyError("network destination host is empty")
    if "%" in value:
        # Zone identifiers and percent-encoded host tricks are intentionally rejected.
        raise NetworkPolicyError("network destination host uses an ambiguous encoding")
    try:
        return value.encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise NetworkPolicyError("network destination host is not valid IDNA") from exc


def _literal_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _is_public_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_private
    )


async def _system_resolver(host: str, port: int) -> tuple[str, ...]:
    try:
        results = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise NetworkPolicyError(
            "network destination could not be resolved for policy validation"
        ) from exc

    addresses: list[str] = []
    for result in results:
        sockaddr = result[4]
        if not sockaddr:
            continue
        address = str(sockaddr[0])
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise NetworkPolicyError(
            "network destination resolved to no usable addresses"
        )
    return tuple(addresses)


@dataclass(frozen=True)
class NetworkPolicy:
    """Host-controlled egress policy for URL-backed discovery and execution.

    trusted_internal() preserves SchemaRouter's historical ability to reach
    loopback/private services. public_only() is intended for URLs influenced
    by less-trusted input and rejects every resolved address that is not globally
    routable unless its hostname is explicitly allowlisted.

    Public-mode DNS validation happens immediately before each request/session.
    The standard HTTP clients still perform their own DNS lookup afterwards, so
    this check narrows SSRF exposure but cannot completely eliminate DNS rebinding
    without a transport that pins the validated resolution. Applications with a
    custom transport should supply a resolver with matching resolution semantics.
    """

    allow_non_global: bool = True
    allowed_hosts: frozenset[str] = frozenset()
    allowed_ports: frozenset[int] | None = None
    allowed_schemes: frozenset[str] = _DEFAULT_SCHEMES
    resolver: NetworkResolver | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        schemes = frozenset(
            str(value).strip().casefold()
            for value in self.allowed_schemes
            if str(value).strip()
        )
        if not schemes or not schemes.issubset(_DEFAULT_SCHEMES):
            raise ValueError(
                "network policy schemes must be a non-empty subset of http/https"
            )

        hosts = frozenset(_normalize_host(str(value)) for value in self.allowed_hosts)
        ports = self.allowed_ports
        if ports is not None:
            normalized_ports = frozenset(int(value) for value in ports)
            if any(port < 1 or port > 65535 for port in normalized_ports):
                raise ValueError("network policy ports must be between 1 and 65535")
            ports = normalized_ports

        object.__setattr__(self, "allowed_schemes", schemes)
        object.__setattr__(self, "allowed_hosts", hosts)
        object.__setattr__(self, "allowed_ports", ports)

    @classmethod
    def trusted_internal(
        cls,
        *,
        allowed_ports: Iterable[int] | None = None,
    ) -> NetworkPolicy:
        """Allow public and internal destinations while retaining URL sanity checks."""

        return cls(
            allow_non_global=True,
            allowed_ports=(
                None if allowed_ports is None else frozenset(allowed_ports)
            ),
        )

    @classmethod
    def public_only(
        cls,
        *,
        allowed_hosts: Iterable[str] = (),
        allowed_ports: Iterable[int] | None = None,
        resolver: NetworkResolver | None = None,
    ) -> NetworkPolicy:
        """Reject non-global destinations except explicitly allowlisted hosts."""

        return cls(
            allow_non_global=False,
            allowed_hosts=frozenset(allowed_hosts),
            allowed_ports=(
                None if allowed_ports is None else frozenset(allowed_ports)
            ),
            resolver=resolver,
        )

    def validate_url(self, url: str) -> tuple[str, int]:
        """Validate URL syntax and return the normalized host and effective port."""

        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise NetworkPolicyError("network destination URL is malformed") from exc

        scheme = parsed.scheme.casefold()
        if scheme not in self.allowed_schemes or hostname is None:
            raise NetworkPolicyError(
                "network destination must use an allowed absolute http(s) URL"
            )
        if parsed.username is not None or parsed.password is not None:
            raise NetworkPolicyError(
                "network destination URL must not contain credentials"
            )

        host = _normalize_host(hostname)
        effective_port = port if port is not None else (443 if scheme == "https" else 80)
        if self.allowed_ports is not None and effective_port not in self.allowed_ports:
            raise NetworkPolicyError(
                "network destination port is not allowed by policy"
            )

        if self.allow_non_global or host in self.allowed_hosts:
            return host, effective_port

        if host == "localhost" or host.endswith(".localhost") or host in _METADATA_HOSTS:
            raise NetworkPolicyError(
                "network destination is not allowed by the public-network policy"
            )

        literal = _literal_address(host)
        if literal is not None and not _is_public_address(literal):
            raise NetworkPolicyError(
                "network destination is not allowed by the public-network policy"
            )
        return host, effective_port

    async def authorize(self, url: str) -> None:
        """Authorize one destination immediately before network access."""

        host, port = self.validate_url(url)
        if self.allow_non_global or host in self.allowed_hosts:
            return

        literal = _literal_address(host)
        if literal is not None:
            # validate_url() already rejected non-global literals.
            return

        resolver = self.resolver or _system_resolver
        addresses = tuple(await resolver(host, port))
        if not addresses:
            raise NetworkPolicyError(
                "network destination resolved to no usable addresses"
            )
        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(str(raw_address))
            except ValueError as exc:
                raise NetworkPolicyError(
                    "network resolver returned an invalid address"
                ) from exc
            if not _is_public_address(address):
                raise NetworkPolicyError(
                    "network destination is not allowed by the public-network policy"
                )


TRUSTED_INTERNAL_NETWORK_POLICY = NetworkPolicy.trusted_internal()

from __future__ import annotations

from .system_one import SystemOneDecisionBackend


class JevDecisionBackend(SystemOneDecisionBackend):
    """TypeSafe Jev specialization of the generic System One backend.

    This class preserves the existing public API and metadata defaults while sharing
    the Jev-compatible wire-contract implementation with other System One providers.
    """

    provider_display_name = "Jev"
    install_extra = "jev"
    default_provider_name = "typesafe-system-one"
    default_model_name = "jev-latest"

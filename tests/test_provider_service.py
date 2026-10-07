from __future__ import annotations

from pathlib import Path

from schemarouter.provider_service import ProviderProfileService

ROOT = Path(__file__).resolve().parents[1]


def test_provider_profile_service_resolves_builtin_identity() -> None:
    service = ProviderProfileService()

    resolution = service.resolve("mp")

    assert resolution.provider_id == "materials-project"
    assert resolution.methods


def test_provider_profile_service_keeps_discovery_non_authoritative() -> None:
    service = ProviderProfileService()

    proposal = service.discover("google")

    assert proposal.status == "ambiguous"
    assert "google" not in service.registry.provider_ids()
    assert proposal.candidates


def test_runtime_delegates_provider_profile_lifecycle_to_service() -> None:
    runtime = (ROOT / "src" / "schemarouter" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "ProviderProfileService(" in runtime
    assert "built_in_provider_profile_registry(" not in runtime
    assert "_load_provider_profile_plugins" not in runtime

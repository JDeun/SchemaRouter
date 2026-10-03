import schemarouter


def test_typed_capability_workstream_public_surface_is_consolidated() -> None:
    expected = {
        "CapabilityGraphDrift",
        "CapabilityLineage",
        "CapabilityEligibilityExplanation",
        "CapabilityOperationalMetadata",
        "CapabilityFallbackEligibility",
        "CapabilityNegotiationResult",
        "CapabilityGraphSnapshot",
        "StateAwareCapabilityRetrieval",
    }

    assert expected <= set(schemarouter.__all__)
    assert all(hasattr(schemarouter, name) for name in expected)

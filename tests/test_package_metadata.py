from schemarouter import __version__


def test_installed_version_is_exposed() -> None:
    assert __version__ == "0.2.0a1"

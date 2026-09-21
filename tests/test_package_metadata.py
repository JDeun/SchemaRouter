from importlib.metadata import version

from schemarouter import __version__


def test_installed_version_is_exposed() -> None:
    assert __version__ == version("schemarouter")

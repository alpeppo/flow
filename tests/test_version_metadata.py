"""Version must be readable at runtime and match pyproject.toml."""

from pathlib import Path

import tomllib

from wnflow.config import __version__


def test_version_is_a_three_part_semver_string() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), f"non-numeric part in {__version__}"


def test_version_matches_pyproject_toml() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    assert __version__ == pyproject["project"]["version"]

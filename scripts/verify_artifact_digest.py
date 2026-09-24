from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def _artifact(root: Path, kind: str) -> Path:
    suffix = ".whl" if kind == "wheel" else ".tar.gz"
    candidates = sorted(root.glob(f"schemarouter-*{suffix}"))
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one {kind} artifact in {root}; found {candidates}"
        )
    return candidates[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_artifact_digest(
    built_dir: Path,
    published_dir: Path,
    artifact_kind: str,
) -> tuple[Path, str]:
    built = _artifact(built_dir, artifact_kind)
    published = _artifact(published_dir, artifact_kind)

    if built.name != published.name:
        raise ValueError(
            f"artifact filename mismatch: built={built.name!r}, "
            f"published={published.name!r}"
        )

    built_digest = _sha256(built)
    published_digest = _sha256(published)
    if built_digest != published_digest:
        raise ValueError(
            f"artifact SHA-256 mismatch for {built.name}: "
            f"built={built_digest}, published={published_digest}"
        )
    return built, built_digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify that a downloaded PyPI artifact matches the trusted release build."
    )
    parser.add_argument("--built-dir", type=Path, required=True)
    parser.add_argument("--published-dir", type=Path, required=True)
    parser.add_argument(
        "--artifact-kind",
        choices=("wheel", "sdist"),
        required=True,
    )
    args = parser.parse_args()

    try:
        artifact, digest = verify_artifact_digest(
            args.built_dir,
            args.published_dir,
            args.artifact_kind,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Verified PyPI artifact SHA-256: {artifact.name} {digest}")


if __name__ == "__main__":
    main()

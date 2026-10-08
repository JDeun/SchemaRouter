"""Preflight a protected SafeAct V1 Linux runner without calling a model.

The pinned upstream external agent demands bubblewrap, root-owned resource
limiters, a trusted Unix-domain model broker, and a real coding-agent CLI.
Never print authentication values, filesystem secrets, or broker locations.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
from pathlib import Path

BROKER_KEYS = (
    "SAFEACT_MODEL_BROKER_DIR",
    "SAFEACT_MODEL_BROKER_SOCKET",
    "SAFEACT_MODEL_BROKER_PORT",
)


def inspect_runner(*, backend: str, environ: dict[str, str] | None = None) -> dict:
    env = dict(os.environ if environ is None else environ)
    errors: list[str] = []
    if backend not in {"codex", "claude"}:
        errors.append("backend must be codex or claude")
    if env.get("SAFEACT_V1_RUNTIME_VERIFIED") != "1":
        errors.append("protected runner authorization not present")

    binaries = ["bwrap", "timeout", "prlimit"]
    if backend in {"codex", "claude"}:
        binaries.append(backend)
    for name in binaries:
        path = (
            env.get("SAFEACT_SANDBOX_RESOURCE_PATH")
            if name == "bwrap" else None
        ) or shutil.which(name)
        if not path:
            errors.append(f"required executable unavailable: {name}")
            continue
        try:
            actual = Path(path).resolve(strict=True)
            metadata = actual.stat()
            if not actual.is_file() or not os.access(actual, os.X_OK):
                errors.append(f"required executable not runnable: {name}")
            if name in {"bwrap", "timeout", "prlimit"} and (
                metadata.st_uid != 0 or metadata.st_mode & 0o022
            ):
                errors.append(f"untrusted resource binary ownership: {name}")
            if name in {"timeout", "prlimit"} and (
                actual != Path("/usr/bin") / name
            ):
                errors.append(f"upstream requires /usr/bin/{name}")
            if name == "bwrap" and actual.name != "bwrap":
                errors.append("sandbox executable basename must be bwrap")
        except (OSError, ValueError):
            errors.append(f"required executable path invalid: {name}")

    if any(not env.get(key) for key in BROKER_KEYS):
        errors.append("trusted model broker environment is incomplete")
    else:
        try:
            broker_dir = Path(env[BROKER_KEYS[0]]).resolve(strict=True)
            name = env[BROKER_KEYS[1]]
            port = int(env[BROKER_KEYS[2]])
            if (
                name != Path(name).name
                or not broker_dir.is_dir()
                or not (broker_dir / name).is_socket()
                or not 1 <= port <= 65535
            ):
                errors.append("trusted model broker socket/port is invalid")
        except (OSError, ValueError):
            errors.append("trusted model broker socket/port is invalid")
    return {
        "kind": "safeact_v1_protected_runner_preflight",
        "ready": not errors,
        "blockers": errors,
        "model_calls": 0,
        "broker_secret_values_exposed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    baseline = manifest["conditions"]["SAFEACT-UNGATED"]["agent_command"]
    tokens = shlex.split(baseline)
    backends = [
        token.partition("=")[2]
        for token in tokens if token.startswith("--backend=")
    ]
    backends.extend(
        tokens[i + 1] for i, value in enumerate(tokens[:-1])
        if value == "--backend"
    )
    if len(backends) != 1:
        raise ValueError("reviewed official backend must be declared exactly once")
    report = inspect_runner(backend=backends[0])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

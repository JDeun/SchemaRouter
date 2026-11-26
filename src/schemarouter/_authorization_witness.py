"""Private authorization-policy content witness shared by native routing proofs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .authorization import AuthorizationPolicy
from .errors import PolicyViolationError


def _policy_contents_digest(policy: AuthorizationPolicy) -> str:
    """Private digest of same-object RBAC, data scopes and compiled indexes.

    Frozen policy dataclasses still have mutable nested rule/index objects.
    This digest is never exposed as a selection receipt or model input.
    """
    try:
        if type(policy) is not AuthorizationPolicy:
            raise ValueError("invalid policy class")

        def index_rows(index: Any) -> list[dict[str, Any]]:
            if type(index.partitions) is not dict or type(index.rules) is not tuple:
                raise ValueError("invalid compiled authority index")
            rows: list[dict[str, Any]] = []
            for key, positions in index.partitions.items():
                if (
                    type(key) is not tuple or len(key) != 3
                    or any(value is not None and type(value) is not str for value in key)
                    or type(positions) is not tuple
                    or any(type(value) is not int or value < 0 for value in positions)
                ):
                    raise ValueError("invalid compiled authority entry")
                rows.append({"key": list(key), "positions": list(positions)})
            rows.sort(key=lambda row: json.dumps(row["key"]))
            return rows

        payload = {
            "default_effect": policy.default_effect,
            "rules": [asdict(rule) for rule in policy.rules],
            "data_rules": [asdict(rule) for rule in policy.data_rules],
            "compiled_rule_index": {
                "rules": [asdict(rule) for rule in policy._rule_index.rules],
                "partitions": index_rows(policy._rule_index),
            },
            "compiled_data_rule_index": {
                "rules": [asdict(rule) for rule in policy._data_rule_index.rules],
                "partitions": index_rows(policy._data_rule_index),
            },
        }
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (
        TypeError, ValueError, AttributeError,
        OverflowError, RecursionError, RuntimeError,
    ):
        raise PolicyViolationError(
            "cannot attest current authorization policy"
        ) from None
    return hashlib.sha256(encoded).hexdigest()

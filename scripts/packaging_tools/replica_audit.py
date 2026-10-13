"""Classify replica mismatches for read-only packaging review."""

from __future__ import annotations

import os
from typing import Any


_REPLICA_MISMATCH = "Replica differs from primary: "


def _path_key(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def classify_replica_errors(
    errors: list[str],
    manifest: Any,
) -> tuple[list[str], list[str]]:
    """Demote only positively associated writable-backup drift to warnings."""
    replica_roles: dict[str, tuple[str, bool]] = {}
    if isinstance(manifest, dict):
        replicas = manifest.get("replicas")
        if isinstance(replicas, list):
            for replica in replicas:
                if not isinstance(replica, dict) or not isinstance(replica.get("path"), str):
                    continue
                replica_roles[_path_key(replica["path"])] = (
                    str(replica.get("role", "")),
                    replica.get("associated") is True,
                )

    blocking: list[str] = []
    warnings: list[str] = []
    for error in errors:
        if not isinstance(error, str) or not error.startswith(_REPLICA_MISMATCH):
            blocking.append(str(error))
            continue
        path = error[len(_REPLICA_MISMATCH):]
        role = replica_roles.get(_path_key(path))
        if role == ("writable-backup", True):
            warnings.append(error)
        else:
            blocking.append(error)
    return blocking, warnings

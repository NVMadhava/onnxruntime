"""Shared deterministic helpers for ORT monitoring tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    repository = config.get("authoritative_repository")
    hosts = config.get("allowed_download_hosts")
    if not isinstance(repository, str) or "/" not in repository:
        raise RuntimeError("config authoritative_repository must have owner/name form")
    if not isinstance(hosts, list) or not hosts or not all(isinstance(host, str) for host in hosts):
        raise RuntimeError("config allowed_download_hosts must be a non-empty string array")
    return config


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def decision_sha256(path: Path) -> str:
    return sha256_file(path)


def semantic_manifest(decision: dict[str, Any]) -> dict[str, Any]:
    issue = decision.get("issue") or {}
    release = decision.get("release") or {}
    selected = decision.get("selected_artifacts") or []
    return {
        "issue": {
            "repository": issue.get("repository"),
            "number": issue.get("number"),
        },
        "release": {
            "version": release.get("version"),
            "candidate_revision": release.get("candidate_revision"),
        },
        "selected_artifacts": selected,
    }


def semantic_manifest_sha256(decision: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(semantic_manifest(decision))).hexdigest()


def project_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


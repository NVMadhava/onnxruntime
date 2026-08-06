#!/usr/bin/env python3
"""Validate persisted RC decisions, source snapshots, status, and lineage."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any
import urllib.parse

from common import PROJECT_ROOT, decision_sha256, load_config, sha256_file


DECISION_VALUES = {
    "source_trust": {"authoritative", "demo", "untrusted"},
    "lifecycle_status": {"active", "released", "superseded", "uncertain"},
    "disposition": {"actionable", "historical", "watch", "needs_human_review", "not_rc"},
    "confidence": {"high", "medium", "low"},
}


def _load_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        errors.append(f"{path}: cannot read JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path}: top-level value must be an object")
        return None
    return value


def _validate_url(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{location}: URL must be a string")
        return
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{location}: URL must use HTTPS")


def _validate_decision(path: Path, state_directory: Path, errors: list[str]) -> dict[str, Any] | None:
    decision = _load_object(path, errors)
    if decision is None:
        return None

    required = {
        "schema_version",
        "source_snapshot_sha256",
        "issue",
        "decision",
        "release",
        "evidence",
        "candidate_artifacts",
        "selected_artifacts",
        "ambiguities",
    }
    missing = required - decision.keys()
    if missing:
        errors.append(f"{path}: missing fields {sorted(missing)}")
        return decision

    issue = decision.get("issue")
    summary = decision.get("decision")
    release = decision.get("release")
    selected = decision.get("selected_artifacts")
    if not isinstance(issue, dict) or not isinstance(summary, dict) or not isinstance(release, dict):
        errors.append(f"{path}: issue, decision, and release must be objects")
        return decision
    if not isinstance(selected, list):
        errors.append(f"{path}: selected_artifacts must be an array")
        return decision

    for field, allowed in DECISION_VALUES.items():
        if summary.get(field) not in allowed:
            errors.append(f"{path}: decision.{field} must be one of {sorted(allowed)}")

    repository = issue.get("repository")
    number = issue.get("number")
    snapshot_digest = decision.get("source_snapshot_sha256")
    if isinstance(repository, str) and isinstance(number, int) and isinstance(snapshot_digest, str):
        snapshot = (
            state_directory
            / "sources"
            / f"{repository.replace('/', '__')}__{number}"
            / f"{snapshot_digest}.json"
        )
        if not snapshot.is_file():
            errors.append(f"{path}: referenced snapshot does not exist: {snapshot}")
        elif sha256_file(snapshot) != snapshot_digest:
            errors.append(f"{path}: referenced snapshot hash does not match its content")
    else:
        errors.append(f"{path}: invalid issue identity or source_snapshot_sha256")

    if summary.get("disposition") == "actionable":
        if summary.get("lifecycle_status") != "active":
            errors.append(f"{path}: actionable decision must have active lifecycle")
        for index, artifact in enumerate(selected):
            if not isinstance(artifact, dict) or not artifact.get("download_url"):
                errors.append(f"{path}: actionable selected_artifacts[{index}] needs download_url")

    for index, artifact in enumerate(selected):
        if not isinstance(artifact, dict):
            errors.append(f"{path}: selected_artifacts[{index}] must be an object")
            continue
        if "download_url" in artifact:
            _validate_url(artifact["download_url"], f"{path}: selected_artifacts[{index}]", errors)

    return decision


def validate_decision_file(path: Path, state_directory: Path) -> list[str]:
    errors: list[str] = []
    _validate_decision(path, state_directory, errors)
    return errors


def validate(root: Path) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    state_directory = root / "state"
    config = load_config(root / "config.json")
    decisions: dict[str, dict[str, Any]] = {}

    for path in sorted((state_directory / "decisions").rglob("*.json")):
        decision = _validate_decision(path, state_directory, errors)
        if decision is not None:
            decisions[path.relative_to(root).as_posix()] = decision

    status_count = 0
    for path in sorted((state_directory / "release-status").glob("*.json")):
        status_count += 1
        status = _load_object(path, errors)
        if status is None:
            continue
        decision_path = status.get("decision_path")
        if not isinstance(decision_path, str) or decision_path not in decisions:
            errors.append(f"{path}: decision_path does not reference a validated decision")
            continue
        full_decision_path = root / decision_path
        if status.get("decision_sha256") != decision_sha256(full_decision_path):
            errors.append(f"{path}: decision_sha256 is stale")
        if status.get("release_repository") != config["authoritative_repository"]:
            errors.append(f"{path}: release_repository differs from config")

    lineage_path = state_directory / "rc-lineage.json"
    lineage = _load_object(lineage_path, errors)
    if lineage is not None:
        if lineage.get("authoritative_repository") != config["authoritative_repository"]:
            errors.append(f"{lineage_path}: authoritative_repository differs from config")
        for field in ("latest_handled", "previous_handled", "active_unreleased_rc"):
            entry = lineage.get(field)
            if entry is None:
                continue
            if not isinstance(entry, dict) or entry.get("decision_path") not in decisions:
                errors.append(f"{lineage_path}: {field} has an invalid decision_path")

    return errors, {
        "decisions": len(decisions),
        "release_status_records": status_count,
        "lineage_records": 1 if lineage is not None else 0,
    }


def main() -> int:
    try:
        errors, counts = validate(PROJECT_ROOT)
    except (json.JSONDecodeError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if errors:
        print(json.dumps({"valid": False, "errors": errors, "counts": counts}, indent=2))
        return 1
    print(json.dumps({"valid": True, "errors": [], "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

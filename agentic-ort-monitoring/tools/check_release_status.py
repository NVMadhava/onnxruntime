#!/usr/bin/env python3
"""Collect authoritative final-release evidence for an RC decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


GITHUB_API = "https://api.github.com"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _request_release(repository: str, tag: str) -> dict[str, Any] | None:
    encoded_tag = urllib.parse.quote(tag, safe="")
    url = f"{GITHUB_API}/repos/{repository}/releases/tags/{encoded_tag}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "trt-rtx-agent-release-status/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub release request failed ({error.code}): {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GitHub release request failed: {error.reason}") from error


def collect_status(decision_path: Path, release_repository: str) -> dict[str, Any]:
    decision_bytes = decision_path.read_bytes()
    decision = json.loads(decision_bytes)
    release = decision.get("release") or {}
    version = release.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("decision does not contain a release version")

    tag = f"v{version}"
    github_release = _request_release(release_repository, tag)
    if github_release is None:
        observed_status = "no_final_release_observed"
        evidence_url = f"https://github.com/{release_repository}/releases/tag/{tag}"
        evidence = {
            "tag": tag,
            "url": evidence_url,
            "found": False,
        }
    else:
        is_final = not github_release["draft"] and not github_release["prerelease"]
        observed_status = "released" if is_final else "prerelease_or_draft"
        evidence = {
            "tag": github_release["tag_name"],
            "url": github_release["html_url"],
            "found": True,
            "draft": github_release["draft"],
            "prerelease": github_release["prerelease"],
            "published_at": github_release.get("published_at"),
            "target_commitish": github_release.get("target_commitish"),
        }

    return {
        "schema_version": 1,
        "decision_path": str(decision_path),
        "decision_sha256": hashlib.sha256(decision_bytes).hexdigest(),
        "release_repository": release_repository,
        "version": version,
        "candidate_revision": release.get("candidate_revision"),
        "observed_status": observed_status,
        "evidence": evidence,
        "interpretation_limit": (
            "A final release proves the RC is no longer active. Absence of a final GitHub "
            "release does not by itself prove that an RC is active."
        ),
    }


def save_status(status: dict[str, Any], state_directory: Path) -> Path:
    release_name = re.sub(r"[^A-Za-z0-9_.-]", "_", status["version"])
    destination = state_directory / "release-status" / f"{release_name}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_canonical_bytes(status))
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", required=True, type=Path)
    parser.add_argument("--release-repository", default="microsoft/onnxruntime")
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "state",
    )
    args = parser.parse_args()
    if not REPOSITORY_PATTERN.fullmatch(args.release_repository):
        parser.error("--release-repository must have owner/name form")
    return args


def main() -> int:
    args = parse_args()
    try:
        status = collect_status(args.decision, args.release_repository)
        destination = save_status(status, args.state_directory)
    except (json.JSONDecodeError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status_path": str(destination), **status}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

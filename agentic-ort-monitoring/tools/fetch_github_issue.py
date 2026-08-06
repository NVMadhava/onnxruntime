#!/usr/bin/env python3
"""Fetch a complete GitHub issue snapshot without making semantic decisions."""

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

from common import DEFAULT_CONFIG_PATH, canonical_bytes, load_config


GITHUB_API = "https://api.github.com"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _request_json(url: str) -> tuple[Any, dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "trt-rtx-agent-rc-discovery/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        remaining = error.headers.get("X-RateLimit-Remaining")
        reset = error.headers.get("X-RateLimit-Reset")
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub request failed ({error.code}) for {url}; "
            f"rate_limit_remaining={remaining}, rate_limit_reset={reset}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GitHub request failed for {url}: {error.reason}") from error


def _fetch_all_comments(repository: str, issue_number: int) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        url = f"{GITHUB_API}/repos/{repository}/issues/{issue_number}/comments?{query}"
        payload, _ = _request_json(url)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub comments response was not a list")

        comments.extend(
            {
                "id": comment["id"],
                "url": comment["html_url"],
                "author": comment["user"]["login"],
                "author_association": comment.get("author_association"),
                "created_at": comment["created_at"],
                "updated_at": comment["updated_at"],
                "body": comment.get("body") or "",
            }
            for comment in payload
        )
        if len(payload) < 100:
            return comments
        page += 1


def fetch_snapshot(repository: str, issue_number: int) -> dict[str, Any]:
    issue_url = f"{GITHUB_API}/repos/{repository}/issues/{issue_number}"
    issue, _ = _request_json(issue_url)
    if "pull_request" in issue:
        raise RuntimeError(f"{repository}#{issue_number} is a pull request, not an issue")

    return {
        "schema_version": 1,
        "repository": repository,
        "number": issue["number"],
        "url": issue["html_url"],
        "title": issue["title"],
        "state": issue["state"],
        "state_reason": issue.get("state_reason"),
        "author": issue["user"]["login"],
        "author_association": issue.get("author_association"),
        "created_at": issue["created_at"],
        "updated_at": issue["updated_at"],
        "closed_at": issue.get("closed_at"),
        "labels": sorted(label["name"] for label in issue.get("labels", [])),
        "body": issue.get("body") or "",
        "comments": _fetch_all_comments(repository, issue_number),
    }


def save_snapshot(snapshot: dict[str, Any], state_directory: Path) -> tuple[Path, str, bool]:
    content = canonical_bytes(snapshot)
    digest = hashlib.sha256(content).hexdigest()
    issue_directory = state_directory / "sources" / (
        f"{snapshot['repository'].replace('/', '__')}__{snapshot['number']}"
    )
    issue_directory.mkdir(parents=True, exist_ok=True)
    destination = issue_directory / f"{digest}.json"
    created = not destination.exists()
    if created:
        destination.write_bytes(content)
    return destination, digest, created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and content-address a complete public GitHub issue snapshot."
    )
    parser.add_argument("--repository")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument(
        "--state-directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "state",
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (json.JSONDecodeError, OSError, RuntimeError) as error:
        parser.error(str(error))
    args.repository = args.repository or config["authoritative_repository"]
    if not REPOSITORY_PATTERN.fullmatch(args.repository):
        parser.error("--repository must have owner/name form")
    if args.issue < 1:
        parser.error("--issue must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        snapshot = fetch_snapshot(args.repository, args.issue)
        path, digest, created = save_snapshot(snapshot, args.state_directory)
    except (RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "snapshot_path": str(path),
                "source_snapshot_sha256": digest,
                "created": created,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

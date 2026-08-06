#!/usr/bin/env python3
"""Download and safely extract artifacts selected by an agent decision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from common import (
    DEFAULT_CONFIG_PATH,
    PROJECT_ROOT,
    canonical_bytes,
    decision_sha256,
    load_config,
    project_relative,
    semantic_manifest_sha256,
    sha256_file,
)
from validate_state import validate_decision_file

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXTRACTED_BYTES = 4 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 50_000


def _validate_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError(f"artifact URL must use HTTPS: {url}")
    if parsed.username or parsed.password:
        raise RuntimeError("artifact URL must not contain credentials")
    if parsed.hostname.lower() not in allowed_hosts:
        raise RuntimeError(f"artifact host is not allowed: {parsed.hostname}")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        self._allowed_hosts = allowed_hosts
        super().__init__()

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        _validate_url(new_url, self._allowed_hosts)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _safe_component(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
    if not safe or safe in {".", ".."}:
        raise RuntimeError(f"value cannot form a safe path component: {value!r}")
    return safe


def _download(url: str, destination: Path, allowed_hosts: set[str]) -> tuple[str, int, str]:
    _validate_url(url, allowed_hosts)
    opener = urllib.request.build_opener(_SafeRedirectHandler(allowed_hosts))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "trt-rtx-agent-artifact-fetcher/0.1"},
    )
    temporary = destination.with_suffix(destination.suffix + ".partial")
    digest = hashlib.sha256()
    size = 0

    try:
        with opener.open(request, timeout=60) as response, temporary.open("wb") as output:
            final_url = response.geturl()
            _validate_url(final_url, allowed_hosts)
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(f"artifact exceeds {MAX_DOWNLOAD_BYTES} bytes")

            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError(f"artifact exceeds {MAX_DOWNLOAD_BYTES} bytes")
                digest.update(chunk)
                output.write(chunk)
    except (urllib.error.URLError, OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"artifact download failed: {error}") from error
    except RuntimeError:
        temporary.unlink(missing_ok=True)
        raise

    temporary.replace(destination)
    return digest.hexdigest(), size, final_url


def _validated_member_path(member: zipfile.ZipInfo) -> PurePosixPath:
    if "\\" in member.filename:
        raise RuntimeError(f"archive entry contains a backslash: {member.filename}")
    path = PurePosixPath(member.filename)
    if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise RuntimeError(f"unsafe archive entry path: {member.filename}")
    mode = member.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise RuntimeError(f"archive contains a symbolic link: {member.filename}")
    return path


def _extract_zip(archive: Path, destination: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    temporary = destination.with_name(f"{destination.name}.partial-{os.getpid()}")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)

    try:
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise RuntimeError(f"archive contains more than {MAX_ARCHIVE_ENTRIES} entries")
            total_size = sum(member.file_size for member in members)
            if total_size > MAX_EXTRACTED_BYTES:
                raise RuntimeError(f"archive expands beyond {MAX_EXTRACTED_BYTES} bytes")

            for member in members:
                relative = _validated_member_path(member)
                target = temporary.joinpath(*relative.parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                file_digest = hashlib.sha256()
                with package.open(member) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        file_digest.update(chunk)
                        output.write(chunk)
                inventory.append(
                    {
                        "path": relative.as_posix(),
                        "size": member.file_size,
                        "sha256": file_digest.hexdigest(),
                    }
                )
    except (zipfile.BadZipFile, OSError, RuntimeError):
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    if destination.exists():
        shutil.rmtree(destination)
    try:
        temporary.replace(destination)
    except PermissionError:
        # OneDrive and antivirus filters can briefly hold a directory handle on
        # Windows and reject an otherwise atomic directory rename. Preserve the
        # validated extraction by copying it to the final location instead.
        shutil.copytree(temporary, destination)
        shutil.rmtree(temporary, ignore_errors=True)
    return sorted(inventory, key=lambda entry: entry["path"])


def _export_dlls(
    decision: dict[str, Any],
    result: dict[str, Any],
    dll_output_directory: Path,
) -> dict[str, Any]:
    release = decision.get("release") or {}
    version = release.get("version")
    revision = release.get("candidate_revision")
    if not isinstance(version, str):
        raise RuntimeError("decision release version is required to export DLLs")
    release_name = _safe_component(f"{version}-{revision}" if revision else version)
    release_directory = dll_output_directory / release_name
    exports: list[dict[str, Any]] = []

    for artifact in result["artifacts"]:
        extraction_root = Path(artifact["extraction_path"])
        package_directory = release_directory / _safe_component(artifact["package"])
        for entry in artifact["files"]:
            relative = PurePosixPath(entry["path"])
            if relative.suffix.lower() != ".dll":
                continue
            source = extraction_root.joinpath(*relative.parts)
            destination = package_directory.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            exports.append(
                {
                    "package": artifact["package"],
                    "source_path": relative.as_posix(),
                    "exported_path": str(destination),
                    "size": entry["size"],
                    "sha256": entry["sha256"],
                }
            )

    export_result = {
        "release": release_name,
        "directory": str(release_directory),
        "dlls": sorted(exports, key=lambda entry: (entry["package"], entry["source_path"])),
    }
    release_directory.mkdir(parents=True, exist_ok=True)
    (release_directory / "dll-manifest.json").write_bytes(canonical_bytes(export_result))
    return export_result


def _find_reusable_artifact(
    output_directory: Path,
    package: str,
    version: str,
    requested_url: str,
) -> dict[str, Any] | None:
    for result_path in output_directory.glob("*/materialization.json"):
        try:
            prior_result = json.loads(result_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for artifact in prior_result.get("artifacts", []):
            archive_path = Path(artifact.get("archive_path", ""))
            if (
                artifact.get("package") == package
                and artifact.get("version") == version
                and artifact.get("requested_url") == requested_url
                and archive_path.is_file()
                and Path(artifact.get("extraction_path", "")).is_dir()
                and sha256_file(archive_path) == artifact.get("archive_sha256")
            ):
                return artifact
    return None


def materialize(
    decision_path: Path,
    output_directory: Path,
    allowed_hosts: set[str],
    allow_demo_source: bool = False,
    allow_non_active_release: bool = False,
    dll_output_directory: Path | None = None,
) -> dict[str, Any]:
    decision_bytes = decision_path.read_bytes()
    decision = json.loads(decision_bytes)
    decision_summary = decision.get("decision", {})
    disposition = decision_summary.get("disposition")
    if disposition != "actionable" and not (
        disposition == "historical" and allow_non_active_release
    ):
        raise RuntimeError("only actionable decisions may be materialized by default")
    lifecycle_status = decision_summary.get("lifecycle_status")
    if lifecycle_status != "active" and not allow_non_active_release:
        raise RuntimeError(
            "non-active RC requires the explicit --allow-non-active-release override"
        )
    source_trust = decision_summary.get("source_trust")
    if source_trust == "demo" and not allow_demo_source:
        raise RuntimeError("demo source requires the explicit --allow-demo-source override")
    if source_trust != "authoritative" and source_trust != "demo":
        raise RuntimeError("only authoritative or explicitly allowed demo sources may be materialized")
    selected = decision.get("selected_artifacts")
    if not isinstance(selected, list) or not selected:
        raise RuntimeError("agent decision has no selected artifacts")

    decision_digest = decision_sha256(decision_path)
    manifest_sha256 = semantic_manifest_sha256(decision)
    run_directory = output_directory / manifest_sha256
    result_path = run_directory / "materialization.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if dll_output_directory is not None:
            result = {
                **result,
                "dll_export": _export_dlls(decision, result, dll_output_directory),
            }
        return result

    run_directory.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for artifact in selected:
        url = artifact.get("download_url")
        if not isinstance(url, str):
            raise RuntimeError(f"selected artifact {artifact.get('package')!r} has no download_url")
        reusable = _find_reusable_artifact(
            output_directory,
            artifact["package"],
            artifact["version"],
            url,
        )
        if reusable is not None:
            results.append(reusable)
            continue
        name = _safe_component(f"{artifact['package']}-{artifact['version']}")
        archive = run_directory / f"{name}.nupkg"
        sha256, size, final_url = _download(url, archive, allowed_hosts)
        extraction_directory = run_directory / f"{name}-extracted"
        inventory = _extract_zip(archive, extraction_directory)
        results.append(
            {
                "package": artifact["package"],
                "version": artifact["version"],
                "requested_url": url,
                "final_url": final_url,
                "archive_path": str(archive),
                "archive_size": size,
                "archive_sha256": sha256,
                "extraction_path": str(extraction_directory),
                "files": inventory,
            }
        )

    result = {
        "schema_version": 1,
        "decision_path": project_relative(decision_path),
        "decision_sha256": decision_digest,
        "manifest_sha256": manifest_sha256,
        "source_trust": source_trust,
        "artifacts": results,
    }
    if dll_output_directory is not None:
        result["dll_export"] = _export_dlls(decision, result, dll_output_directory)
    result_path.write_bytes(canonical_bytes(result))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "state" / "artifacts",
    )
    parser.add_argument(
        "--dll-output-directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "extracted_ort_dlls",
        help="Directory receiving a release-organized copy of every downloaded DLL.",
    )
    parser.add_argument(
        "--allow-demo-source",
        action="store_true",
        help="Allow a demo fixture. Never use this in production.",
    )
    parser.add_argument(
        "--allow-non-active-release",
        action="store_true",
        help="Allow historical RC artifacts for an explicit comparison or demo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        validation_errors = validate_decision_file(args.decision, PROJECT_ROOT / "state")
        if validation_errors:
            raise RuntimeError("decision validation failed: " + "; ".join(validation_errors))
        allowed_hosts = {host.lower() for host in config["allowed_download_hosts"]}
        result = materialize(
            args.decision,
            args.output_directory,
            allowed_hosts,
            allow_demo_source=args.allow_demo_source,
            allow_non_active_release=args.allow_non_active_release,
            dll_output_directory=args.dll_output_directory,
        )
    except (json.JSONDecodeError, KeyError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

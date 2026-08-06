# Session Notes

## Mission

Build a human-in-the-loop agent system for `winai/trt-rtx-ep-abi` that:

- validates the EP against ORT release-candidate artifacts announced in GitHub
  issues;
- tracks upstream ORT pull requests for ABI and behavior impact;
- publishes evidence-backed GitLab issues and draft merge requests;
- implements approved changes and resolves actionable review feedback;
- leaves approval and merge exclusively to humans.

Agents make workflow decisions. Deterministic tools only fetch inputs, perform
builds and tests, validate downloads and policy, calculate checksums, scan for
secrets, and enforce idempotency.

## Current milestone

Discover ORT release candidates from complete GitHub issue content, identify
the applicable Windows SDK/runtime artifacts, download them safely, and emit
an auditable package manifest. ORT is not built from source.

The prototype is temporarily isolated under `agentic-ort-monitoring/` in the
local ONNX Runtime checkout. It should move to `winai/trt-rtx-ep-abi` before EP
build, GitLab, or implementation workflows are added.

The prototype is published to the `agentic-ort-monitoring` branch of
`https://github.com/NVMadhava/onnxruntime`. In this checkout, Git remote `fork`
points to that repository and `origin` remains the Microsoft upstream. Agent
changes must be pushed only to `fork`.

## Decisions

- RC recognition and package selection are semantic agent decisions, not
  title, regex, or fixed-section parsing.
- The agent reads issue title, body, comments, metadata, and edits when
  available. It records evidence, confidence, and ambiguity.
- Deterministic tooling may expose all links and download only an
  agent-selected artifact after host, checksum, and archive-safety checks.
- Deduplication key: GitHub issue number, inferred RC version, and canonical
  package-manifest hash.
- If an issue changes its artifacts, preserve the old manifest and create a
  new revision. Never silently replace the accepted baseline.
- `SESSION_NOTES.md` is the chronological project memory.
  `skills/rc-candidate-discovery/SKILL.md` contains reusable procedure and
  durable knowledge.

## Findings

### GitHub access

- GitHub CLI is installed at `C:/Program Files/GitHub CLI/gh.exe`; it is not
  currently on the shell `PATH`.
- GitHub authentication is available for development-time inspection.
- Production discovery should support a least-privilege token and public,
  read-only fallback with explicit rate-limit handling.
- Git clones and forks do not contain GitHub issues. Issues are GitHub-hosted
  records outside the Git object database. Local agent tests therefore use
  immutable JSON snapshots containing exact issue metadata, body, and comments.
- Fetching one issue is not subject to a 300-entry cap. Comments are paginated.
  GitHub search has a separate 1,000-result-per-query cap, which can be avoided
  for incremental synchronization by using update-time windows and pagination.

### ORT RC publication pattern observed

- Issue `microsoft/onnxruntime#29831`, created 2026-07-23, semantically
  announces ORT 1.28.0 release-candidate builds for validation.
- Its body provides a release branch plus Python and NuGet packages.
- Windows-native candidates are published through NuGet. The CPU package
  `Microsoft.ML.OnnxRuntime` version `1.28.0-rc.1` is a candidate for the base
  Windows x64 SDK/runtime needed to load a standalone EP.
- CUDA packages are also listed, but they should not be selected merely
  because the target EP uses NVIDIA hardware. The standalone EP host baseline
  and its documented ORT package requirement determine applicability.
- Issue comments can add availability limitations. For issue 29831, a comment
  reports incomplete public PyPI publication due to quota; this does not by
  itself invalidate the listed NuGet package.
- The exact issue and comments are stored locally under
  `state/sources/microsoft__onnxruntime__29831/`. Its canonical snapshot
  SHA-256 is
  `3fde04e83b437347056645e08dd6076273fbef70974df2e23f1427ad0cc90a41`.
- Semantic review selected `Microsoft.ML.OnnxRuntime` 1.28.0-rc.1 with medium
  confidence for the assumed Windows x64 native host role. It did not select
  the C# managed package or bundled CUDA/TensorRT provider package.
- The selected NuGet archive downloaded successfully. Size: 139,140,322 bytes.
  SHA-256:
  `636869d04be6f9fd058855f31e9b98857b909156d45ae0977d820e2cbef161f4`.
- The package contains the needed Windows x64 runtime assets:
  `onnxruntime.dll`, `onnxruntime.lib`,
  `onnxruntime_providers_shared.dll`, and
  `onnxruntime_providers_shared.lib`. It also contains native public headers,
  including `onnxruntime_ep_c_api.h`.
- `runtimes/win-x64/native/onnxruntime.dll` SHA-256 is
  `dae386283db9f9109b8a0e42da9fc7ff544406840f09d0a435d189dd3856bc05`.
- An unchanged rerun produced the same source snapshot with `created: false`
  and reused the same materialization decision and archive hashes.

### Fork issue demo

- Created `NVMadhava/onnxruntime#2` with the exact current title and body from
  upstream issue 29831. Title and body comparisons both passed; each body has
  SHA-256
  `531422d59fd6e60e1ac84bf08439b67ec35df4528aa6654fadb0340353076919`.
- GitHub cannot copy issue number, author, timestamps, reactions, edit history,
  or comment authors between repositories. The demo intentionally does not
  impersonate upstream commenters.
- The local demo snapshot SHA-256 is
  `36b96df5866fddb9736711773b2e02282dc6e526dd072cddbc8c2e59d299e536`.
- Provenance is a separate decision from semantic content. Production accepts
  RC announcements only from the configured authoritative repository,
  currently `microsoft/onnxruntime`. A copied issue is marked `demo` and is
  blocked unless the deterministic downloader receives an explicit
  `--allow-demo-source` override.
- With the demo override, the agent-selected NuGet package downloaded and
  extracted successfully. Its archive and Windows x64 DLL hashes exactly match
  the authoritative-issue run.
- OneDrive/Windows denied an atomic extraction-directory rename during the
  first demo run. The extractor now uses per-process staging directories and
  falls back to a validated copy when a filesystem filter blocks the rename.
- Downloaded archives and full extraction trees remain under the ignored
  `state/artifacts/` cache. Every DLL from the selected package is also copied
  into the ignored, release-organized `extracted_ort_dlls/` directory. For
  1.28.0-rc.1 this contains four DLLs across Windows x64 and ARM64.

### RC lifecycle and lineage

- An open RC issue does not mean the RC remains active. Lifecycle is checked
  independently against authoritative final releases.
- ORT v1.28.0 was published as a non-draft, non-prerelease final release on
  2026-07-25. Therefore 1.28.0-rc.1 is `released`/`historical`, despite issue
  29831 remaining open.
- ORT v1.27.0 was published as a final release on 2026-06-19. Its latest
  observed candidate was 1.27.0-rc.3, so that candidate is also historical.
- `state/rc-lineage.json` now records:
  - latest handled: `ORT 1.28.0-rc.1`;
  - previous handled: `ORT 1.27.0-rc.3`;
  - active unreleased RC: none.
- When a new authoritative, unreleased RC appears, it becomes the active/latest
  comparison side and 1.28.0-rc.1 becomes the previous comparison side.
- Historical RC artifacts are blocked by default and require an explicit
  comparison override. Materialization can reuse an already verified package
  across decision revisions instead of downloading duplicate bytes.

## Open questions

- Confirm whether `winai/trt-rtx-ep-abi` expects the CPU
  `Microsoft.ML.OnnxRuntime` package as `ONNXRUNTIME_ROOT`, or a different
  native SDK package/layout.
- Confirm required architectures. Current working assumption is Windows x64.
- Define how the production agent obtains an LLM runtime and model. The
  prototype initially uses the Cursor agent plus a project skill, keeping
  semantic reasoning out of deterministic scripts.
- Determine whether GitHub issue edit history must be fetched through GraphQL
  or whether saved source snapshots and `updated_at` are sufficient.

## Progress

- [x] Agreed on architecture boundary between agent decisions and tools.
- [x] Located the current ORT 1.28.0 RC issue and inspected its body/comments.
- [x] Create reusable RC discovery skill.
- [x] Implement source snapshot and safe artifact-download tools.
- [x] Produce and validate the first semantic decision and package manifest.
- [x] Download and inspect the selected Windows package.
- [x] Verify an unchanged rerun is idempotent.
- [x] Reproduce the RC issue in the fork and verify exact title/body content.
- [x] Enforce source provenance and complete an explicitly authorized demo
  download.
- [x] Export downloaded DLLs into `extracted_ort_dlls/`.
- [x] Detect that ORT 1.28 is final despite its open RC issue.
- [x] Record latest and previous handled RC versions for future comparison.
- [ ] Generalize remaining 1.28-specific prototype assumptions after the user
  confirms the demo is successful.
- [ ] Run the requested cleanup pass after demo confirmation.


# Session Notes

## Maintenance rule

Agents must read and continuously maintain both this file and
`skills/rc-candidate-discovery/SKILL.md`.

- Update this file after every meaningful finding, decision, blocker, state
  transition, or implementation change.
- Update the skill in the same change whenever reusable procedure, tool
  contracts, or durable domain knowledge changes.
- Version-specific evidence belongs here or in `state/`; reusable guidance
  belongs in the skill.
- If the files disagree, correct the skill first and then align these notes.

## Mission

Build a human-in-the-loop agent system for `winai/trt-rtx-ep-abi` that:

- validates the EP against published ORT RC SDK/runtime artifacts;
- tracks upstream ORT pull requests for ABI and behavioral impact;
- opens evidence-backed GitLab issues and draft merge requests;
- implements approved changes and resolves actionable review feedback;
- leaves approval and merge exclusively to humans.

Agents make semantic workflow decisions. Deterministic tools fetch evidence,
collect release metadata, validate state and download policy, checksum and
safely extract packages, run builds/tests, and enforce idempotency.

## Project status

The RC discovery/download demo succeeded on 2026-08-06. The implementation is
being generalized and cleaned for repeatable RC monitoring and the upcoming RC
comparison milestone.

Assets remain isolated under `agentic-ort-monitoring/` in this ONNX Runtime
checkout and are published to the `agentic-ort-monitoring` branch of
`NVMadhava/onnxruntime`. Git remote `fork` is the write target; `origin`
(`microsoft/onnxruntime`) remains read-only.

Move this directory to `winai/trt-rtx-ep-abi` before adding EP builds, GitLab
publishing, or implementation-agent workflows.

## Current configuration

`config.json` is the single policy source for:

- authoritative upstream repository;
- allowed download hosts;
- default target OS and architecture;
- demo completion state.

Do not duplicate these values in tools.

## Durable decisions

- RC recognition, applicability, source trust, package selection, and lifecycle
  are semantic agent decisions.
- Issue open/closed state is not RC lifecycle. A final authoritative release
  makes the RC historical even if its issue remains open.
- Copied issue text is not authoritative. Demo fixtures require an explicit
  override and production accepts only configured authoritative sources.
- Source snapshots are immutable and content-addressed.
- Artifact identity is the canonical semantic manifest of issue, release, and
  selected artifacts; mutable commentary must not orphan package caches.
- Archives, extraction trees, and exported DLLs remain ignored local outputs.
- Historical artifacts require an explicit comparison/replay override.

## Tool chain

1. `tools/fetch_github_issue.py` saves complete issue/comment snapshots.
2. The agent writes an evidence-backed semantic decision.
3. `tools/check_release_status.py` collects final-release evidence.
4. `tools/validate_state.py` verifies decisions, snapshots, status, and lineage.
5. `tools/materialize_artifacts.py` downloads, verifies, safely extracts, and
   exports an `ONNXRUNTIME_ROOT`-style `include/` + `lib/` layout.

## Successful demo evidence

### Upstream RC

- Authoritative issue: `microsoft/onnxruntime#29831`.
- Candidate: `ORT 1.28.0-rc.1`.
- Snapshot SHA-256:
  `3fde04e83b437347056645e08dd6076273fbef70974df2e23f1427ad0cc90a41`.
- Selected package: `Microsoft.ML.OnnxRuntime` 1.28.0-rc.1.
- Archive size: 139,140,322 bytes.
- Archive SHA-256:
  `636869d04be6f9fd058855f31e9b98857b909156d45ae0977d820e2cbef161f4`.
- Windows x64 `onnxruntime.dll` SHA-256:
  `dae386283db9f9109b8a0e42da9fc7ff544406840f09d0a435d189dd3856bc05`.
- Package inspection found public C/C++ headers, import libraries, and Windows
  x64/ARM64 DLLs.

### Fork fixture

- Demo issue: `NVMadhava/onnxruntime#2`.
- Its title and body exactly matched the upstream issue at copy time; body
  SHA-256:
  `531422d59fd6e60e1ac84bf08439b67ec35df4528aa6654fadb0340353076919`.
- GitHub cannot preserve issue number, author, timestamps, reactions, edit
  history, or comment authors across repositories; the demo did not impersonate
  commenters.
- The copied source was correctly classified as `demo`, blocked by default,
  and materialized only with explicit demo/historical overrides.

### Filesystem behavior

- Full package caches are under ignored `state/artifacts/`.
- Consumable SDK files are under ignored
  `extracted_ort_dlls/<version>-<candidate>/include/` and `lib/`.
- `include/` comes from NuGet's `build/native/include/`.
- `lib/` contains all files from the selected architecture's
  `runtimes/win-<arch>/native/`, including runtime DLLs and import libraries.
- The verified 1.28.0-rc.1 layout contains 15 headers and four x64 native
  files: `onnxruntime.dll`, `onnxruntime.lib`,
  `onnxruntime_providers_shared.dll`, and
  `onnxruntime_providers_shared.lib`.
- OneDrive/antivirus filters denied an atomic extraction-directory rename once;
  per-process staging plus validated copy fallback resolved it.
- NuGet-extracted paths may also carry Windows read-only attributes. SDK layout
  replacement clears those attributes with bounded retries before removing a
  stale export.

## RC lifecycle and comparison lineage

`state/rc-lineage.json` currently records:

- latest handled: `ORT 1.28.0-rc.1` — released/historical;
- previous handled: `ORT 1.27.0-rc.3` — released/historical;
- active unreleased RC: none.

Authoritative final releases:

- v1.28.0 published 2026-07-25;
- v1.27.0 published 2026-06-19.

When a new authoritative active RC appears, it becomes the new comparison side;
the prior `latest_handled` becomes the previous side.

## Confirmed findings

- Git clones/forks do not contain GitHub issues; local replay requires API
  snapshots.
- One issue plus all comments has no 300-entry cap. Comments are paginated.
  GitHub search has a separate 1,000-result-per-query cap.
- A GPU-targeting external EP does not automatically require ORT's bundled GPU
  provider package. Package choice depends on the standalone host contract.
- Public issue comments may correct package availability and must be included.
- NuGet packages can contain multiple architectures. SDK export selects the
  architecture recorded in the semantic artifact decision.

## Post-demo cleanup results

- `AGENTS.md`, this file, and the RC skill now mandate synchronized continuous
  maintenance.
- The skill is version-independent; ORT 1.28 details remain only as demo
  evidence/state.
- `config.json` centralizes repository, host, target, and demo policy.
- `tools/validate_state.py` validates three decisions, two release-status
  records, their source snapshots, and lineage.
- Materialization now uses semantic manifest identity. The demo manifest is
  `8115759f21303be5edf9724565df16ab9fc643ed5239f6f4fa3ef5206c21ec9c`.
- Cached archives are rehashed before reuse. A cache-hit rerun left
  `materialization.json` byte-for-byte unchanged.
- Release-status paths are normalized to repository-relative forward-slash
  paths.
- Legacy ignored cache directories remain available because the canonical demo
  record references their verified archive/extraction. They are not tracked
  source and can be migrated to a standalone content store later.

## Open questions

- Confirm the exact `ONNXRUNTIME_ROOT` package/layout expected by
  `winai/trt-rtx-ep-abi`.
- Confirm whether validation requires Windows x64 only.
- Select the production LLM runtime/model and authorization mechanism.
- Decide whether saved snapshots plus `updated_at` are sufficient or GitHub
  issue edit history is required.
- Resolve the historical 1.27 Azure feed artifact to a stable authorized
  download URL before comparing binaries.
- Add the policy gateway, secret scanning, and external-write controls before
  production deployment.

## Progress

- [x] Semantic RC discovery from complete issue context.
- [x] Source provenance and demo override enforcement.
- [x] Safe NuGet download, extraction, checksum inventory, and SDK export.
- [x] Final-release lifecycle detection independent of issue state.
- [x] Latest/previous RC lineage for future comparison.
- [x] Successful end-to-end fork issue demo.
- [x] Generalize reusable skill beyond ORT 1.28.
- [x] Make skill/session-note maintenance mandatory.
- [x] Complete state validation and semantic cache-identity cleanup.
- [x] Complete the requested post-demo documentation and prompt cleanup.
- [x] Export the selected ORT package as `include/` and `lib/` folders.
- [ ] Implement RC comparison after cleanup validation.


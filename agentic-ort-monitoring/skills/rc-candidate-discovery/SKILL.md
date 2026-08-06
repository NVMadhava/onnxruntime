---
name: rc-candidate-discovery
description: Semantically identifies ONNX Runtime release-candidate announcements in GitHub issues, selects applicable Windows SDK/runtime artifacts, and produces evidence-backed manifests. Use when discovering, comparing, downloading, or validating ORT RC packages for the TensorRT RTX EP ABI repository.
---

# ORT Release-Candidate Discovery

## Boundary

The agent decides:

- whether an issue announces a usable ORT release candidate;
- whether the source repository is authoritative, explicitly authorized for a
  demo, or untrusted;
- the inferred release and candidate revision;
- which artifacts are applicable to the target EP scenario;
- whether evidence is sufficient or requires human review.

Tools only fetch complete source content, preserve snapshots, list links,
validate selected URLs, checksum files, safely extract archives, and enforce
idempotency. Never replace semantic judgment with title keywords, regexes, or
assumptions about headings and layout.

## Inputs

Read:

1. The issue title, body, state, author, timestamps, labels, and complete
   comments.
2. Any prior source snapshot and decision for the same issue.
3. Target constraints: OS, architecture, package role, ORT baseline, and EP
   build requirements.
4. `../../../SESSION_NOTES.md` for current constraints and confirmed findings.

If source content is missing or truncated, do not decide. Fetch it again or
return `needs_human_review`.

Git clones and forks do not contain GitHub issues. For repeatable local tests,
first synchronize an issue into an immutable JSON snapshot, then make the
semantic decision from that snapshot.

## Semantic decision process

1. Determine the issue's intent from the complete context. Evidence of an RC
   may include an explicit request for prerelease validation, provisional
   package versions, a release branch, a release manager, or package
   installation instructions. These are examples, not required strings.
2. Distinguish an official announcement from a user question, bug report,
   downstream test request, or discussion that merely mentions an RC.
3. Verify provenance independently of issue content. Production ORT RC
   announcements must come from the configured authoritative repository,
   currently `microsoft/onnxruntime`. Copied text and valid package links do
   not make another repository authoritative. Mark a copied fixture as `demo`
   only when the caller explicitly authorizes demo mode.
4. Infer the release version and RC revision from mutually supporting
   evidence. Record conflicts instead of choosing silently.
5. Inventory every published artifact without selecting by section name.
   Understand package ecosystem, platform, architecture, provider, version,
   and role from surrounding prose and linked metadata.
6. Select only artifacts needed by the target EP validation scenario. Do not
   infer that a GPU-named host package is required merely because the EP uses
   a GPU.
7. Read comments for superseded packages, known publication failures,
   corrections, or limitations. A later correction takes precedence, but both
   sources remain in the evidence record.
8. Assign:
   - `high` confidence when intent, version, artifact identity, and
     applicability are supported without material conflict;
   - `medium` when the likely decision is clear but package role or revision
     has unresolved uncertainty;
   - `low` when evidence is incomplete or conflicting.
9. Set disposition:
   - `actionable` only when safe to create a manifest and download;
   - `watch` when publication is expected but no applicable build is ready;
   - `needs_human_review` for material ambiguity;
   - `not_rc` when the issue is not an RC announcement.

## Evidence requirements

Every conclusion must cite source locations using the issue URL or comment URL
and a short quotation or faithful summary. Include negative evidence and
ambiguities that could alter artifact selection.

Never expose private repository data, internal URLs, credentials, or
unreleased details in a public report.

## Decision output

Write a JSON decision that conforms to `../../schemas/rc-decision.schema.json`.
Keep agent explanation in fields intended for semantic evidence; do not add
free-form fields containing secrets or raw tokens.

For each selected artifact, include:

- exact package identity and version;
- source URL as published or derived from authoritative package metadata;
- target OS, architecture, configuration, and package role;
- why it is required;
- limitations;
- evidence references.

The downloader adds final URL, byte size, SHA-256, extracted file inventory,
and download timestamp. The agent must not invent these values.

An `authoritative` decision may be materialized normally. A `demo` decision
requires an explicit deterministic-tool override. Never materialize an
`untrusted` decision.

## Idempotency

Canonicalize the completed manifest and hash it with SHA-256. Use issue number,
inferred RC version, and manifest hash as the identity.

- Same source snapshot and same decision: return the existing result.
- Changed issue or comments: create a new source snapshot and reevaluate.
- Same artifact URL with changed bytes: quarantine it and require human review.
- Never overwrite an accepted baseline.

## Current package knowledge

ORT RC announcements have recently linked Windows native packages through
NuGet. A `Microsoft.ML.OnnxRuntime` package can contain the native CPU host
runtime and C/C++ SDK assets, while provider-specific packages have different
roles. Inspect actual package contents and target repository requirements
before selecting one.

Confirmed for `Microsoft.ML.OnnxRuntime` 1.28.0-rc.1:

- `build/native/include/` contains C and C++ API headers, including
  `onnxruntime_ep_c_api.h`;
- `runtimes/win-x64/native/` contains `onnxruntime.dll`, `onnxruntime.lib`,
  `onnxruntime_providers_shared.dll`, and its import library;
- the same NuGet archive contains other operating systems and architectures,
  so selection must identify the intended subdirectory instead of treating the
  whole package as Windows x64-only.

Do not encode current issue wording, package versions, or dates as discovery
rules.


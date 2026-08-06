---
name: rc-candidate-discovery
description: Semantically identifies ONNX Runtime release-candidate announcements, determines lifecycle and source trust, selects applicable SDK/runtime artifacts, and maintains evidence-backed comparison lineage. Use when discovering, downloading, validating, or comparing ORT RC packages for the TensorRT RTX EP ABI repository.
---

# ORT Release-Candidate Discovery

## Mandatory maintenance

Read this file, `../../SESSION_NOTES.md`, and `../../config.json` before work.
After every meaningful discovery, decision, blocker, or tool/workflow change:

1. update `SESSION_NOTES.md` with current evidence and project state;
2. update this skill with any durable, version-independent procedure or
   knowledge learned;
3. remove or correct stale guidance immediately.

Keep version-specific evidence in session notes and `state/`, not in reusable
procedure.

## Decision boundary

The agent decides:

- whether complete issue context represents an official RC announcement;
- whether the source is `authoritative`, explicitly authorized `demo`, or
  `untrusted`;
- release version, candidate revision, lifecycle, and confidence;
- which artifacts apply to the target standalone EP validation scenario;
- whether ambiguity requires human review.

Tools fetch and preserve inputs, collect release evidence, validate state,
enforce download policy, calculate checksums, safely extract archives, export
DLLs, and provide idempotency. Never replace semantic judgment with title
keywords, regex classification, or fixed issue sections.

## Workflow

### 1. Synchronize the complete issue

Run:

```text
python tools/fetch_github_issue.py --issue <number>
```

Override `--repository` only for an explicitly authorized fixture. The tool
stores an immutable, content-addressed snapshot containing title, body,
metadata, labels, and all paginated comments.

Git clones and forks do not contain GitHub issues. Agents reason from the saved
snapshot, not from repository files or truncated search results.

### 2. Make the semantic decision

Read the complete snapshot and:

1. Infer intent from the whole discussion. Requests for prerelease validation,
   provisional packages, release branches, managers, and installation
   instructions are supporting evidence, not required strings.
2. Distinguish an announcement from a user question, bug report, downstream
   test request, or incidental RC mention.
3. Verify provenance independently. Read the authoritative repository from
   `config.json`. Copied text and valid links do not establish authority.
4. Infer version and candidate revision from mutually supporting evidence.
   Preserve conflicts as ambiguities.
5. Inventory artifacts semantically by ecosystem, platform, architecture,
   provider, version, and role.
6. Select only artifacts required by the target EP. A GPU-named package is not
   automatically required merely because the external EP uses a GPU.
7. Apply later corrections or availability notices from comments without
   deleting older evidence.

Write a decision conforming to `../../schemas/rc-decision.schema.json`.

Confidence:

- `high`: intent, identity, applicability, and provenance have no material
  conflict;
- `medium`: likely decision is clear but a package role or revision remains
  uncertain;
- `low`: evidence is incomplete or conflicting.

Disposition:

- `actionable`: active candidate is safe to materialize;
- `historical`: released or superseded candidate retained for comparison;
- `watch`: announcement exists but no applicable artifact is ready;
- `needs_human_review`: material ambiguity remains;
- `not_rc`: context is not an RC announcement.

### 3. Determine lifecycle independently

Issue open/closed state is not lifecycle evidence. Run:

```text
python tools/check_release_status.py --decision <decision.json>
```

Then assign:

- `released` when an authoritative, published, non-draft, non-prerelease final
  release exists for the version;
- `superseded` when a newer candidate replaces it;
- `active` only with positive RC evidence and no final/superseding evidence;
- `uncertain` when checks are incomplete or conflicting.

Absence of a final GitHub release alone does not prove an RC is active.

### 4. Maintain comparison lineage

Keep `state/rc-lineage.json` aligned with validated decisions:

- `latest_handled`: newest distinct RC handled;
- `previous_handled`: the immediately prior distinct RC;
- `active_unreleased_rc`: newest authoritative active RC, or `null`;
- when a new active RC arrives, compare it with the prior `latest_handled`,
  then shift the lineage.

### 5. Validate state

Run:

```text
python tools/validate_state.py
```

Do not download or publish while validation errors remain.

### 6. Materialize selected artifacts

Run:

```text
python tools/materialize_artifacts.py --decision <decision.json>
```

An active authoritative decision needs no override. Demo sources require
`--allow-demo-source`. Released or superseded artifacts require
`--allow-non-active-release` for an explicit comparison or replay. Never
materialize an untrusted decision.

The tool:

- restricts HTTPS hosts using `config.json`;
- limits archive size and entries and rejects unsafe paths/symlinks;
- hashes archives and extracted files;
- reuses only locally revalidated cached artifacts;
- writes full artifacts under ignored `state/artifacts/`;
- copies all DLLs from the selected package into ignored
  `extracted_ort_dlls/<version>-<revision>/`.

## Evidence and safety

Every conclusion must cite an issue, comment, package, or release URL and a
short quotation or faithful summary. Record negative evidence and ambiguity.

Do not publish credentials, private repository data, internal-only URLs, raw
logs, or unreleased information. Public issue snapshots may be tracked only
when their contents are already public.

Selected artifacts require exact package identity, version, published URL,
target, role, selection reason, limitations, and evidence. An actionable
artifact also requires a resolvable HTTPS `download_url`.

## Idempotency

- Source snapshots are keyed by canonical snapshot SHA-256.
- Materializations are keyed by a canonical semantic manifest containing issue
  identity, release identity, and selected artifacts—not raw decision
  whitespace or mutable lifecycle commentary.
- A cache candidate is reused only when its archive exists and still matches
  the recorded SHA-256.
- Changed issue content creates a new snapshot and agent reevaluation.
- Remote-byte mutation can only be detected by a fresh download or an
  authoritative expected checksum; do not claim otherwise.
- Never silently replace an accepted baseline.

## Durable package knowledge

ORT RC announcements may publish native packages through NuGet or another
authorized feed. The base `Microsoft.ML.OnnxRuntime` package commonly contains
native host runtimes, import libraries, public C/C++ headers, and multiple
platform/architecture payloads. Managed and provider-specific packages serve
different roles.

Always inspect the selected archive and target repository contract. Preserve
architecture paths when exporting DLLs, and do not treat a multi-platform
archive as target-specific.


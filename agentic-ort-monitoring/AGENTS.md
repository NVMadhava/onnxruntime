# Agentic ORT Monitoring

Keep all ORT-monitoring agent assets inside this directory. Do not modify ONNX
Runtime source for this project.

## Mandatory maintenance rule

Read both `SESSION_NOTES.md` and
`skills/rc-candidate-discovery/SKILL.md` before continuing work.

After every meaningful discovery, decision, blocker, tool-contract change, or
workflow change, update both files in the same change:

- `SESSION_NOTES.md` records current state, chronology, evidence, and open work.
- `SKILL.md` records durable, version-independent procedure and knowledge.

Do not leave either file stale. If they disagree, correct the skill first and
then align the session notes. Version-specific observations belong in session
notes or state fixtures, not in the reusable skill.

## Operating rules

1. Agents make semantic decisions. Do not identify release candidates,
   applicability, lifecycle, or package intent using title keywords or fixed
   formatting.
2. Read configuration from `config.json`; do not duplicate repository or host
   policy in tools.
3. Preserve complete public source evidence and explain decisions with
   confidence and unresolved ambiguity.
4. Validate persisted state before downloading or publishing.
5. Keep credentials, archives, and extracted binaries out of source control.
6. External writes require explicit authorization. Production writes will
   eventually pass through a policy gateway; the current implementation only
   performs authorized GitHub demo writes and local state/download operations.

## Tool chain

1. `tools/fetch_github_issue.py` snapshots the complete issue and comments.
2. The agent reads the snapshot and writes a semantic decision.
3. `tools/check_release_status.py` collects authoritative final-release
   evidence; the agent assigns lifecycle status.
4. `tools/validate_state.py` checks decision/source/status/lineage consistency.
5. `tools/materialize_artifacts.py` downloads an approved artifact, verifies
   and safely extracts it, then exports an `include/` + `lib/` SDK layout under
   `extracted_ort_dlls/`.


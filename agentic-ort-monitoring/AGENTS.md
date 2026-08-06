# Agentic ORT Monitoring

Keep all prototype assets for ORT release-candidate monitoring inside this
directory. Do not modify ONNX Runtime source code for this prototype.

## Operating rules

1. Read `SESSION_NOTES.md` before continuing work and update it after each
   meaningful discovery, decision, blocker, or workflow change.
2. For release-candidate discovery, read
   `skills/rc-candidate-discovery/SKILL.md`.
3. Agents make semantic decisions. Do not identify release candidates,
   applicability, or package intent using title keywords or fixed formatting.
4. Deterministic tools may fetch complete source material, enumerate links,
   validate schemas and hosts, calculate checksums, safely extract archives,
   and enforce idempotency.
5. Preserve source evidence and explain every agent decision with confidence
   and unresolved ambiguity.
6. Keep credentials and downloaded binaries out of source-controlled outputs.
7. All external writes require a future policy-gateway authorization. The
   current milestone is read-only except for local files and downloads.


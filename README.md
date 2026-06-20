# governance

This repository provides non-authoritative reference implementations,
deterministic projectors, checks, and evidence materializers derived from
accepted authority sources.

It does not own accepted policy conditions, record-location authority, or
repo-local domain facts.

## Authority Boundary

- ADRs own accepted purposes, conditions, non-goals, and destructive cases.
- The SSOT registry owns exact record locations, replacements, and lifecycle.
- policy owns schemas, rules, and admission contracts.
- Each owning repository owns its package/build/runtime domain facts.
- governance tools may compute checks and projections, but their code and
  generated output are not normative authority.
- old `records/**` and `generated/**` content, while retained during migration,
  is frozen non-authority migration evidence and must not receive new writes.

Do not infer authority from this README, a path name, generated output, cache,
dashboard, or compatibility input name. Resolve it through the accepted ADR,
SSOT registry, and policy records.

## Layout

- `records/` - frozen migration source during cutover; not active authority
- `generated/` - frozen projection evidence during cutover; not active authority
- `tools/` - reference implementation/projector/check scripts
- `modules/` - Nix environment building blocks
- `issues/` - issue ledger records

## bootstrap consumable input

`packages.<system>.bootstrap-input` exposes `bootstrap-input.json`
(`governance.bootstrapInput.v1`) from the ADRS governance-records projection.
The bootstrap pinned-flake-input consumer reads `requiredSsot`, `specsOptional`,
and `outOfScope` from it. The `ssotLocations` URL slots are `null` (NOT YET
ACCEPTED): the consumer must not fabricate URLs from null.

## Provenance

This repository is the history-preserving merge of governance-records@eaefe95 +
governance-nix@683f0b3. Both source lineages remain present in git history.

# governance

Unified governance repository: accepted JSONL record authority plus its Nix-side
projection tooling, merged into a single repo with both histories preserved.

## Layout

- `records/` — 権威台帳 (accepted JSONL record authority; the SSOT for accepted definitions)
- `tools/` — projection 関数 (pure projection scripts: `make-spec-catalog.py`, `make-feat-input.py`, `check-package-facet-proof.py`)
- `modules/` — env 部品 (Nix environment building blocks, e.g. `common-worker-env.nix`)
- `generated/` — 射影出力 (projection outputs derived from `records/`; not definition authority)
- `issues/` — issue ledger records

### bootstrap consumable input

`packages.<system>.bootstrap-input` exposes
`generated/bootstrap-input/bootstrap-minimal-acceptance.json`
(`governance.bootstrapInput.v1`), the projection of the accepted record
`records/decisions/bootstrap-minimal-acceptance.v1.jsonl` produced by
`tools/make-bootstrap-input.py`. The bootstrap pinned-flake-input consumer reads
`requiredSsot` / `specsOptional` / `outOfScope` from it. The `ssotLocations` URL
slots are `null` (NOT YET ACCEPTED): no policy/ops SSOT URL is an accepted
governance definition, so the consumer must not fabricate URLs — see
`ssotLocationContract` in the projection. Drift is gated by the
`bootstrap-input-projection` flake check.

Generated/projection artifacts are never accepted definition authority; authority
lives exclusively in `records/`.

## Provenance

This repository is the history-preserving merge of
governance-records@eaefe95 + governance-nix@683f0b3
(governance-records branch `claude/gr-catalog-membership-260611` and
governance-nix branch `claude/governance-nix-catalog-bridge-260611`,
merged with `--allow-unrelated-histories`). Both source lineages remain
fully present in this repository's git history.

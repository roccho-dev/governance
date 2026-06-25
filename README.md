# governance

`governance` is the concrete `gov*` repository for non-authoritative, deterministic governance projection.

It is not a decision authority, accepted-definition record store, policy source, runtime executor, or merge/cutover approval surface.

## Purpose

`governance` provides deterministic, non-authority checks, projections, and
provider-adapter validation for repositories that choose to adopt governance
conventions through their own accepted path.

## Authority boundary

- `adrs` owns accepted decisions, purposes, responsibilities, rules, non-goals, waivers, and destructive cases.
- `governance` may compile, project, lint, and materialize evidence from accepted ADR bundles.
- `governance` must not own accepted-definition records or mint independent authority.
- `governance` must not mutate repositories, perform runtime promotion, approve merges, approve policy retirement, or restore `spec`/`specs` as authority.
- `ops` and owning feature repositories perform effectful execution and produce receipts.
- `spec` and `specs` are deprecated legacy evidence only, not authority inputs.

Do not infer authority from this README, a path name, generated output, cache, dashboard, or compatibility input name. Resolve authority through accepted ADR records and their digest-pinned projected bundle.

README.md is a checked artifact. It may be handwritten, partially managed, or
generated according to readme_mode. README.md is not an independent authority.

## Pure projection contract

Input:

- accepted ADR bundle
- schema version
- compiler/projector version
- target repository identity

Output:

- `governance.bundle.json`
- repo-scoped rule bundles such as `repos/<repo-id>.rules.json`
- package/catalog projections
- GitHub ruleset plans
- negative fixtures
- provenance and digest metadata

Required properties:

- deterministic
- explicit inputs only
- same input produces the same output digest
- fail closed on missing, stale, or unknown input
- trace ADR rule id to projection rule id to ops check id to receipt rule id
- side effects: none

## Inputs

- accepted ADR bundles and their digest-pinned projected inputs
- repo-local intent files such as `ci.intent.v1.jsonl`
- repo-local convention manifests such as `repo-convention.intent.v1.json`
- Nix inputs declared by `flake.nix`

## Outputs / artifacts

- deterministic check receipts from `nix flake check`
- provider CI adapter findings
- README artifact findings
- repo convention findings
- non-authority projection artifacts and compatibility packages

## Checks

The primary verification entrypoint is `nix flake check`.

Current checks include ADR input presence, no local records/generated trees, Nix
surface checks, ADRS shadow monitor selftests, provider CI YAML selftests, and
repo convention checks. `.github/workflows/*.yml` are checked-in provider
adapter artifacts. They are executable by GitHub, but they are not authority.
All GitHub provider workflows must be declared by `ci.intent.v1.jsonl`.

## Ownership / handoff

`governance` owns the implementation of convention checks. It does not accept
downstream repo policy by itself. Each downstream repo owns whether and how it
adopts governance checks, including severity and exceptions.

## Active tree layout

- `tools/` — reference pure projectors, compilers, checks, and linters
- `modules/` — Nix building blocks only when they support projection/check surfaces
- `issues/` — legacy issue-ledger evidence, not decision authority
- `MIGRATION_SOURCE.md` — deletion boundary note for removed local records/generated content

The active tree must not contain local `records/` or `generated/` directories. Historical data remains available through Git history and accepted ADR-derived projection bundles.

## Removed local authority/cache trees

`records/` and `generated/` were removed from the active governance tree.

They are not active authority and not active cache. Future consumers must read digest-pinned ADR-derived governance bundles, not `governance/records` or `governance/generated`.

Reintroducing local `records/` or `generated/` requires a new accepted ADR and must fail CI by default.

## bootstrap consumable input

`packages.<system>.bootstrap-input` exposes `bootstrap-input.json` (`governance.bootstrapInput.v1`) from the ADR-derived governance projection input, not from local `records/` or local `generated/`.

The bootstrap pinned-flake-input consumer reads `requiredSsot`, `specsOptional`, and `outOfScope` from that digest-pinned projection. `ssotLocations` URL slots remain `null` until accepted by ADR-derived authority; consumers must not fabricate URLs from null.

## Provenance

This repository is the history-preserving merge of governance-records@eaefe95 and governance-nix@683f0b3. Both source lineages remain present in Git history. Their former local record/projection trees are historical evidence only after this proposal.

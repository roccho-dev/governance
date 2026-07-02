# governance

`governance` is the concrete `gov*` repository for non-authoritative, deterministic governance projection.

It translates accepted ADRS decisions into repo/package-facing contracts, required assertions, required receipts, actionable failure reports, and gate-adapter inputs.

It is not a decision authority, accepted-definition record store, policy source, runtime executor, or merge/cutover approval surface.

This README is a human-readable projection surface. It is not independent authority.

## Purpose

`governance` exists so downstream repos and packages can follow accepted ADRS decisions without reading ADRS prose by hand.

It does this by:

- projecting accepted ADRS decisions into package-facing contracts;
- requiring package assertions against those contracts;
- requiring CI receipts for those assertions;
- joining ADRS grants, package assertions, receipts, provider CI state, and governance admission;
- explaining drift with expected state, actual state, delta, likely owner, and next action;
- converging final merge authority toward an active-only final-scope join after explicit cutover.

## Authority boundary

- `adrs` owns accepted decisions, purposes, responsibilities, rules, non-goals, waivers, and exceptional cases.
- `governance` may compile, project, lint, diagnose, and materialize evidence from accepted ADRS bundles.
- `governance` must not own accepted-definition records or mint independent authority.
- `governance` must not directly change target repositories, perform runtime promotion, approve merges, approve retirement, or make legacy `spec`/`specs` authoritative.
- `ops` and owning feature repositories perform effectful execution and produce receipts.
- `spec` and `specs` are deprecated legacy evidence only, not authority inputs.

Do not infer authority from this README, a path name, generated output, cache, dashboard, artifact, fixture, or compatibility input name. Resolve authority through accepted ADR records and their digest-pinned projected bundle.

README.md is a checked artifact and a checked projection artifact. It may be handwritten, partially managed, or generated according to `readme_mode`. README.md is not an independent authority.

## Final-scope purpose join

The target final merge gate is:

```text
gov-final-scope-purpose-join / gate
```

The target pass condition is:

```text
accepted ADRS grant
  x package assertion
  x CI receipt
  x governance admission
  = organization-active only
```

This gate is not branch-protection authority until explicit cutover and a same-name green run exist.

A standalone package check, artifact export, report generator, compiler selftest, shadow report, or `nix flake check` green result is not final ADRS compliance unless it is consumed by the final join.

## Feature repo contract

Feature and package repos answer ADRS-derived obligations with assertions and receipts.

A package should be able to use governance output without reading ADRS prose by hand:

| Governance output | Package/repo action |
|---|---|
| required claim template | assert the package responsibility |
| missing claim finding | add or route the missing assertion |
| stale claim finding | update the assertion to the current decision digest |
| missing receipt finding | produce the required check/evidence receipt |
| provider CI finding | fix stale/manual/undeclared provider CI surface |
| residual finding | return incomplete work instead of hiding it |
| `nextAction` | take the smallest action toward `organization-active` |

Blocking findings should include `packageId`, `contractId`, `adrsRef`, `expected`, `actual`, `delta`, `diagnosticClass`, `likelyOwner`, `nextAction`, `decisionDigest`, `assertionDigest`, and `receiptDigest`.

## README projection model

The repo root README is a map and boundary document.

Package-specific responsibility should live in package READMEs or package contracts, not in this root README.

Root README responsibilities:

- repo purpose;
- authority boundary;
- package index;
- current versus target state;
- final gate target;
- CI surface classification;
- repo non-goals;
- links to package README surfaces.

Package README responsibilities:

- package purpose;
- package responsibilities;
- public contract;
- required assertion;
- required receipt;
- entrypoints;
- dependency boundary;
- non-goals;
- residual handling;
- ADRS references and digests.

## Package index

This repository is a management surface for governance packages and projection/check tools.

Package responsibility is no longer only described by the root README. Current package-like surfaces have package README entrypoints, and future work may split finer-grained tool/package READMEs as needed.

| Area | Role | README responsibility |
|---|---|---|
| [`tools/`](tools/README.md) | reference projectors, compilers, checks, and linters | defines tool/package purpose, inputs, outputs, assertions, receipts, and non-goals |
| [`modules/`](modules/README.md) | Nix building blocks for projection/check surfaces | defines accepted usage, dependency boundaries, and receipt expectations |
| `issues/` | legacy issue-ledger evidence | must remain evidence only, not decision authority |
| `MIGRATION_SOURCE.md` | deletion boundary note for removed local records/generated content | explains migration evidence, not active authority |

## README projection receipts

This repository includes README projection receipts under [`docs/readme-projection/`](docs/readme-projection/):

- [`docs/readme-projection/README.md`](docs/readme-projection/README.md) explains the receipt role;
- [`docs/readme-projection/readmeProjectionReceipt.jsonl`](docs/readme-projection/readmeProjectionReceipt.jsonl) records receipt rows for root README, `tools/README.md`, and `modules/README.md`;
- [`docs/readme-projection/final-scope-readme-integration.md`](docs/readme-projection/final-scope-readme-integration.md) defines how README drift enters the final-scope report.

These receipts are evidence only. They do not make README authority and do not make README projection green a final merge pass.

## Gov package output

`packages.<system>.gov-package-output` exposes the repo-local `govPackageOutput.v1` packet for this repository.

`checks.<system>.gov-package-output` verifies that the packet contains the required files and minimum identity markers.

Packet files live under [`docs/gov-package-output/`](docs/gov-package-output/):

- `manifest.json`
- `repo.json`
- `packages.jsonl`
- `assertions.jsonl`
- `receipts.jsonl`
- `readmeProjectionReceipt.jsonl`
- `provider-ci.jsonl`
- `findings.jsonl`
- `admission.jsonl`

The packet is evidence for governance joins. It is not meaning authority and is not final merge authority unless consumed by `gov-final-scope-purpose-join / gate` after accepted cutover.

## CI surfaces

| Surface | Classification |
|---|---|
| `gov-final-scope-purpose-join / gate` | target final merge gate after cutover |
| package internal checks | receipt producers |
| package contract checks | receipt producers |
| provider CI YAML checks | final gate input or receipt producer |
| README artifact exporters | artifact producers, not final merge authority |
| explain/report generators | artifact producers, not final merge authority |
| compiler and fixture selftests | tool selftests, not final merge authority |
| standalone `nix flake check` | evidence producer unless consumed by final join |
| shadow reports | observation only, not merge authority |

## Current status versus target state

Current checks include ADR input presence, no local records/generated trees, Nix surface checks, ADRS shadow monitor selftests, provider CI YAML selftests, repo convention checks, claim/admission checks, gov package output checks, and artifact exporters.

These checks are useful, but they are transitional unless and until they are consumed by the final-scope join.

All GitHub provider workflows must be declared by `ci.intent.v1.jsonl`.

The target state is one final merge signal after explicit cutover:

```text
gov-final-scope-purpose-join / gate
```

Old CI surfaces should eventually become receipt producers, artifact producers, tool selftests, or final-join internal steps. They must not remain misleading final-green signals.

## Pure projection contract

Input:

- accepted ADR bundle
- schema version
- compiler/projector version
- target repository identity
- package assertions
- CI receipts
- provider CI state
- README projection receipts
- repo-local gov package output packets

Output:

- `governance.bundle.json`
- repo-scoped rule bundles such as `repos/<repo-id>.rules.json`
- package/catalog projections
- GitHub ruleset plans
- negative fixtures
- provenance and digest metadata
- final-scope purpose join reports
- projection receipts and findings
- README drift findings

Required properties:

- deterministic
- explicit inputs only
- same input produces the same output digest
- fail closed on missing, stale, or unknown input
- trace ADR rule id to projection rule id to ops check id to receipt rule id
- side effects: none

## Inputs

- accepted ADR bundles and their digest-pinned projected inputs
- repo/package assertions
- CI receipts
- provider CI state
- README projection receipts
- repo-local gov package output packets
- repo-local intent files such as `ci.intent.v1.jsonl`
- repo-local convention manifests such as `repo-convention.intent.v1.json`
- Nix inputs declared by `flake.nix`

## Outputs / artifacts

- deterministic check receipts from `nix flake check`
- provider CI adapter findings
- README projection findings
- README projection receipts
- repo convention findings
- package responsibility closure reports
- gov package output packets
- final-scope purpose join reports
- non-authority projection artifacts and compatibility packages

## Checks

The current primary verification entrypoint is `nix flake check`.

That does not make `nix flake check` the final merge authority. It is a high-level evidence producer until final-scope join cutover.

Current checks include ADR input presence, no local records/generated trees, Nix surface checks, ADRS shadow monitor selftests, provider CI YAML selftests, repo convention checks, claim/admission checks, gov package output checks, and artifact exporters.

`.github/workflows/*.yml` are checked-in provider adapter artifacts. They are executable by GitHub, but they are not authority. All GitHub provider workflows must be declared by `ci.intent.v1.jsonl`.

## Ownership / handoff

`governance` owns deterministic implementation of convention checks, projection checks, report generation, and final-gate adapter code.

It does not accept downstream repo policy by itself. Each downstream repo owns whether and how it adopts governance checks, including severity and exceptions, unless an accepted ADRS universe and cutover record says otherwise.

Effectful execution belongs to owning repos, ops, and provider control planes.

## Active tree layout

- `tools/` — reference pure projectors, compilers, checks, and linters
- `modules/` — Nix building blocks only when they support projection/check surfaces
- `issues/` — legacy issue-ledger evidence, not decision authority
- `docs/readme-projection/` — README projection receipts and final-scope integration contract
- `docs/gov-package-output/` — repo-local `govPackageOutput.v1` packet
- `MIGRATION_SOURCE.md` — deletion boundary note for removed local records/generated content

The active tree must not contain local `records/` or `generated/` directories. Historical data remains available through Git history and accepted ADR-derived projection bundles.

## Removed local authority/cache trees

`records/` and `generated/` were removed from the active governance tree.

They are not active authority and not active cache. Future consumers must read digest-pinned ADR-derived governance bundles, not `governance/records` or `governance/generated`.

Reintroducing local `records/` or `generated` requires a new accepted ADR and must fail CI by default.

## bootstrap consumable input

`packages.<system>.bootstrap-input` exposes `bootstrap-input.json` (`governance.bootstrapInput.v1`) from the ADR-derived governance projection input, not from local `records` or local `generated`.

The bootstrap pinned-flake-input consumer reads `requiredSsot`, `specsOptional`, and `outOfScope` from that digest-pinned projection. `ssotLocations` URL slots remain `null` until accepted by ADR-derived authority; consumers must not fabricate URLs from null.

## Non-goals

`governance` must not:

- become accepted meaning authority;
- treat feature wishes as ADRS grants;
- treat README, artifacts, screenshots, or generated output as authority;
- treat shadow reports as merge authority;
- treat standalone green checks as final ADRS compliance;
- directly change target repos;
- approve branch protection cutover without an accepted cutover decision;
- hide residual work;
- move package-specific responsibility back into root README once package README rollout exists.

## Provenance

This repository is the history-preserving merge of governance-records@eaefe95 and governance-nix@683f0b3. Both source lineages remain present in Git history. Their former local record/projection trees are historical evidence only after this proposal.

## ADRS provenance

This README projection is based on ADRS contracts merged through:

- `roccho-dev/adrs#105` — governance final-scope purpose join
- `roccho-dev/adrs#106` — README projection plane and gov package output plane

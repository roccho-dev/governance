# repo-governance

`repo-governance` is the core+port lib package for common repo and package governance.

It is a non-authority implementation of accepted ADR semantics. It does not decide rules; it projects and checks rules accepted by `adrs`.

## Goal

Given an accepted ADR bundle and an explicit repo snapshot, return deterministic data for repo contracts, package contracts, violations, explanations, generated README/docs content, migration plans, provenance, and digest metadata.

## No-goals

- no file writes
- no console or exit-code behavior
- no live network access
- no hidden clock or environment input
- no remote repo mutation
- no secret access
- no independent authority
- no runtime effect execution

## Shape

- `core`: pure project, check, explain, plan, and docs functions
- `port`: input, output, violation, and result data contracts

Adapters are outside this package.

## Initial rule modules

- repo-is-packages
- core-port-is-lib
- adapter-placement
- dependency-direction
- goal-no-goal
- generated-non-authority
- readme-contract
- waiver-expiry
- hidden-input-ban

Rule modules remain inside this package until a module has an independent port, consumer, version cadence, and no duplicated shared model.

## Inputs

- accepted ADR bundle
- target repo id
- explicit repo snapshot
- projector version
- optional base snapshot for non-regression comparison

## Outputs

- `repo.contract.json`
- `package.contracts.json`
- `violations.json`
- `readme.generated.md` as data
- `plan.json`
- `provenance.json`

## Boundary

Generated outputs are views, not authority. README content produced by this package is generated explanation of the contract, not the contract source.

## Contract trace: package-contract-expansion-20261029-v2

This section is a package-local contract refinement, not a new ADRS decision. Accepted ADRS remains the meaning authority; the package exposes implementation responsibilities and observations separately.

| Internal operation | Required behavior | Provided / observed at this revision | Limit |
|---|---|---|---|
| `project` | accepted ADR bundle and explicit repo snapshot to contract projections | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |
| `check` | rule checks return violations and explanations | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |
| `plan-and-docs` | pure plans/docs output with provenance and digest metadata | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |

**Evidence boundary:** the required behavior is documented, but reading this README is only document-level Observation. It cannot prove executable behavior, source integration, complete adherence, or production use. Required/Provided/Observation joins must pin their inputs and public revision; unmatched requirements remain explicitly open.

**Open observations:** No core function execution observed; No acceptance of all accepted ADR semantics proven. The observations above are not runtime tests and are not PASS receipts.

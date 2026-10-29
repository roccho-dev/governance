# repo-governance-cli

`repo-governance-cli` is the thin adapter package for using `repo-governance` from local and CI environments.

It must not contain governance rule semantics. It only decodes inputs, calls `repo-governance`, and encodes outputs.

## Goal

Make `repo-governance` observable and enforceable in CI through console output, requested output files, and process status.

## No-goals

- no new rule definitions
- no business judgement
- no hidden inputs
- no live network access
- no remote repo mutation
- no runtime operation execution
- no authority over generated docs or plans

## Allowed adapter behavior

- read explicit files or stdin
- pass decoded data into `repo-governance`
- print violations and explanations
- write requested generated outputs
- return pass or fail status

## Forbidden behavior

- deciding whether a rule should exist
- changing repo contents unless an explicit output path is requested
- calling remote APIs
- using current time as an implicit input
- adding checks not represented by the lib package contract

## Boundary

The CLI is a carrier. The lib package owns the result shape; `adrs` owns the rule meaning.

## Contract trace: package-contract-expansion-20261029-v2

This section is a package-local contract refinement, not a new ADRS decision. Accepted ADRS remains the meaning authority; the package exposes implementation responsibilities and observations separately.

| Internal operation | Required behavior | Provided / observed at this revision | Limit |
|---|---|---|---|
| `decode` | explicit file/stdin decoded into data | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |
| `delegate` | forward decoded data to repo-governance without minting rule semantics | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |
| `emit` | print violations/explanations, write only requested outputs, return pass/fail status | Existing package README states this responsibility; source/API/runtime behavior is not established by the README alone | Unverified implementation |

**Evidence boundary:** the required behavior is documented, but reading this README is only document-level Observation. It cannot prove executable behavior, source integration, complete adherence, or production use. Required/Provided/Observation joins must pin their inputs and public revision; unmatched requirements remain explicitly open.

**Open observations:** No runtime CLI invocation observed; No output/status contract execution observed. The observations above are not runtime tests and are not PASS receipts.

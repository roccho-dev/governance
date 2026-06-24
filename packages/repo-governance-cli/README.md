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

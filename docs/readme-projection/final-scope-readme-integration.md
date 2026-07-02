# Final-scope README integration

## Purpose

Define how README projection receipts enter the future `gov-final-scope-purpose-join / gate` report.

README and package README files are not authority. They are human-readable projections of ADRS meaning. Drift in those files is evidence that the repo's reader-facing projection has diverged from ADRS-derived expectations.

## Inputs

- `readmeProjectionReceipt.v1` rows for root README and package READMEs.
- `readmeProjectionFinding.v1` rows for missing sections, forbidden claims, stale projection, or missing package README.
- ADRS projection contracts from `repoReadmeProjection.v1` and `packageReadmeProjection.v1`.

## Report behavior

The final-scope report should include README findings as non-authority projection drift.

| Finding | Final-scope meaning |
|---|---|
| missing root README section | root README no longer works as repo map |
| missing package README | package responsibility is not reader-visible |
| missing required receipt section | package does not expose evidence expectations |
| forbidden authority claim | README or package README overclaims authority |
| stale ADRS reference | README projection points at old decision digest |

## Gate behavior

A README projection finding may block final scope only when an accepted ADRS projection contract marks that surface required.

The gate must not treat README content as meaning authority. It only treats the receipt as evidence that the human-readable projection matches accepted ADRS expectations.

## Required finding fields

- `repoId`
- `packageId`
- `surfacePath`
- `diagnosticClass`
- `expected`
- `actual`
- `delta`
- `likelyOwner`
- `nextAction`
- `adrsRef`

## Current projection status

`governance#77` introduced root README, tools README, modules README, and proposal-stage receipt rows.

Phase A/C follow-up work moves those receipt rows to accepted projection mode after the ADRS foundation in `roccho-dev/adrs#105` and `roccho-dev/adrs#106` has merged.

Accepted-mode README projection receipts remain non-authority evidence. They do not make README projection green a final merge pass unless a later accepted final-scope gate consumes the receipt and all other required joins are active.

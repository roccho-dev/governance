# Claim check adoption monitor proposal

## Why

A feat repo can call the governance claim checker, but that alone does not prove it will keep calling it. Governance needs a deterministic adoption monitor that detects when a selected repo removes, weakens, or stales its claim admission check.

## Decision

Add a governance-side adoption monitor for selected repos.

The monitor checks repo snapshots for:

- governance checker input presence
- declared claim admission CI intent
- workflow or generated check wiring
- strictness mode when required
- stale governance or ADRS references
- missing downstream claim and receipt surfaces

## Diagnostic classes

- `missing-gov-input`
- `missing-claim-admission-check`
- `warning-only-escape`
- `stale-gov-ref`
- `missing-ci-intent`
- `missing-selected-repo`
- `missing-downstream-claim-surface`
- `missing-receipt-surface`

## Boundary

The monitor does not execute downstream repo code and does not become policy authority. It reports adoption drift against an ADRS-selected universe and governance contract.

## Implementation proof

`tools/check-claim-check-adoption-monitor.py selftest` reads `fixtures/claim-check-adoption-monitor/cases.jsonl` and proves pass, missing-check, warning-only escape, stale reference, missing CI intent, missing selected repo, and missing surface cases.

Fixture count: 8 cases.

## Merge gate

Merge only after a fixture proves that removing the claim check from a selected repo snapshot is reported as adoption drift.

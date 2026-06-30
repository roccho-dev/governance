# Reusable package check export work order

## Purpose

Create the third governance core PR after parser fixtures and package join report.

Feature repos must not remain self-report only. Governance should export reusable package checks that repos can run in their own CI while keeping governance non-authoritative.

## Scope

Add work-order guidance for reusable checks covering:

- claim shape
- requirement-to-test coverage
- evidence freshness
- receipt and residual presence
- README / artifact boundary
- generated output boundary
- check adoption proof

## Inputs

- package response rows from feature repos
- package join report rows
- repo-local evidence receipts
- repo-local adoption markers

## Outputs

- reusable check commands or modules
- deterministic diagnostic rows
- fixture proof that a feature repo can call the check package

## Required exported checks

| check | diagnostic |
|---|---|
| claim shape | `claim-shape-invalid` |
| requirement test | `requirement-test-missing` |
| evidence freshness | `evidence-stale` |
| receipt presence | `receipt-missing` |
| hidden residual | `hidden-residual` |
| route match | `route-mismatch` |
| generated output boundary | `generated-output-boundary-missing` |
| README artifact boundary | `readme-artifact-boundary-missing` |
| adoption proof | `check-adoption-missing` |

## Non-goals

- Do not mutate feature repos.
- Do not claim selected repos have adopted these checks yet.
- Do not make exported diagnostics authority.

## Acceptance

The future implementation should expose a reusable package check surface and prove locally that a fixture feature repo can invoke it.

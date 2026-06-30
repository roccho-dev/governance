# Package join report work order

## Purpose

Create the second governance core PR after package obligation and claim parser fixtures.

This PR should define how parsed package obligations and package-side responses become a deterministic package report.

## Scope

Add work-order guidance for:

- joining expected package obligations to package responses
- reporting missing package response rows
- reporting role mismatch and path drift
- reporting untested requirement rows
- reporting non-goal gaps and extra responses

## Inputs

- parsed ADRS package obligations
- parsed feature package responses
- target universe records

## Outputs

- package join report
- package diagnostic rows
- repo-attributed unresolved gap rows

## Join key

A package response must match the expected obligation by:

- ADRS ref
- universe id
- repo locator
- package id
- package path
- owner role
- obligation id
- requirement id
- required test id

## Diagnostics

| diagnostic | meaning |
|---|---|
| `missing-response` | expected package obligation has no package response |
| `role-mismatch` | response exists but owner role does not match |
| `path-drift` | response exists but package path differs |
| `untested-requirement` | response claims adoption without required test evidence |
| `missing-required-test` | required test id is absent from the response |
| `non-goal-gap` | response declares the package requirement as non-goal |
| `extra-response` | response exists without expected obligation |
| `duplicate-response` | more than one response claims the same package obligation |

## Non-goals

- Do not define ADRS package meaning in governance.
- Do not mutate feature repos.
- Do not claim all-repo green here.

## Acceptance

The future implementation should emit deterministic package-level rows and attribute every unresolved row to the owning repo and package id.

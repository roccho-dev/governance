# All-repo package status CI work order

## Purpose

Create the final governance core PR for package-level evidence adoption.

Governance should produce repo-level status from package-level obligations, responses, join reports, exported check results, receipts, and residuals.

## Scope

Add work-order guidance for:

- reading package join report rows
- reading reusable package check rows
- producing repo status and package status
- keeping repos non-green until required proof exists or ADRS-backed out-of-scope proof exists
- attributing every non-green result to repo, package id, package path, and diagnostic

## Inputs

- package join report rows
- reusable package check rows
- evidence receipts
- residual rows
- check adoption rows

## Outputs

- repo status report
- package status report
- non-green diagnostic rows
- CI artifact for review

## Non-green causes

| cause | meaning |
|---|---|
| `missing-response` | required package response is absent |
| `missing-required-test` | required test proof is absent |
| `requirement-test-missing` | exported check cannot find required test proof |
| `evidence-stale` | evidence is not fresh |
| `receipt-missing` | receipt is absent |
| `hidden-residual` | residual is hidden or not surfaced |
| `route-mismatch` | response route does not match expected route |
| `extra-response` | response has no expected obligation |
| `duplicate-response` | duplicate package response exists |
| `role-mismatch` | owner role does not match expected obligation |
| `path-drift` | package path differs from expected obligation |
| `check-adoption-missing` | feature repo has not proven check adoption |

## Green condition

A repo can be green only when each required package obligation has fresh proof and receipt, or has ADRS-backed out-of-scope proof.

## Non-goals

- Do not make governance the ADRS authority.
- Do not mutate downstream repos.
- Do not claim deploy adoption is complete here.

## Acceptance

The future implementation should emit deterministic repo/package status rows and fail non-green fixtures for every listed cause.

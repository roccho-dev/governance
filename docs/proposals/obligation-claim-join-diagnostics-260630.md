# Obligation claim join diagnostics work order

## Purpose

Create the second governance core PR for ADRS #100.

The goal is to join ADRS package obligations with feature package claims and emit bounded diagnostics.

## Scope

Add work-order guidance for:

- join keys: `adrs_ref`, `target_universe_id`, `repo_locator`, `authority_surface`, `package_id`, `package_path`, `owner_role`, `obligation_id`, `requirement_id`, `required_test_id`
- diagnostics: `owner-role-mismatch`, `package-path-drift`, `requirement-untested`, `required-test-missing`, `non-goal-untested`, `non-goal-violation`, `overclaim`, `duplicate-claim`

## Inputs

- parsed ADRS obligations
- parsed feature claims
- required tests
- non-goals

## Outputs

- `package_join_report.jsonl`
- per-package diagnostic rows
- blocking/non-blocking severity field

## Required fixtures

| fixture | expected diagnostic |
|---|---|
| claim role differs from obligation role | `owner-role-mismatch` |
| package_path differs without receipt | `package-path-drift` |
| adopted claim lacks test | `requirement-untested` |
| required test not referenced | `required-test-missing` |
| non-goal lacks guard | `non-goal-untested` |
| non-goal is claimed as implemented | `non-goal-violation` |
| feature claims outside ADRS obligation | `overclaim` |
| conflicting claims for same obligation | `duplicate-claim` |

## Non-goals

- Do not provide feature repo CI adoption here.
- Do not build the all-repo red gate here.
- Do not decide ADRS meaning in governance.

## Acceptance

The future implementation should produce deterministic diagnostic rows from fixture inputs.

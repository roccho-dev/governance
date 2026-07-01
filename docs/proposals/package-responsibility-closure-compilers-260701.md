# Package responsibility closure compiler work order

## Purpose

Turn the ADRS package responsibility closure plane into governance-owned non-authority compilers and reports.

The gap is not that governance lacks a package parser or package join. Those exist for governance-ready rows. The gap is that old ADRS package proposals and real repo packages are not yet normalized into the same input surface.

This PR defines implementation responsibilities for:

1. ADRS obligation extraction.
2. Repo package inventory scanning.
3. Feature response normalization.
4. Three-way drift joining.
5. Drift-to-PR work order reporting.

## Boundary

`governance` remains a non-authority diagnostic and projection repo.

This PR must not:

- define accepted ADRS meaning;
- mutate target repos;
- approve merges;
- claim all repos are adopted;
- turn selected rollout into all-repo strict;
- treat generated outputs as authority.

## Current usable base

Existing package parser and joins already handle governance-readable rows. This work should extend input surfaces, not replace the existing parser/join/status code.

## Target architecture

```text
ADRS docs/jsonl
  -> package-obligation-extractor
  -> packageObligation.v1 rows

repo tree / flake / package manifests / package jsonl
  -> package-inventory-scanner
  -> packageInventory.v1 rows

repo package response files
  -> package-response-normalizer
  -> packageResponse.v1 rows

obligation + inventory + response
  -> package-drift-join
  -> packageDrift.v1 rows

packageDrift.v1 rows
  -> drift-work-order-report
  -> PR work order candidates
```

## Work package 1: ADRS obligation extractor

### Input

- ADRS explicit JSONL package records.
- ADRS proposal docs with explicit package obligation tables.
- Existing ADRS #100/#101/#102 package obligation contract records.

### Output

`packageObligation.v1` JSONL rows with the governance identity fields and expanded requirement/test rows.

### Required diagnostics

| Diagnostic | Meaning |
|---|---|
| `adrs-obligation-shape-invalid` | required obligation field is missing |
| `package-id-missing` | stable package identity is absent |
| `package-path-missing` | current package path is absent |
| `required-test-missing` | obligation has no required test |
| `target-universe-unknown` | referenced universe is not defined |

### Non-goals

- Do not infer package obligations from arbitrary prose in the first implementation.
- Do not claim ADRS docs without explicit tables/jsonl are fully backfilled.

## Work package 2: package inventory scanner

### Input

- repo `packages/**` directories;
- flake packages and checks;
- `package.json` workspaces;
- repo-local `build/packages.jsonl` and `build/checks.jsonl` when present;
- checked-in package response locations.

### Output

`packageInventory.v1` rows.

### Required fields

- `repo_locator`
- `package_path`
- `package_id_candidate`
- `source_kind`
- `entrypoints[]`
- `tests[]`
- `confidence`
- `discovered_by`
- `digest`

### Required diagnostics

| Diagnostic | Meaning |
|---|---|
| `unregistered-package` | inventory row has no ADRS obligation |
| `generated-artifact-misclassified` | generated/evidence output is counted as source package |
| `inventory-source-unsupported` | scanner cannot classify source kind |

## Work package 3: response normalizer

### Input

- `governance.packageResponse.v1` rows;
- `ops.packageResponse.v1` rows;
- UI package response rows;
- future deploy package response rows.

### Output

Canonical `packageResponse.v1` rows that the existing package join can consume.

### Required diagnostics

| Diagnostic | Meaning |
|---|---|
| `response-shape-invalid` | required response fields cannot be mapped |
| `response-obligation-missing` | response lacks obligation id or ADRS ref |
| `response-test-missing` | response does not cite required test |
| `response-receipt-missing` | closure claim lacks receipt |
| `response-residual-hidden` | incomplete response hides residual |

## Work package 4: three-way drift join

### Input

- `packageObligation.v1`
- `packageInventory.v1`
- `packageResponse.v1`

### Output

`packageDrift.v1` rows.

### Required drift codes

| Drift | Meaning |
|---|---|
| `registered-package-missing-on-disk` | ADRS obligation exists but no inventory path exists |
| `unregistered-package` | inventory package exists but ADRS obligation is absent |
| `claim-missing` | obligation exists but no response exists |
| `extra-response` | response exists without obligation |
| `overclaim` | response claims beyond obligation boundary |
| `package-path-drift` | stable package id moved without receipt |
| `required-test-missing` | required test is absent |
| `receipt-missing` | closure lacks receipt |
| `residual-hidden` | residual is not returned |
| `owner-role-mismatch` | wrong owner role answered |
| `authority-collision` | non-authority output is treated as meaning authority |

## Work package 5: drift-to-work-order report

### Output

`packageWorkOrder.report.v1` with PR-ready rows.

Each work-order row must contain:

- `primary_gap_id`
- `repo_locator`
- `package_id`
- `diagnostic`
- `current`
- `ideal`
- `suggested_pr_title`
- `suggested_scope`
- `proof_required`
- `receipt_required`
- `residual_policy`
- `blocking_level`

## Rollout plan

| Phase | Mode | Merge condition |
|---|---|---|
| 1 | selftest only | fixtures prove parser/scanner/normalizer/drift rows |
| 2 | shadow | reports are emitted but do not fail all repos |
| 3 | selected-warning | selected repos produce warnings for blocking drift |
| 4 | selected-strict | explicit ADRS-selected repos fail on blocking drift |
| 5 | all-repo-baseline | all repos inventoried without strict adoption claim |

## Initial fixture matrix

| Fixture | Expected diagnostic |
|---|---|
| ADRS obligation with no inventory and no response | `registered-package-missing-on-disk`, `claim-missing` |
| repo package with no ADRS obligation | `unregistered-package` |
| response with no ADRS obligation | `extra-response` |
| package moved without receipt | `package-path-drift` |
| response missing required test | `required-test-missing` |
| adopted response missing receipt | `receipt-missing` |
| blocked response missing reason | `blocked-without-reason` |
| generated artifact counted as source package | `generated-artifact-misclassified` |

## Acceptance

This PR is complete as a work order when it cleanly defines the governance implementation boundaries and fixture expectations.

A later implementation PR should be considered complete only when it adds deterministic tools, selftests, and CI wiring for the work packages above without making governance an authority repo.

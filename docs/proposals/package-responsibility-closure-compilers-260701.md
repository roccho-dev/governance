# Package responsibility closure compiler implementation

## Purpose

Implement the governance side of the Package Responsibility Closure Plane as non-authority compilers and reports.

The gap is not that governance lacks a package parser or package join. Those exist for governance-ready rows. The gap is that old ADRS package proposals and real repo packages are not yet normalized into the same input surface.

This PR implements the current governance compiler layer for:

1. ADRS obligation extraction.
2. Repo package inventory scanning.
3. Feature package response normalization.
4. Obligation x inventory x response drift joining.
5. Drift-to-PR work-order reporting.
6. Deterministic fixture selftests.

## Boundary

`governance` remains a non-authority diagnostic and projection repo.

This PR must not:

- define accepted ADRS meaning;
- mutate target repos;
- approve merges;
- claim all repos are adopted;
- turn selected rollout into all-repo strict;
- treat generated outputs as authority.

## Implemented surface

The implementation lives in:

- `tools/build-package-responsibility-closure.py`
- `fixtures/package-responsibility-closure/**`

The tool supports:

```text
python3 tools/build-package-responsibility-closure.py selftest
python3 tools/build-package-responsibility-closure.py build --adrs <path> --repo <path> --responses <path> --out-dir <out>
```

CI also runs the tool through the existing package governance selftest loop because it is named `tools/build-package-*.py`.

## Target architecture

```text
ADRS docs/jsonl
  -> package-obligation-extractor
  -> governance.packageObligation.v1 rows

repo tree / package manifests / package jsonl
  -> package-inventory-scanner
  -> governance.packageInventory.v1 rows

repo package response files
  -> package-response-normalizer
  -> governance.packageResponse.v1 rows

obligation + inventory + response
  -> package-drift-join
  -> governance.packageDrift.v1 rows

packageDrift.v1 + parser/scanner/normalizer diagnostics
  -> drift-work-order-report
  -> governance.packageWorkOrder.v1 rows
```

## Work package 1: ADRS obligation extractor

### Input

- explicit JSONL package records;
- explicit markdown package obligation tables.

### Output

`governance.packageObligation.v1` JSONL rows.

### Diagnostics

| Diagnostic | Meaning |
|---|---|
| `package-id-missing` | stable package identity is absent |
| `package-path-missing` | current package path is absent |
| `required-test-missing` | obligation has no required test |
| `target-universe-unknown` | referenced universe is not defined |

### Non-goals

- Do not infer package obligations from arbitrary prose.
- Do not claim ADRS docs without explicit tables/jsonl are fully backfilled.

## Work package 2: package inventory scanner

### Input

- repo `packages/*` directories;
- root `package.json` package;
- repo-local `build/packages.jsonl` when present;
- generated-looking package manifests for misclassification diagnostics.

### Output

`governance.packageInventory.v1` rows.

### Required fields

- `repoLocator`
- `packagePath`
- `packageIdCandidate`
- `sourceKind`
- `entrypoints[]`
- `tests[]`
- `confidence`
- `discoveredBy`
- `digest`

### Diagnostics

| Diagnostic | Meaning |
|---|---|
| `unregistered-package` | inventory row has no ADRS obligation |
| `generated-artifact-misclassified` | generated/evidence output is counted as source package candidate |

## Work package 3: response normalizer

### Input

- `governance.packageResponse.v1` rows;
- `ops.packageResponse.v1` rows;
- `ui.packageResponse.v1` rows;
- `deploy.packageResponse.v1` rows.

### Output

Canonical `governance.packageResponse.v1` rows that the package join can consume.

### Diagnostics

| Diagnostic | Meaning |
|---|---|
| `response-shape-invalid` | required response fields cannot be mapped |
| `response-obligation-missing` | response lacks obligation id or ADRS ref |
| `response-test-missing` | response does not cite required test |
| `response-receipt-missing` | closure claim lacks receipt |
| `response-residual-hidden` | incomplete response hides residual |

## Work package 4: three-way drift join

### Input

- `governance.packageObligation.v1`
- `governance.packageInventory.v1`
- `governance.packageResponse.v1`

### Output

`governance.packageDrift.v1` rows.

### Drift codes

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

`governance.packageWorkOrder.v1` PR-ready rows with:

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

## Deterministic fixture matrix

| Fixture | Expected diagnostic |
|---|---|
| ADRS obligation with no inventory and no response | `registered-package-missing-on-disk`, `claim-missing` |
| repo package with no ADRS obligation | `unregistered-package` |
| response with no ADRS obligation | `extra-response` |
| package moved without receipt | `package-path-drift` |
| response missing required test | `required-test-missing` |
| implemented response missing receipt | `receipt-missing` |
| blocked response missing residual | `residual-hidden` |
| wrong owner role answered | `owner-role-mismatch` |
| response claims authority | `authority-collision` |
| generated package-like output | `generated-artifact-misclassified` |

## Acceptance

This PR is complete when:

- the compiler emits obligation, inventory, response, drift, diagnostic, and work-order rows;
- deterministic selftests prove the fixture matrix;
- outputs remain non-authority;
- no downstream repo is mutated;
- all-repo strict gating is not enabled.

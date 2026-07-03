# Final-scope purpose join cutover plan

This document is non-authority evidence for governance #82 under parent governance #125.

## Required final check

```text
gov-final-scope-purpose-join / gate
```

The check name is produced by `.github/workflows/gov-final-scope-purpose-join.yml` with job name `gate`.

## Boundary

This plan does not change branch protection by itself. It records the intended cutover path after same-name green evidence exists.

`handoff-ready`, `report-generated`, artifact output, drift rows, and work-order rows are evidence only. They are not selected real package `closure-pass`.

## Cutover order

1. Merge the final gate adapter PR only after CI proves the same check name exists and is green.
2. Record the head SHA and check run evidence in governance #114.
3. Update ruleset / branch protection required checks to require only `gov-final-scope-purpose-join / gate` as the final merge surface.
4. Keep old checks as evidence producers, artifact producers, tool selftests, or final-join internal steps.
5. If cutover fails, roll back required checks to the previous protected set and keep the final gate workflow non-required until corrected.

## Old CI role mapping

| Current surface | Final role | Merge authority |
|---|---|---|
| `.github/workflows/ci.yml` / `nix flake check` | evidence producer, receipt producer, tool selftest runner | no |
| `.github/workflows/readme-artifact.yml` | artifact producer | no |
| `.github/workflows/repo-explain-artifact-minimal.yml` | artifact producer | no |
| `.github/workflows/repo-governance.yml` | tool selftest | no |
| `.github/workflows/claim-port-join.yml` | final-join internal selftest | no |
| `.github/workflows/claim-port-org-admission.yml` | final-join admission selftest | no |
| `.github/workflows/log-route-join.yml` | final-join internal selftest | no |
| `.github/workflows/intent-reality-gap.yml` | final-join internal selftest | no |
| `.github/workflows/adrs-shadow-monitor.yml` | shadow observer / artifact producer | no |
| `.github/workflows/manual-ci.yml` | manual observation only | no |
| `.github/workflows/gov-final-scope-purpose-join.yml` | final required gate after cutover | yes, only after same-name green evidence and explicit ruleset cutover |

## Rollback

Rollback means removing `gov-final-scope-purpose-join / gate` from required checks and restoring the previous required check set while preserving the workflow and CI intent row as non-required evidence.

Rollback must be recorded with:

- ruleset or branch-protection state before rollback;
- ruleset or branch-protection state after rollback;
- head SHA whose final gate was rejected;
- blocker class that caused rollback;
- next owner action.

## Acceptance effect

This plan supports governance #115, #116, #117, and #118. It does not close #115 by itself because branch protection cutover must wait for same-name green evidence and an explicit settings/ruleset change.

# Old CI demotion map

Parent: governance #125  
Phase parent: governance #82  
Issues: governance #117, governance #118

This file is non-authority evidence. It records how old CI surfaces are classified after the final gate adapter exists.

## Final merge surface

```text
gov-final-scope-purpose-join / gate
```

This is the only surface that may become final merge authority after same-name green evidence and explicit ruleset / branch-protection cutover.

## Demotion table

| Workflow | Current compatible role | Final role | Final merge authority |
|---|---|---|---|
| `.github/workflows/gov-final-scope-purpose-join.yml` | `bootstrap_exception` until cutover | `primary_required_surface_after_cutover` | yes, after cutover only |
| `.github/workflows/ci.yml` | `primary_nix_check` until cutover | `receipt_producer_and_tool_selftest_after_cutover` | no after cutover |
| `.github/workflows/manual-ci.yml` | `bootstrap_exception` | `manual_observation_only` | no |
| `.github/workflows/adrs-shadow-monitor.yml` | `bootstrap_exception` | `artifact_or_shadow_observer` | no |
| `.github/workflows/repo-explain-artifact-minimal.yml` | `artifact_exporter` | `artifact_producer_not_merge_authority` | no |
| `.github/workflows/repo-governance.yml` | `bootstrap_exception` | `tool_selftest_not_merge_authority` | no |
| `.github/workflows/readme-artifact.yml` | `artifact_exporter` | `artifact_producer_not_merge_authority` | no |
| `.github/workflows/claim-port-join.yml` | `bootstrap_exception` | `final_join_internal_step_or_tool_selftest` | no |
| `.github/workflows/claim-port-org-admission.yml` | `bootstrap_exception` | `final_join_admission_step` | no |
| `.github/workflows/log-route-join.yml` | `bootstrap_exception` | `final_join_internal_step_or_tool_selftest` | no |
| `.github/workflows/intent-reality-gap.yml` | `bootstrap_exception` | `final_join_internal_step_or_tool_selftest` | no |

## Machine check

`tools/check-package-ci-final-role-demotion.py selftest --json` validates:

- every workflow has a `ci.intent.v1` row;
- every old workflow has the expected `final_role`;
- all workflow rows remain `authority:false`;
- old workflows do not declare `required_check_name`;
- the final gate declares the exact check name `gov-final-scope-purpose-join / gate`;
- ruleset cutover still requires same-name green evidence first.

## Boundary

This demotes names and roles in repo evidence. It does not directly change GitHub branch protection, does not make governance authority, and does not close selected real package `closure-pass`.

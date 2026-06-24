# repo-governance executable proof

## Goal

Turn the merged `adrs#21` package strategy into an executable, deterministic, non-authority governance check and a GitHub CI gate.

## Result

| Item | Result |
|---|---:|
| Pure lib | `repo-governance` core+port |
| IO adapter | `repo-governance-cli` |
| External dependencies | 0 |
| Proof checks | 18 PASS |
| Destructive fixtures | 8 rejected |
| Unknown rule | rejected |
| Input order change | same digest |
| Clean-room CLI repeat | same result |
| Valid result digest | `357c04de31b1ef24407bc69463ac51a6af141c1bfcafee8751d5be4c319a3087` |
| Workflow permissions | `contents: read` |
| Required-check candidate | `repo-governance / proof` |

## Boundary

- `adrs` owns rule meaning.
- `repo-governance` projects and checks explicit data without IO.
- `repo-governance-cli` reads/writes and maps violations to process status.
- GitHub Actions runs the proof and blocks through its status result.
- `github/ruleset-plan.json` is a plan, not control-plane authority or mutation.

## Apply order

1. Open the implementation proposal PR.
2. Confirm the workflow passes on the proposal branch.
3. Confirm the observed check context is exactly `repo-governance / proof`.
4. Apply the ruleset plan through an authorized repository administrator or adapter.
5. Re-run one negative PR to confirm the required check blocks.

## Rollback

Remove the required status check before renaming or deleting the workflow/job. Then revert the implementation while retaining its receipt and source-decision references.

# Repo Convention Policy

This policy defines the first governance-side convention gate for repositories
that adopt governance checks through `nix flake check`.

## Scope

The initial convention has two rules:

- `README.md` is a checked artifact.
- GitHub provider CI entries are declared adapter artifacts whose primary
  verification entrypoint is `nix flake check`.

## README as Artifact

`README.md` is a checked artifact. It may be handwritten, partially managed, or
generated according to `readme_mode`. `README.md` is not an independent
authority.

Allowed `readme_mode` values:

- `checked_handwritten`: existing README content is allowed, but required
  sections and boundary wording are checked.
- `managed_block`: only marked README blocks are generated and drift-checked.
- `generated`: the entire README is generated and drift-checked.

Required sections for `checked_handwritten`:

- Purpose
- Authority boundary
- Inputs
- Outputs / artifacts
- Checks
- Ownership / handoff

## CI Provider Entries

`.github/workflows/*.yml` are checked-in provider adapter artifacts. They are
executable by GitHub, but they are not authority.

All GitHub provider workflows must be declared by `ci.intent.v1.jsonl`.

The primary verification entrypoint is `nix flake check`.

`workflow_dispatch` is allowed when declared and when it dispatches
non-authority provider behavior.

Undeclared independent authority CI entries fail.

Allowed workflow roles:

- `primary_nix_check`: runs `nix flake check`.
- `manual_dispatch_alias`: manually dispatches declared non-authority behavior.
- `artifact_exporter`: publishes nix-defined outputs without creating
  independent CI authority.
- `bootstrap_exception`: temporary declared exception with owner, reason, and
  expiry.

## Governance Consumption

Governance may be consumed as:

- `flake_lib`: downstream imports `governance.lib.<system>.repoConventionChecks`.
- `flake_false_path`: downstream calls `tools/check-repo-convention.py` from a
  path input.
- `shadow_unconnected`: report-only mode for repos not yet connected.

Branch-pinned governance input is a freshness risk, not a convention failure.
Downstream repos must declare `governance_ref` so convention results are
explainable.

## Severity

Allowed severities:

- `report_only`: print results without failing.
- `warning`: print warning receipts without failing.
- `blocking`: fail on convention violations.

`adrs` starts as `repo_class=root_authority` with `report_only` severity.
Blocking adoption for a root authority repo requires a separate accepted
decision.

## Determinism

Convention checks must be local, deterministic, network-free, and independent of
`.git` state.

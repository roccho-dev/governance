# README artifact gov-lib Canon TDD implementation review

## Why

The README artifact gov-lib implementation must be reviewed as a PR-scoped change, not as unreviewed default-branch drift. This document records the implementation review lane for the commits already present on `proposals`.

## Direction

Keep governance limited to ADR-derived policy/model/check projection. The implementation must prove the contract through CI and must not render Markdown, upload artifacts, mutate repositories, or become an independent policy source.

## Decision

Review the README artifact gov-lib implementation as a Canon TDD lane:

1. contract test first;
2. minimal pure projector;
3. negative fixtures for authority inversion;
4. CI path through `nix flake check` or an explicitly declared non-authority workflow;
5. no artifact ownership in governance.

## Boundary

Allowed:

- generate `readme.policy.capsule.json`;
- generate `repo.explain.model.json`;
- generate `diagnostics.jsonl`;
- generate `source-closure.jsonl`;
- fail closed on stale, missing, unknown, or raw-authority inputs.

Forbidden:

- write `README.md`;
- emit final Markdown bytes;
- upload GitHub artifacts as owner;
- mutate downstream repositories;
- treat raw ADR rows as final authority;
- create independent policy.

## Current review scope

The review lane covers these files:

- `tools/project-readme-govlib.py`
- `tools/check-readme-govlib-contract.py`
- `tools/check-repo-convention.py`
- `.github/workflows/readme-govlib-contract.yml`
- `ci.intent.readme.v1.jsonl`
- `repo-convention.intent.v1.json`

## Merge Gate

This lane is not complete until the CI path is green and the final reviewed state is represented as a proper PR diff before further implementation continues.

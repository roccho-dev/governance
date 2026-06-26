# README artifact gov-lib boundary proposal

## Why

README artifact work needs a governance-side boundary before implementation. Without this split, governance can accidentally become a policy source, Markdown renderer, repository mutator, or artifact owner. The goal is to keep governance as a reusable library that resolves and checks ADR-derived policy and model data while leaving artifact materialization to each consuming repository CI.

## Direction

Adopt `gov-lib` as an ADR-derived policy/model/check library. It may project and validate README artifact inputs, but it must not own the final README artifact lifecycle. Each consuming repository should call `gov-lib` to obtain policy capsules, semantic document models, diagnostics, and provenance data, then hand the document model to a renderer and upload its own artifact.

## Decision

`governance` should provide a library surface for README artifact policy and model projection. This proposal does not implement the library. It fixes the expected responsibilities, input/output shape, forbidden paths, negative fixtures, and merge gates for the later implementation proposal.

## Boundary

| Area | Decision |
|---|---|
| `gov as lib` | YES |
| policy source | NO |
| ADR-derived policy/model projection | YES |
| README required-slot checks | YES |
| Markdown bytes rendering | NO |
| artifact upload | NO |
| repository mutation | NO |
| runtime execution | NO |
| consumer adoption authority | NO |

Allowed responsibilities:

- resolve ADR-derived policy/model capsules from accepted inputs;
- check README required slots;
- report missing, stale, and unknown inputs;
- compute source closure and provenance rules;
- define a consumer contract for downstream repository CI.

Forbidden responsibilities:

- invent policy independently of ADR-derived inputs;
- read raw ADR rows as final authority;
- render Markdown bytes as the final surface;
- write README.md as artifact owner;
- upload GitHub Actions artifacts as the owning side;
- mutate downstream repositories;
- decide downstream severity or exception adoption by itself.

## Input contract

Minimum inputs for `gov-lib`:

| Input | Meaning |
|---|---|
| accepted ADR bundle | authority-derived source bundle |
| repository identity | target repo such as `roccho-dev/ui` |
| repo-local manifest | repo/package profile and local intent |
| profile | repo shape such as library, service, adapter, workflow, UI, data, evidence, archive |
| capsule pin | digest-pinned governance input version |
| projector version | version of the gov-lib projection/check surface |

## Output contract

Minimum outputs from `gov-lib`:

| Output | Meaning |
|---|---|
| `readme.policy.capsule.json` | required slots, gates, severity, and policy facts |
| `repo.explain.model.json` | semantic document model for the target repo |
| `diagnostics.jsonl` | missing, stale, unknown, or forbidden state findings |
| `source-closure.jsonl` | source rows and digest/provenance closure |

The model may later be rendered by `ui-lib`, but `gov-lib` must not own the Markdown surface.

## Consumer contract

Each consuming repository should:

1. pin the `gov-lib` input or capsule;
2. provide repository identity and local manifest;
3. run the `gov-lib` checks in CI;
4. pass the resolved document model to `ui-lib` or an equivalent accepted renderer;
5. write `README.md`, `manifest.json`, `sources.jsonl`, and `receipt.json` inside its own CI job;
6. upload those files as that repository's own CI artifact;
7. include `gov-lib` input digest and source closure digest in the manifest.

## Negative fixtures to add later

- `gov-lib` emits Markdown bytes as final artifact;
- `gov-lib` uploads a GitHub Actions artifact;
- `gov-lib` accepts raw ADR rows directly as final authority;
- `gov-lib` mutates a downstream repository;
- downstream repo forks the generator logic;
- required slot is missing but check passes;
- stale capsule is accepted as fresh;
- unknown policy input is treated as warning when blocking is required.

## Proof

This proposal follows ADR `doc://adrs/readme-artifact-library-boundaries` from adrs #64. It narrows the governance-side implementation surface before code is added, preserving the existing governance README boundary that governance is non-authority deterministic projection, not a decision authority or runtime executor.

## Change Summary

- Add a proposal document for `gov-lib` README artifact boundaries.
- Define input/output contracts for later implementation.
- Define consumer contract for downstream repositories.
- Explicitly remove artifact ownership and Markdown rendering from governance scope.

## Merge Gate

Merge only if the existing governance CI passes. Later implementation PRs should add checks and fixtures against this proposal before changing generator code.

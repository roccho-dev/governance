# R1 governance README artifact CI adoption

## Purpose

Make governance own its own README artifact CI while keeping gov-lib pure and keeping README non-authority.

## Direction

Add a governance-local README artifact package and a declared GitHub artifact exporter workflow. The workflow uploads only the Nix-built output.

## Decision

`governance` should expose `packages.<system>.readme-artifact` and `checks.<system>.readme-artifact`. The artifact packet must include `README.md`, `manifest.json`, `sources.jsonl`, and `receipt.json` with non-authority provenance.

## Boundary

- gov-lib emits policy/model/diagnostics/source closure only.
- ui-lib renders Markdown bytes from document.model.v1 only.
- governance repo CI writes and uploads the governance README artifact.
- The artifact is evidence, not authority.

## Merge Gate

- `nix flake check` passes.
- `nix build .#readme-artifact` emits the four required files.
- `.github/workflows/readme-artifact.yml` is declared in `ci.intent.v1.jsonl` as `artifact_exporter` with `source:nix-output`.

# Retire proof README artifact paths proposal

## Why

The R1 governance README artifact adoption PR is merged and is now the production path for governance README artifact materialization. Earlier minimal or proof paths should not be mistaken for the current contract.

## Direction

Mark proof and minimal README artifact paths as non-authority historical evidence or obsolete helpers. The production path is the declared R1 artifact exporter and Nix-built packet.

## Decision

- `governance #41` is the R1 production adoption lane for governance README artifacts.
- proof/minimal workflows and docs are not active ownership or authority paths.
- if proof files remain useful, keep them labelled as proof-only;
- otherwise remove or obsolete them in a follow-up implementation PR.

## Boundary

This proposal does not remove functional files by itself. It fixes interpretation and prepares safe cleanup.

## Merge Gate

Merge only if the active path remains the R1 declared artifact exporter and gov-lib does not own artifact upload or Markdown rendering.
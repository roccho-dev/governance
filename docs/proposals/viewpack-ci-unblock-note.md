# Viewpack CI unblock note

This branch exists only to carry the already-reviewed gov-lib contract implementation changes onto `proposals` so downstream Viewpack proposal PRs can be judged by the single declared `nix flake check` path.

## Boundary

This does not add Viewpack semantics, Markdown rendering, artifact upload ownership, or repository mutation logic.

## Expected effect

Remove the duplicate standalone README govlib workflow from the active proposal base and use the declared `ci.intent.v1.jsonl` convention path instead.

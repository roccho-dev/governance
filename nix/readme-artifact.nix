{ pkgs }:

pkgs.runCommand "governance-readme-artifact" { } ''
  set -euo pipefail
  mkdir -p "$out"

  cat > "$out/README.md" <<'EOF'
# governance

Non-authority README artifact for the governance repository.

## Purpose

Provide deterministic governance projection and checks.

## Authority boundary

- adrs owns accepted meaning
- governance projects and checks accepted inputs
- README artifacts are evidence, not authority

## Inputs

- accepted boundary bundle
- repo-local manifest
- gov-lib projector version
- ui-lib renderer source

## Outputs / artifacts

- README.md
- manifest.json
- sources.jsonl
- receipt.json

## Checks

- nix flake check
- readme-artifact packet check

## Ownership / handoff

governance repo CI owns this artifact packet. gov-lib and ui-lib remain reusable libraries.
EOF

  cat > "$out/sources.jsonl" <<'EOF'
{"kind":"governance.sourceClosure.v1","nonAuthority":true,"source":"doc://adrs/readme-artifact-library-boundaries"}
EOF

  cat > "$out/manifest.json" <<'EOF'
{"kind":"repo.readmeArtifact.manifest.v1","repo":"roccho-dev/governance","artifactOwner":"repo-ci","nonAuthority":true,"readmeMode":"generated","workflow_definition":"checked_in","artifact_source":"nix-output","artifact_generation":"generated"}
EOF

  cat > "$out/receipt.json" <<'EOF'
{"kind":"repo.readmeArtifact.receipt.v1","repo":"roccho-dev/governance","artifactOwner":"repo-ci","nonAuthority":true,"entrypoint":"nix build .#readme-artifact","requiredFiles":["README.md","manifest.json","sources.jsonl","receipt.json"]}
EOF

  test -s "$out/README.md"
  test -s "$out/manifest.json"
  test -s "$out/sources.jsonl"
  test -s "$out/receipt.json"
''

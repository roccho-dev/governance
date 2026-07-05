{ pkgs }:
let
  sanitizeName = value: builtins.replaceStrings [ "/" ":" " " ] [ "-" "-" "-" ] value;
  mkReadmeMaterializedCheck =
    { repoId
    , readmeArtifact
    , committedReadme
    , mode ? "generated"
    , producerRepo ? "roccho-dev/governance"
    , generatedBy ? "nix/readme-materialization-checks.nix:mkReadmeMaterializedCheck"
    }:
    pkgs.runCommand "${sanitizeName repoId}-readme-materialized-check" {
      nativeBuildInputs = [ pkgs.coreutils pkgs.diffutils ];
    } ''
      set -euo pipefail
      mkdir -p "$out"

      if [ "${mode}" != "generated" ]; then
        cat > "$out/residual.json" <<EOF
      {"kind":"readmeMaterializationResidual.v1","repoId":"${repoId}","mode":"${mode}","status":"residual","authority":false,"nonAuthority":true,"reason":"repo is not declared as generated README mode"}
EOF
        touch "$out/pass"
        exit 0
      fi

      test -s ${readmeArtifact}/README.md
      test -s ${committedReadme}

      artifact_digest=$(sha256sum ${readmeArtifact}/README.md | cut -d ' ' -f1)
      committed_digest=$(sha256sum ${committedReadme} | cut -d ' ' -f1)

      if ! cmp ${readmeArtifact}/README.md ${committedReadme}; then
        echo "[FAIL] committed README.md differs from generated README artifact for ${repoId}" >&2
        diff -u ${readmeArtifact}/README.md ${committedReadme} >&2 || true
        cat > "$out/finding.json" <<EOF
      {"kind":"readmeMaterializationFinding.v1","repoId":"${repoId}","status":"fail","diagnosticClass":"readme-materialization-drift","expected":"generated README artifact README.md","actual":"committed README.md","artifactDigest":"$artifact_digest","committedDigest":"$committed_digest","nextAction":"materialize README.md from the generated artifact or change repo-convention readme_mode with a residual","authority":false,"nonAuthority":true}
EOF
        exit 1
      fi

      cat > "$out/receipt.json" <<EOF
      {"kind":"readmeMaterializationReceipt.v1","repoId":"${repoId}","status":"pass","mode":"generated","artifactDigest":"$artifact_digest","committedDigest":"$committed_digest","producerRepo":"${producerRepo}","generatedBy":"${generatedBy}","authority":false,"nonAuthority":true}
EOF
      touch "$out/pass"
    '';

  mkReadmeMaterializationResidual =
    { repoId
    , mode
    , owner
    , reason
    , nextAction
    , returnCondition
    , expires
    }:
    pkgs.runCommand "${sanitizeName repoId}-readme-materialization-residual" { } ''
      set -euo pipefail
      mkdir -p "$out"
      cat > "$out/residual.json" <<EOF
      {"kind":"readmeMaterializationResidual.v1","repoId":"${repoId}","mode":"${mode}","status":"residual","owner":"${owner}","reason":"${reason}","nextAction":"${nextAction}","returnCondition":"${returnCondition}","expires":"${expires}","authority":false,"nonAuthority":true}
EOF
      touch "$out/pass"
    '';
in {
  inherit mkReadmeMaterializedCheck mkReadmeMaterializationResidual;
  boundary = "local README materialization evidence only; no README authority, no final join authority, no branch protection mutation";
}

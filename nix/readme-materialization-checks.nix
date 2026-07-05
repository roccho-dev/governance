{ pkgs, governanceSrc ? ../. }:
let
  sanitizeName = value: builtins.replaceStrings [ "/" ":" " " ] [ "-" "-" "-" ] value;
  checkTool = "${governanceSrc}/tools/check-readme-materialization.py";

  mkReadmeMaterializedCheck =
    { repoId
    , readmeArtifact
    , committedReadme
    , mode ? "generated"
    , producerRepo ? "roccho-dev/governance"
    , generatedBy ? "nix/readme-materialization-checks.nix:mkReadmeMaterializedCheck"
    }:
    pkgs.runCommand "${sanitizeName repoId}-readme-materialized-check" {
      nativeBuildInputs = [ pkgs.python3 ];
    } ''
      set -euo pipefail
      python3 "${checkTool}" check \
        --repo-id ${pkgs.lib.escapeShellArg repoId} \
        --mode ${pkgs.lib.escapeShellArg mode} \
        --artifact-readme ${pkgs.lib.escapeShellArg "${readmeArtifact}/README.md"} \
        --committed-readme ${pkgs.lib.escapeShellArg "${committedReadme}"} \
        --producer-repo ${pkgs.lib.escapeShellArg producerRepo} \
        --generated-by ${pkgs.lib.escapeShellArg generatedBy} \
        --out "$out"
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
    pkgs.runCommand "${sanitizeName repoId}-readme-materialization-residual" {
      nativeBuildInputs = [ pkgs.python3 ];
    } ''
      set -euo pipefail
      python3 "${checkTool}" residual \
        --repo-id ${pkgs.lib.escapeShellArg repoId} \
        --mode ${pkgs.lib.escapeShellArg mode} \
        --owner ${pkgs.lib.escapeShellArg owner} \
        --reason ${pkgs.lib.escapeShellArg reason} \
        --next-action ${pkgs.lib.escapeShellArg nextAction} \
        --return-condition ${pkgs.lib.escapeShellArg returnCondition} \
        --expires ${pkgs.lib.escapeShellArg expires} \
        --out "$out"
    '';

  selftest = pkgs.runCommand "readme-materialization-common-selftest" {
    nativeBuildInputs = [ pkgs.python3 pkgs.gnugrep ];
  } ''
    set -euo pipefail
    mkdir -p "$out"
    python3 "${checkTool}" selftest > "$out/selftest.json"
    grep -q '"kind":"readmeMaterializationChecker.selftest.v1"' "$out/selftest.json"
    grep -q '"status":"pass"' "$out/selftest.json"
    grep -q '"name":"generated-drift"' "$out/selftest.json"
    grep -q '"kind":"readmeMaterializationResidual.v1"' "$out/selftest.json"
    touch "$out/pass"
  '';
in {
  inherit mkReadmeMaterializedCheck mkReadmeMaterializationResidual selftest;
  boundary = "local README materialization evidence only; no README authority, no final join authority, no branch protection mutation";
}

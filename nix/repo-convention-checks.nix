{ pkgs, governanceSrc ? null }:

{ src
, manifestPath ? "repo-convention.intent.v1.json"
}:
{
  repo-convention = pkgs.runCommand "repo-convention-check" {
    nativeBuildInputs = [ pkgs.python3 ];
  } ''
    set -euo pipefail
    cp -R ${src} source
    chmod -R u+w source
    cd source
    python ${if governanceSrc == null then "." else governanceSrc}/tools/check-repo-convention.py \
      --repo-root . \
      --manifest ${manifestPath}
    touch "$out"
  '';
}

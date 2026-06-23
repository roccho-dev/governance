{ pkgs, self }:

pkgs.writeShellApplication {
  name = "repo-governance";
  runtimeInputs = [ pkgs.python3 ];
  text = ''
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH="${self}/packages/repo-governance/src:${self}/packages/repo-governance-cli/src''${PYTHONPATH:+:$PYTHONPATH}"
    exec python3 -m repo_governance_cli "$@"
  '';
}

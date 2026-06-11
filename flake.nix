{
  description = "governance: authoritative records (SSOT) + records-gate policy checks";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      checks = forEachSystem (pkgs: {
        # records-gate: CUE schema vet (policy/cue) + DuckDB relational
        # assertions (policy/sql/assertions; each SELECT returns violation
        # rows, 0 rows = pass) over records/. The non-blocking obligation-debt
        # report is kept as a build artifact for visibility.
        records-gate =
          pkgs.runCommand "records-gate"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.cue
                pkgs.duckdb
              ];
            }
            ''
              set -euo pipefail
              export HOME="$TMPDIR"
              mkdir -p "$out"
              python3 ${self}/tools/records-gate.py \
                --root ${self} \
                --report "$out/obligation-debt.json" \
                > "$out/records-gate.log"
              tail -n 3 "$out/records-gate.log"
            '';
      });
    };
}

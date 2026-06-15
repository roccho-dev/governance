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
        # records-gate: BLOCKING = cue vet only (C1 CUE unification).
        # Declaration-driven plumbing (identical shape across repos):
        # policy/interface.json lists {file, def, group};
        #   (a) every entry with a def is vetted per file:
        #       cue vet policy/cue/*.cue <file> -d '<def>'
        #   (b) grouped files are bundled into one labeled JSON and vetted
        #       against the relational constraints:
        #       cue vet policy/cue/*.cue all.json -d '#All'
        # All checking logic lives in policy/cue/; this derivation only does
        # the declared plumbing.
        # tools/records-gate.py is REPORT-ONLY (DuckDB obligation debt; never
        # blocks); its JSON is kept as a build artifact for visibility.
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
              cd ${self}
              mkdir -p "$out"
              python3 tools/cue-records-gate.py \
                --root . \
                --interface policy/interface.json \
                --cue-dir policy/cue \
                --relational-def '#All' \
                --bundle-out "$TMPDIR/relational-all.json"
              python3 tools/records-gate.py --root . --report "$out/obligation-debt.json" > "$out/records-gate.log"
              tail -n 3 "$out/records-gate.log"
            '';
      });
    };
}

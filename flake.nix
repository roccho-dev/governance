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
              python3 -c 'import json,os; e=json.load(open("policy/interface.json")); m=[x["file"] for x in e if x.get("required") and not os.path.exists(x["file"])]; assert not m, "missing required record files: %s" % m; print("\n".join(x["file"]+" "+x["def"] for x in e if x.get("def") and os.path.exists(x["file"])))' > "$TMPDIR/per-file-defs"
              while read -r file def; do
                cue vet policy/cue/*.cue "$file" -d "$def"
              done < "$TMPDIR/per-file-defs"
              python3 -c 'import json,os; e=json.load(open("policy/interface.json")); g=sorted({x["group"] for x in e if x.get("group")}); print(json.dumps({k: [json.loads(l) for x in e if x.get("group")==k and os.path.exists(x["file"]) for l in open(x["file"], encoding="utf-8") if l.strip()] for k in g}))' > "$TMPDIR/relational-all.json"
              cue vet policy/cue/*.cue "$TMPDIR/relational-all.json" -d '#All'
              echo "records-gate: cue vet PASS (per-file + relational)"
              python3 tools/records-gate.py --root . --report "$out/obligation-debt.json" > "$out/records-gate.log"
              tail -n 3 "$out/records-gate.log"
            '';
      });
    };
}

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
      # Consumable machine-input output for the bootstrap pinned-flake-input
      # consumer. A downstream flake pins this `governance` input and reads
      # `${governance.packages.<system>.bootstrap-input}/bootstrap-input.json`
      # (kind governance.bootstrapInput.v1). It is the committed projection of
      # the accepted record records/decisions/bootstrap-minimal-acceptance.v1.jsonl
      # produced by tools/make-bootstrap-input.py. URL slots in `ssotLocations`
      # are null (NOT YET ACCEPTED) — see ssotLocationContract; the consumer must
      # not fabricate URLs from null.
      packages = forEachSystem (pkgs: {
        bootstrap-input =
          pkgs.runCommand "bootstrap-input" { } ''
            mkdir -p "$out"
            cp ${self}/generated/bootstrap-input/bootstrap-minimal-acceptance.json "$out/bootstrap-input.json"
          '';

        # validate-local-raw: governance function package for provisional
        # feat-side discovery. Validates a feat-local raw.jsonl against the
        # governance #AdrRaw CUE schema. Output is
        # governance.localRawValidation.v1 JSON (explicitly non-authoritative).
        # Feat repos consume this via:
        #   nix run governance#validate-local-raw -- --raw ./local-raw.jsonl
        validate-local-raw = pkgs.writeShellApplication {
          name = "validate-local-raw";
          runtimeInputs = [
            pkgs.python3
            pkgs.cue
          ];
          text = ''
            exec python3 ${self}/tools/validate-local-raw.py \
              --cue-dir ${self}/policy/cue \
              "$@"
          '';
        };
      });

      checks = forEachSystem (pkgs: {
        # bootstrap-input-projection: guard the committed machine input against
        # drift from its accepted-record source (pure re-projection must match).
        bootstrap-input-projection =
          pkgs.runCommand "bootstrap-input-projection"
            { nativeBuildInputs = [ pkgs.python3 ]; }
            ''
              set -euo pipefail
              cd ${self}
              python3 tools/make-bootstrap-input.py --root . --out "$TMPDIR/fresh.json"
              if ! diff -u generated/bootstrap-input/bootstrap-minimal-acceptance.json "$TMPDIR/fresh.json"; then
                echo "bootstrap-input projection is stale: re-run tools/make-bootstrap-input.py" >&2
                exit 1
              fi
              echo "bootstrap-input-projection: committed == re-projected (PASS)"
              touch "$out"
            '';

        # validate-local-raw-proof: prove the governance function package
        # correctly validates a provisional local raw.jsonl fixture against
        # the #AdrRaw CUE schema and produces the expected non-authoritative
        # governance.localRawValidation.v1 output.
        validate-local-raw-proof =
          pkgs.runCommand "validate-local-raw-proof"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.cue
              ];
            }
            ''
              set -euo pipefail
              cd ${self}
              python3 tools/validate-local-raw.py \
                --cue-dir policy/cue \
                --raw tests/fixtures/provisional-local-raw.jsonl \
                --out "$TMPDIR/validation-result.json"
              python3 -c "
import json, sys
r = json.load(open('$TMPDIR/validation-result.json'))
assert r['kind'] == 'governance.localRawValidation.v1', f'unexpected kind: {r[\"kind\"]}'
assert r['authoritative'] is False, 'must be non-authoritative'
assert r['valid'] is True, f'validation failed: {r}'
assert r['totalRows'] >= 1, 'must validate at least one row'
print('validate-local-raw-proof: PASS')
"
              touch "$out"
            '';

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

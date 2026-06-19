{
  description = "governance: record projections and records-gate policy checks";

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
      });

      checks = forEachSystem (pkgs: {
        # feat-input-projection: the canonical gate function implementing the
        # Gate 6 continuity condition defined by the adrs.git ADR proposal
        # (governance-authority-cutover-acceptance). adrs.git is the SSOT for the
        # condition; this check is governance.git's canonical implementation of
        # it, not definition authority. It guards the existing new-feat creation
        # surface: it stages the `governance-records-main/` checkout layout
        # required by tools/make-feat-input.py, re-projects committed feat
        # inputs, checks projection-digest alignment, and smokes accepted/planned
        # package creation paths. PR CI must run tools/check-feat-input-pr-continuity.sh
        # to enforce accepted package non-decrease against the merge base.
        feat-input-projection =
          pkgs.runCommand "feat-input-projection"
            { nativeBuildInputs = [ pkgs.python3 ]; }
            ''
              set -euo pipefail
              cd ${self}
              python3 tools/check-feat-input-continuity.py --root .
              touch "$out"
            '';

        # feat-input-base-selftest: prove the accepted-set non-decrease path is
        # executable and fails closed when a base accepted package is missing at
        # HEAD. This is a self-test for the canonical gate function; real PR CI
        # must still supply the merge-base contract through
        # tools/check-feat-input-pr-continuity.sh.
        feat-input-base-selftest =
          pkgs.runCommand "feat-input-base-selftest"
            { nativeBuildInputs = [ pkgs.gnugrep pkgs.python3 ]; }
            ''
              set -euo pipefail
              cd ${self}
              mkdir -p "$out"
              cp records/specs/package-contract.v1.jsonl "$TMPDIR/base-package-contract.v1.jsonl"
              python3 tools/check-feat-input-continuity.py \
                --root . \
                --require-base \
                --base-package-contract "$TMPDIR/base-package-contract.v1.jsonl" \
                > "$out/pass.log"
              grep -q 'accepted-set-non-decrease: PASS' "$out/pass.log"

              cp "$TMPDIR/base-package-contract.v1.jsonl" "$TMPDIR/synthetic-drop-base.v1.jsonl"
              chmod u+w "$TMPDIR/synthetic-drop-base.v1.jsonl"
              printf '%s\n' '{"packageId":"__synthetic_removed_accepted__","status":"accepted"}' >> "$TMPDIR/synthetic-drop-base.v1.jsonl"
              if python3 tools/check-feat-input-continuity.py \
                --root . \
                --require-base \
                --base-package-contract "$TMPDIR/synthetic-drop-base.v1.jsonl" \
                > "$out/synthetic-drop.log" 2>&1; then
                echo "synthetic accepted-package drop unexpectedly passed" >&2
                exit 1
              fi
              grep -q '__synthetic_removed_accepted__' "$out/synthetic-drop.log"
              touch "$out/ok"
            '';

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

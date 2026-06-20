{
  description = "governance: record projections and records-gate policy checks";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    adrsRecords = {
      url = "git+ssh://100.124.250.91/home/nixos/repos/adrs.git?ref=refs/heads/proposal/record-jsonl-reproof-rehome-260619&rev=deb5e1ca5edfed1624143db96e483aaa675ed7de";
      flake = false;
    };
  };

  outputs =
    { self, nixpkgs, adrsRecords }:
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
      # (kind governance.bootstrapInput.v1). Governance owns this output surface,
      # but the record data is supplied by adrs.git's governance-records-main
      # projection. URL slots in `ssotLocations` are null (NOT YET ACCEPTED) —
      # see ssotLocationContract; the consumer must not fabricate URLs from null.
      packages = forEachSystem (pkgs: {
        bootstrap-input =
          pkgs.runCommand "bootstrap-input" { } ''
            mkdir -p "$out"
            cp ${adrsRecords}/records/projections/governance-records-main/generated/bootstrap-input/bootstrap-minimal-acceptance.json "$out/bootstrap-input.json"
          '';
      });

      checks = forEachSystem (pkgs: {
        # feat-input-projection: reference gate function implementing the
        # Gate 6 continuity condition defined by the adrs.git ADR proposal
        # (governance-authority-cutover-acceptance). adrs.git is the authority
        # for the condition; this check is governance.git's non-authority
        # reference implementation. It guards the existing new-feat creation
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
              workspace="$TMPDIR/adrs-projection-workspace"
              mkdir -p "$workspace"
              python3 ${adrsRecords}/tools/materialize-governance-records-projection.py \
                --adrs-root ${adrsRecords} \
                --workspace "$workspace" \
                --manifest-out "$TMPDIR/adrs-projection-manifest.json"
              gate_root="$workspace/gate-root"
              mkdir -p "$gate_root"
              ln -s "$workspace/governance-records-main/records" "$gate_root/records"
              ln -s "$workspace/governance-records-main/generated" "$gate_root/generated"
              ln -s ${self}/tools "$gate_root/tools"
              cd ${self}
              python3 tools/check-feat-input-continuity.py --root "$gate_root"
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
              workspace="$TMPDIR/adrs-projection-workspace"
              mkdir -p "$workspace"
              python3 ${adrsRecords}/tools/materialize-governance-records-projection.py \
                --adrs-root ${adrsRecords} \
                --workspace "$workspace" \
                --manifest-out "$TMPDIR/adrs-projection-manifest.json"
              projection_root="$workspace/gate-root"
              mkdir -p "$projection_root"
              ln -s "$workspace/governance-records-main/records" "$projection_root/records"
              ln -s "$workspace/governance-records-main/generated" "$projection_root/generated"
              ln -s ${self}/tools "$projection_root/tools"
              cd ${self}
              mkdir -p "$out"
              cp "$projection_root/records/specs/package-contract.v1.jsonl" "$TMPDIR/base-package-contract.v1.jsonl"
              python3 tools/check-feat-input-continuity.py \
                --root "$projection_root" \
                --require-base \
                --base-package-contract "$TMPDIR/base-package-contract.v1.jsonl" \
                > "$out/pass.log"
              grep -q 'accepted-set-non-decrease: PASS' "$out/pass.log"

              cp "$TMPDIR/base-package-contract.v1.jsonl" "$TMPDIR/synthetic-drop-base.v1.jsonl"
              chmod u+w "$TMPDIR/synthetic-drop-base.v1.jsonl"
              printf '%s\n' '{"packageId":"__synthetic_removed_accepted__","status":"accepted"}' >> "$TMPDIR/synthetic-drop-base.v1.jsonl"
              if python3 tools/check-feat-input-continuity.py \
                --root "$projection_root" \
                --require-base \
                --base-package-contract "$TMPDIR/synthetic-drop-base.v1.jsonl" \
                > "$out/synthetic-drop.log" 2>&1; then
                echo "synthetic accepted-package drop unexpectedly passed" >&2
                exit 1
              fi
              grep -q '__synthetic_removed_accepted__' "$out/synthetic-drop.log"
              touch "$out/ok"
            '';

        # bootstrap-input-from-adrs-projection: prove the bootstrap machine input
        # surface remains available after governance's local records/generated
        # authority is removed. The source data is adrs.git projection output;
        # governance only exposes the package surface used by bootstrap.
        bootstrap-input-from-adrs-projection =
          pkgs.runCommand "bootstrap-input-from-adrs-projection"
            { nativeBuildInputs = [ pkgs.python3 ]; }
            ''
              set -euo pipefail
              python3 - <<'PY'
              import json
              from pathlib import Path
              path = Path("${adrsRecords}/records/projections/governance-records-main/generated/bootstrap-input/bootstrap-minimal-acceptance.json")
              data = json.loads(path.read_text(encoding="utf-8"))
              assert data.get("kind") == "governance.bootstrapInput.v1", data
              assert data.get("status") == "accepted", data
              assert data.get("sourceAuthority") == "records/decisions/bootstrap-minimal-acceptance.v1.jsonl", data
              print("bootstrap-input-from-adrs-projection: PASS")
              PY
              touch "$out"
            '';

        # governance-records-frozen-migration-source: governance may retain the
        # former records/generated trees as frozen migration evidence during the
        # phase-gated cutover. Active package/check surfaces read adrsRecords;
        # physical deletion is a later phase, not this proposal's completion
        # claim.
        governance-records-frozen-migration-source =
          pkgs.runCommand "governance-records-frozen-migration-source"
            { nativeBuildInputs = [ pkgs.diffutils ]; }
            ''
              set -euo pipefail
              test -f ${self}/MIGRATION_SOURCE.md
              diff -qr ${self}/records ${adrsRecords}/records/projections/governance-records-main/records
              diff -qr ${self}/generated ${adrsRecords}/records/projections/governance-records-main/generated
              touch "$out"
            '';
      });
    };
}

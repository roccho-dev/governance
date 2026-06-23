{
  description = "governance: non-authority pure projection and continuity checks";

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

      helpText = ''
        governance flake surface

        Authority boundary:
          adrs decides accepted rules and exceptions.
          governance projects, checks, explains, plans, and renders from accepted inputs.
          generated README/docs/help/man text is not authority.

        Build:
          nix build .#bootstrap-input
            Build the explicit bootstrap compatibility package.
          nix build .
            Intentionally unsupported: governance has no packages.default.

        Run:
          nix run .
            Show this help.
          nix run .#help
            Show this help.

        Check:
          nix flake check
            Run all governance checks.
          checks include projection continuity, base non-decrease selftest,
          bootstrap input availability, no local records/generated, and Nix default surface.

        Dev shells:
          none exposed.

        Default policy:
          packages.default is forbidden unless a later accepted ADR allows one representative artifact.
          apps.default must be the same as apps.help.
      '';

      mkHelpProgram = pkgs:
        pkgs.writeShellApplication {
          name = "governance-help";
          text = ''
            cat <<'EOF'
${helpText}
            EOF
          '';
        };

      mkHelpApp = pkgs:
        let
          helpProgram = mkHelpProgram pkgs;
        in
        {
          type = "app";
          program = "${helpProgram}/bin/governance-help";
        };
    in
    {
      # Consumable machine-input output for the bootstrap pinned-flake-input
      # consumer. Governance exposes the package surface, but source data comes
      # from the ADR-derived governance-records projection, not local records/ or
      # generated/ directories in this repository.
      packages = forEachSystem (pkgs: {
        bootstrap-input =
          pkgs.runCommand "bootstrap-input" { } ''
            mkdir -p "$out"
            cp ${adrsRecords}/records/projections/governance-records-main/generated/bootstrap-input/bootstrap-minimal-acceptance.json "$out/bootstrap-input.json"
          '';
      });

      apps = forEachSystem (pkgs:
        let
          helpApp = mkHelpApp pkgs;
        in
        {
          help = helpApp;
          default = helpApp;
        });

      checks = forEachSystem (pkgs: {
        # feat-input-projection: reference gate function implementing the
        # continuity condition defined by ADR-derived records. adrs.git is the
        # authority for the condition; this check is governance.git's
        # non-authority reference implementation.
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
        # HEAD. This is a self-test for the reference gate function; real PR CI
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
        # authority is removed. The source data is the ADR-derived projection;
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

        # no-local-governance-records: active-tree purity guard. Governance must
        # not carry local accepted records or local generated cache after this
        # physical-removal proposal.
        no-local-governance-records =
          pkgs.runCommand "no-local-governance-records" { } ''
            set -euo pipefail
            if [ -e ${self}/records ] || [ -e ${self}/generated ]; then
              echo "governance must not carry local records/ or generated/ in the active tree" >&2
              exit 1
            fi
            test -f ${self}/MIGRATION_SOURCE.md
            touch "$out"
          '';

        nix-default-surface =
          let
            helpProgram = mkHelpProgram pkgs;
          in
          pkgs.runCommand "nix-default-surface"
            { nativeBuildInputs = [ pkgs.python3 ]; }
            ''
              set -euo pipefail
              ${helpProgram}/bin/governance-help > "$TMPDIR/help.txt"
              python3 ${self}/tools/check-nix-default-surface.py \
                --flake ${self}/flake.nix \
                --help "$TMPDIR/help.txt"
              touch "$out"
            '';
      });
    };
}

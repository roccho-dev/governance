{
  description = "governance: non-authority pure projection and continuity checks";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    adrsRecords = {
      url = "github:roccho-dev/adrs/main";
      flake = false;
    };
  };

  outputs =
    { self, nixpkgs, adrsRecords }:
    let
      systems = [
        "x86_64-linux"
      ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      bootstrapInputText = builtins.toJSON {
        kind = "governance.bootstrapInput.unavailable.v1";
        status = "blocked";
        source = "adrs";
        reason = "ADR-derived governance-records projection is not materialized in the current adrs input";
        boundary = "governance exposes a compatibility package only; this placeholder is not a decision source";
      };

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
          checks include ADR input presence, no local records/generated,
          Nix default surface, and provider CI YAML generated-output selftest.

        Dev shells:
          none exposed.

        Default policy:
          packages.default is forbidden unless a later accepted ADR allows one representative artifact.
          apps.default must be the same as apps.help.
      '';

      mkHelpProgram = pkgs:
        pkgs.writeShellScriptBin "governance-help" ''
          cat <<'EOF'
${helpText}
          EOF
        '';

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
      packages = forEachSystem (pkgs: {
        bootstrap-input =
          pkgs.runCommand "bootstrap-input" { } ''
            mkdir -p "$out"
            cat > "$out/bootstrap-input.json" <<'EOF'
${bootstrapInputText}
EOF
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
        adrs-input-presence =
          pkgs.runCommand "adrs-input-presence" { } ''
            set -euo pipefail
            test -d ${adrsRecords}
            touch "$out"
          '';

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

        provider-ci-yaml-selftest =
          pkgs.runCommand "provider-ci-yaml-selftest"
            { nativeBuildInputs = [ pkgs.python3 ]; }
            ''
              set -euo pipefail
              cd ${self}
              python3 tools/check-provider-ci-yaml.py selftest
              touch "$out"
            '';
      });
    };
}

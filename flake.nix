let
  base = import ./flake-base.nix;
in
base // {
  outputs = inputs@{ self, nixpkgs, adrsRecords }:
    let
      baseOut = base.outputs inputs;
      systems = [ "x86_64-linux" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      mkHelpProgram = pkgs: pkgs.writeShellScriptBin "governance-help" "echo governance";
      contractCheck = pkgs: name: root: pkgs.runCommand name { nativeBuildInputs = [ pkgs.python3 ]; } ''
        set -euo pipefail
        python3 ${self}/tools/check-external-package-contract.py ${root}
        touch "$out"
      '';
    in
    baseOut // {
      lib = (baseOut.lib or {}) // {
        mkExternalPackageBuildChecks = { packageOutputs }: {
          duckdb-python-build = packageOutputs.duckdb-python;
          duckdb-cli-build = packageOutputs.duckdb-cli;
          grafeo-python-build = packageOutputs.grafeo-python;
          grafeo-cli-build = packageOutputs.grafeo-cli;
        };
      };
      checks = forEachSystem (pkgs:
        (baseOut.checks.${pkgs.stdenv.hostPlatform.system} or {}) // {
          adrs-input-presence = pkgs.runCommand "adrs-input-presence" { nativeBuildInputs = [ pkgs.python3 ]; } ''
            set -euo pipefail
            test -d ${adrsRecords}
            python3 ${self}/tools/check-external-package-contract.py ${adrsRecords}
            python3 ${self}/tools/check-external-package-contract.py ${self}/fixtures/adrs/external-package-build-contract
            touch "$out"
          '';
          external-package-contract-real = contractCheck pkgs "external-package-contract-real" adrsRecords;
          external-package-contract-fixture = contractCheck pkgs "external-package-contract-fixture" "${self}/fixtures/adrs/external-package-build-contract";
        }
      );
    };
}

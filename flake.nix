{
  description = "governance: non-authority pure projection and continuity checks";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    adrsRecords = {
      url = "github:roccho-dev/adrs/main";
      flake = false;
    };
    uiLib = {
      url = "github:roccho-dev/ui/proposals";
      flake = false;
    };
  };

  outputs =
    { self, nixpkgs, adrsRecords, uiLib }:
    let
      systems = [ "x86_64-linux" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      bootstrapInputText = builtins.toJSON {
        kind = "governance.bootstrapInput.unavailable.v1";
        status = "blocked";
        source = "adrs";
        reason = "ADR-derived governance-records projection is not materialized in the current adrs input";
        boundary = "governance exposes a compatibility package only; this placeholder is not a decision source";
      };
      readmeArtifactModel = builtins.toJSON {
        kind = "document.model.v1";
        blocks = [
          { kind = "heading"; depth = 1; text = "governance README artifact"; }
          { kind = "heading"; depth = 2; text = "Purpose"; }
          { kind = "paragraph"; text = "Materialize the governance README artifact packet while keeping governance as a pure projection and check library."; }
          { kind = "heading"; depth = 2; text = "Authority boundary"; }
          { kind = "paragraph"; text = "README.md is a checked artifact. README.md is not an independent authority. Accepted decisions remain in adrs; governance projects and checks; ui renders Markdown bytes; repository CI exports the packet."; }
          { kind = "heading"; depth = 2; text = "Inputs"; }
          { kind = "list"; items = [
            "accepted projection bundle contract from adrs"
            "repoExplainView semantic contract from adrs"
            "document.model.v1 passed to ui-lib"
            "ui.markdown-document-renderer.v1 from roccho-dev/ui"
          ]; }
          { kind = "heading"; depth = 2; text = "Outputs / artifacts"; }
          { kind = "list"; items = [
            "README.md"
            "manifest.json"
            "sources.jsonl"
            "receipt.json"
          ]; }
          { kind = "heading"; depth = 2; text = "Checks"; }
          { kind = "list"; items = [
            "nix build .#readme-artifact emits the required packet"
            "nix flake check includes checks.readme-artifact"
            "artifact metadata declares nonAuthority and source closure provenance"
            "workflow upload is declared as artifact_exporter with source nix-output"
          ]; }
          { kind = "heading"; depth = 2; text = "Ownership / handoff"; }
          { kind = "paragraph"; text = "The governance repository owns artifact export. gov-lib does not upload artifacts. ui-lib does not own artifact lifecycle. The packet is evidence for downstream review, not a source of accepted meaning."; }
        ];
      };
      readmeArtifactSourcesText = ''
{"kind":"artifact.source.v1","artifact":"governance-readme","sourceKind":"acceptedProjectionBundleContract","ref":"roccho-dev/adrs#74","authority":false}
{"kind":"artifact.source.v1","artifact":"governance-readme","sourceKind":"repoExplainViewContract","ref":"roccho-dev/adrs#73","authority":false}
{"kind":"artifact.source.v1","artifact":"governance-readme","sourceKind":"artifactContract","ref":"roccho-dev/adrs#75","authority":false}
{"kind":"artifact.source.v1","artifact":"governance-readme","sourceKind":"renderer","ref":"roccho-dev/ui:proposals:src/markdown-document-renderer.mjs","authority":false}
      '';
      sourceClosureDigest = builtins.hashString "sha256" readmeArtifactSourcesText;
      helpText = ''
        governance flake surface

        Authority boundary:
          adrs decides accepted rules and exceptions.
          governance projects, checks, explains, plans, and renders from accepted inputs.
          generated README/docs/help/man text is not authority.

        Build:
          nix build .#bootstrap-input
            Build the explicit bootstrap compatibility package.
          nix build .#readme-artifact
            Build the non-authority README artifact packet.
          nix build .#claim-admission-check
            Build the stable non-authority claim admission checker CLI.
          nix build .
            Intentionally unsupported: governance has no packages.default.

        Run:
          nix run .
            Show this help.
          nix run .#help
            Show this help.
          nix run .#claim-admission-check -- selftest
            Run the exported claim admission checker selftest.

        Check:
          nix flake check
            Run all governance checks.
          checks include ADR input presence, no local records/generated,
          Nix default surface, provider CI YAML generated-output selftest,
          README artifact packet selftest, org admission gate selftest,
          claim port join compiler selftest, claim admission checker export selftest,
          claim check adoption monitor selftest, organization admission join fixture proof,
          and ADRS shadow monitor selftest.

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
        let helpProgram = mkHelpProgram pkgs; in {
          type = "app";
          program = "${helpProgram}/bin/governance-help";
        };
      mkClaimAdmissionCheckProgram = pkgs:
        pkgs.writeShellScriptBin "claim-admission-check" ''
          exec ${pkgs.python3}/bin/python3 ${self}/tools/claim-admission-check.py "$@"
        '';
      repoConventionChecksFor = pkgs:
        import ./nix/repo-convention-checks.nix { inherit pkgs; governanceSrc = self; };
      mkReadmeArtifact = pkgs:
        pkgs.runCommand "governance-readme-artifact" { nativeBuildInputs = [ pkgs.nodejs ]; } ''
          set -euo pipefail
          mkdir -p "$out"
          cat > "$TMPDIR/document.model.json" <<'EOF'
${readmeArtifactModel}
EOF
          UI_LIB_SRC=${uiLib} node ${self}/tools/render-readme-artifact-with-ui.mjs \
            --model "$TMPDIR/document.model.json" \
            --out "$out"
          cp "$TMPDIR/document.model.json" "$out/document.model.json"
          cat > "$out/sources.jsonl" <<'EOF'
${readmeArtifactSourcesText}
EOF
          readme_sha=$(sha256sum "$out/README.md" | cut -d' ' -f1)
          model_sha=$(sha256sum "$out/document.model.json" | cut -d' ' -f1)
          sources_sha=$(sha256sum "$out/sources.jsonl" | cut -d' ' -f1)
          render_result_sha=$(sha256sum "$out/render-result.json" | cut -d' ' -f1)
          cat > "$out/manifest.json" <<EOF
{
  "kind": "governance.readmeArtifact.manifest.v1",
  "repo": "roccho-dev/governance",
  "artifact": "README.md",
  "packetKind": "readme-artifact.v1",
  "nonAuthority": true,
  "sourceClosureDigest": "${sourceClosureDigest}",
  "renderer": "ui.markdown-document-renderer.v1",
  "modelDigest": "$model_sha",
  "sourcesDigest": "$sources_sha",
  "renderResultDigest": "$render_result_sha",
  "readmeDigest": "$readme_sha",
  "requiredFiles": ["README.md", "manifest.json", "sources.jsonl", "receipt.json"]
}
EOF
          manifest_sha=$(sha256sum "$out/manifest.json" | cut -d' ' -f1)
          cat > "$out/receipt.json" <<EOF
{
  "kind": "governance.readmeArtifact.receipt.v1",
  "repo": "roccho-dev/governance",
  "status": "success",
  "authority": false,
  "nonAuthority": true,
  "source": "nix-output",
  "sourceClosureDigest": "${sourceClosureDigest}",
  "outputs": {
    "README.md": "$readme_sha",
    "manifest.json": "$manifest_sha",
    "sources.jsonl": "$sources_sha",
    "document.model.json": "$model_sha",
    "render-result.json": "$render_result_sha"
  }
}
EOF
        '';
    in
    {
      lib = forEachSystem (pkgs: {
        repoConventionChecks = repoConventionChecksFor pkgs;
      });
      packages = forEachSystem (pkgs: let claimAdmissionCheckProgram = mkClaimAdmissionCheckProgram pkgs; in {
        bootstrap-input = pkgs.runCommand "bootstrap-input" { } ''
          mkdir -p "$out"
          cat > "$out/bootstrap-input.json" <<'EOF'
${bootstrapInputText}
EOF
        '';
        readme-artifact = mkReadmeArtifact pkgs;
        claim-admission-check = claimAdmissionCheckProgram;
      });
      apps = forEachSystem (pkgs: let
        helpApp = mkHelpApp pkgs;
        claimAdmissionCheckProgram = mkClaimAdmissionCheckProgram pkgs;
      in {
        help = helpApp;
        default = helpApp;
        claim-admission-check = {
          type = "app";
          program = "${claimAdmissionCheckProgram}/bin/claim-admission-check";
        };
      });
      checks = forEachSystem (pkgs: let readmeArtifact = mkReadmeArtifact pkgs; in {
        adrs-input-presence = pkgs.runCommand "adrs-input-presence" { } ''
          set -euo pipefail
          test -d ${adrsRecords}
          touch "$out"
        '';
        adrs-shadow-monitor-selftest = pkgs.runCommand "adrs-shadow-monitor-selftest" { nativeBuildInputs = [ pkgs.python3 pkgs.git ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/adrs-shadow-monitor.py \
            --adrs-path ${adrsRecords} \
            --target-ref flake-adrs-input \
            --report "$TMPDIR/adrs-shadow-monitor.json" \
            --fail-on-alert
          test -s "$TMPDIR/adrs-shadow-monitor.json"
          touch "$out"
        '';
        no-local-governance-records = pkgs.runCommand "no-local-governance-records" { } ''
          set -euo pipefail
          if [ -e ${self}/records ] || [ -e ${self}/generated ]; then
            echo "governance must not carry local records/ or generated/ in the active tree" >&2
            exit 1
          fi
          test -f ${self}/MIGRATION_SOURCE.md
          touch "$out"
        '';
        nix-default-surface = pkgs.runCommand "nix-default-surface" { } ''
          set -euo pipefail
          ${mkHelpProgram pkgs}/bin/governance-help > "$TMPDIR/help.txt"
          test -s "$TMPDIR/help.txt"
          touch "$out"
        '';
        provider-ci-yaml-selftest = pkgs.runCommand "provider-ci-yaml-selftest" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/check-provider-ci-yaml.py selftest
          touch "$out"
        '';
        org-admission-gate-selftest = pkgs.runCommand "org-admission-gate-selftest" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/check-org-admission-gate.py selftest
          touch "$out"
        '';
        claim-port-join-compiler-selftest = pkgs.runCommand "claim-port-join-compiler-selftest" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/compile-claim-port-joins.py selftest
          touch "$out"
        '';
        claim-admission-check-export = pkgs.runCommand "claim-admission-check-export" { } ''
          set -euo pipefail
          ${mkClaimAdmissionCheckProgram pkgs}/bin/claim-admission-check selftest > "$TMPDIR/claim-admission-check.json"
          grep -q '"kind": "governance.claimAdmissionCheck.selftest.v1"' "$TMPDIR/claim-admission-check.json"
          grep -q '"status": "pass"' "$TMPDIR/claim-admission-check.json"
          touch "$out"
        '';
        claim-check-adoption-monitor-selftest = pkgs.runCommand "claim-check-adoption-monitor-selftest" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/check-claim-check-adoption-monitor.py selftest > "$TMPDIR/claim-check-adoption-monitor.json"
          grep -q '"kind": "governance.claimCheckAdoptionMonitor.selftest.v1"' "$TMPDIR/claim-check-adoption-monitor.json"
          grep -q '"status": "pass"' "$TMPDIR/claim-check-adoption-monitor.json"
          touch "$out"
        '';
        org-admission-join-fixture-proof = pkgs.runCommand "org-admission-join-fixture-proof" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          set -euo pipefail
          cd ${self}
          python3 tools/check-org-admission-join-fixture.py
          touch "$out"
        '';
        readme-artifact = pkgs.runCommand "readme-artifact-check" { } ''
          set -euo pipefail
          test -s ${readmeArtifact}/README.md
          test -s ${readmeArtifact}/manifest.json
          test -s ${readmeArtifact}/sources.jsonl
          test -s ${readmeArtifact}/receipt.json
          grep -q 'README.md is not an independent authority' ${readmeArtifact}/README.md
          grep -q '"nonAuthority": true' ${readmeArtifact}/manifest.json
          grep -q '"sourceClosureDigest"' ${readmeArtifact}/manifest.json
          grep -q '"status": "success"' ${readmeArtifact}/receipt.json
          grep -q '"source": "nix-output"' ${readmeArtifact}/receipt.json
          touch "$out"
        '';
        repo-convention-selftest = (repoConventionChecksFor pkgs {
          src = self;
        }).repo-convention;
      });
    };
}

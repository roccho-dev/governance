{ self }:
let
  producerTool = ../tools/check-package-gov-package-output-provenance.py;
  producerDigest = builtins.hashString ''sha256'' (
    builtins.readFile producerTool + builtins.readFile ./gov-package-output-producer.nix
  );
  defaultProducerRev =
    if self ? rev then self.rev
    else if self ? dirtyRev then self.dirtyRev
    else ''unknown'';
  inline = content: { inherit content; };
  mkConfig = args: {
    kind = ''govPackageOutputProducer.config.v1'';
    repoId = args.repoId;
    repoClass = args.repoClass;
    repoPurpose = args.repoPurpose or '''';
    projectionMode = args.projectionMode or ''proposal-preview'';
    status = args.status or (args.projectionMode or ''proposal-preview'');
    sourceRefs = args.sourceRefs or [];
    producer = {
      producerRepo = args.producerRepo or ''roccho-dev/governance'';
      producerRev = args.producerRev or defaultProducerRev;
      producerDigest = args.producerDigest or (''sha256:'' + producerDigest);
      generatedBy = args.generatedBy or ''nix/gov-package-output-producer.nix:mkGovPackageOutput'';
    };
    inputs = {
      packages = inline args.packageInventory;
      assertions = inline args.packageAssertions;
      receipts = inline args.packageReceipts;
      readmeProjectionReceipt = inline args.readmeProjectionReceipt;
      providerCi = inline args.providerCi;
      findings = inline (args.findings or ''{"kind":"govPackageFinding.v1","status":"none"}\n'');
      admission = inline args.admission;
      sourcePaths = args.sourcePaths or [];
    };
  };
  mkGovPackageOutput = args:
    let config = builtins.toJSON (mkConfig args); in
    args.pkgs.runCommand ''gov-package-output'' { nativeBuildInputs = [ args.pkgs.python3 ]; } ''
      set -euo pipefail
      cat > config.json <<'EOF'
${config}
EOF
      python3 ${self}/tools/check-package-gov-package-output-provenance.py build --config config.json --out $out
    '';
  mkGovPackageOutputCheck = args:
    let
      sourceRootArgs = if args ? sourceRoot then ''--source-root ${args.sourceRoot}'' else '''';
      revArgs = if args ? producerRev then ''--producer-rev ${args.producerRev}'' else '''';
      digestArgs = if args ? producerDigest then ''--producer-digest ${args.producerDigest}'' else '''';
    in
    args.pkgs.runCommand ''gov-package-output-provenance-check'' { nativeBuildInputs = [ args.pkgs.python3 ]; } ''
      set -euo pipefail
      python3 ${self}/tools/check-package-gov-package-output-provenance.py verify \
        --packet ${args.packet} \
        --producer-repo ${args.producerRepo or ''roccho-dev/governance''} \
        ${sourceRootArgs} ${revArgs} ${digestArgs} \
        --require-pass > report.json
      test -s report.json
      touch $out
    '';
in {
  inherit mkGovPackageOutput mkGovPackageOutputCheck;
  boundary = ''producer/verifier evidence only; no final gate, cutover, or branch protection claim'';
}

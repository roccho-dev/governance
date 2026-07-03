{
  description = ''Downstream govPackageOutput producer example'';

  inputs = {
    nixpkgs.url = ''github:NixOS/nixpkgs/nixos-unstable'';
    governance.url = ''github:roccho-dev/governance/proposals'';
  };

  outputs = { self, nixpkgs, governance }:
    let
      system = ''x86_64-linux'';
      pkgs = nixpkgs.legacyPackages.${system};
      govProducer = import ''${governance}/nix/gov-package-output-producer.nix'' { self = governance; };
      packet = govProducer.mkGovPackageOutput {
        inherit pkgs;
        repoId = ''roccho-dev/example'';
        repoClass = ''feature_repo'';
        repoPurpose = ''example downstream repo consuming governance input'';
        sourceRefs = [ ''example'' ];
        packageInventory = ''
          {"kind":"govPackageRow.v1","repoId":"roccho-dev/example","packageId":"example","status":"example"}
        '';
        packageAssertions = ''
          {"kind":"govPackageAssertion.v1","repoId":"roccho-dev/example","packageId":"example","assertion":"example package follows its contract","status":"example"}
        '';
        packageReceipts = ''
          {"kind":"govPackageReceipt.v1","repoId":"roccho-dev/example","packageId":"example","status":"present"}
        '';
        readmeProjectionReceipt = ''
          {"kind":"readmeProjectionReceipt.v1","repoId":"roccho-dev/example","surfacePath":"README.md","status":"pass","nonAuthority":true}
        '';
        providerCi = ''
          {"kind":"govProviderCiRow.v1","repoId":"roccho-dev/example","workflow":"CI","role":"evidence-producer","status":"example"}
        '';
        admission = ''
          {"kind":"govPackageAdmission.v1","repoId":"roccho-dev/example","packageId":"example","admission":"not-final","status":"example"}
        '';
        sourcePaths = [
          { role = ''repoReadme''; path = ./README.md; required = true; }
        ];
      };
    in {
      packages.${system}.gov-package-output = packet;
      checks.${system}.gov-package-output = govProducer.mkGovPackageOutputCheck { inherit pkgs packet; };
    };
}

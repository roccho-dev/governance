{
  description = "minimal feat consumer of governance repo-governance package";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    governance.url = "github:roccho-dev/governance";
    governance.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, governance, ... }:
    {
      checks = governance.lib.mkRepoGovernanceChecks {
        inherit nixpkgs;
        systems = [ "x86_64-linux" ];
        repoSnapshot = ./governance/repo-governance.json;
      };
    };
}

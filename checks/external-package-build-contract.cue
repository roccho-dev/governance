package adr

Decision: {
  uri: "infra://package/external-nix-build-contract"
  status: "Accepted"
  spec: {
    kind: "externalNixPackageBuildContract.v1"
    requiredPackageFacts: _
    requiredChecks: _
    profiles: {
      duckdb: _
      grafeo: {
        requiredFeature: "jsonl-import"
      }
    }
  }
}

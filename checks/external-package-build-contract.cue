package adr

Decision: {
  uri: "infra://package/external-nix-build-contract"
  status: "Accepted"
  spec: #ExternalNixPackageBuildContractV1
}

#ExternalNixPackageBuildContractV1: {
  kind: "externalNixPackageBuildContract.v1"
  requiredPackageFacts: [...string]
  requiredChecks: [...string]
  profiles: {
    duckdb: {
      outputs: [...string]
      sourcesAllowed: [...string]
      requiredProofs: [...string]
    }
    grafeo: {
      outputs: [...string]
      sourcesAllowed: [...string]
      requiredFeature: "jsonl-import"
      requiredProofs: [...string]
    }
  }
}

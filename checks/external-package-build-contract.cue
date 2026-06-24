package adr

Decision: {
  uri: "infra://package/external-nix-build-contract"
  status: "Accepted"
  spec: #ExternalNixPackageBuildContractV1
}

#ExternalNixPackageBuildContractV1: {
  kind: "externalNixPackageBuildContract.v1"
  requiredPackageFacts: [
    "packageId",
    "role",
    "sourceProvider",
    "sourceIdentity",
    "sha256",
    "systems",
    "outputNames",
    "featureRequirements",
    "proofs",
    "receiptKind",
  ]
  requiredChecks: [
    "sourceFixed",
    "providerAllowed",
    "outputRole",
    "versionParityOrWaiver",
    "nixParse",
    "nixFormatWhenAccepted",
    "nixDeadCodeWhenAccepted",
    "flakeEval",
    "packageBuild",
    "positiveProof",
    "negativeProof",
    "receiptSchema",
    "generatedBoundary",
    "directGovernanceDependency",
  ]
  profiles: {
    duckdb: {
      outputs: ["pythonLibrary", "cli"]
      sourcesAllowed: ["pypi", "githubRelease"]
      requiredProofs: ["pythonImport", "cliRuns", "jsonlPythonValues", "jsonlCliValues", "malformedJsonlFails"]
    }
    grafeo: {
      outputs: ["pythonLibrary", "cli"]
      sourcesAllowed: ["pypiSource", "githubRelease", "githubSource"]
      requiredFeature: "jsonl-import"
      requiredProofs: ["pythonImport", "realJsonlImport", "propertyValueCheck", "persistenceWhenClaimed", "cliImportQueryValidate", "malformedJsonlFails"]
    }
  }
}

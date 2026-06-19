// records/specs/projected-policy-entry-contract.v1.jsonl — bootstrap-shaped
// projected policy entry output contract.
// Bound via policy/interface.json: cue vet -d '#ProjectedPolicyEntryContract'.
package policy

#ProjectedPolicyEntryContract: {
	kind:                   "governance.projectedPolicyEntryContract.v1"
	contractId:             string & !=""
	packageId:              =~"^[a-z0-9][a-z0-9_-]*$"
	status:                 "proposal-candidate" | "accepted"
	authority:              string & !=""
	recordedAt:             string & !=""
	generatedIsAuthority:   false
	migrationAuthority:     false
	cutoverAuthority:       false
	acceptedArtifactExists: bool
	requiredOutputs: [...string & !=""]
	bootstrapConsumerContract: {
		acceptedEnv:         "policy-entry.accepted.env"
		policy:              "policy.md"
		rules:               "rules/*.md"
		acceptedEnvRequired: [...string & !=""]
	}
	failClosedRules: [...string & !=""]
	unacceptedBlockers: [...string & !=""]
	source: {...}
	if acceptedArtifactExists == false {
		status: "proposal-candidate"
	}
	...
}

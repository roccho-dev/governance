// records/feat/build-evidence.v1.jsonl — feat build-verification evidence.
// Bound via policy/interface.json: cue vet -d '#BuildEvidence'.
//
// Two row profiles share this ledger:
//   - preflight rows (promotableBuildEvidence=false): non-nix preflight runs;
//     they may carry projectionDigest/authorityBoundary and never enter the
//     evidenced set of the obligation-debt report.
//   - promotable rows (promotableBuildEvidence=true): real `nix build` runs of
//     the contract's requiredOutputs/requiredChecks; these MUST pin their full
//     provenance (ops branch+rev, governance rev, catalog sha) and are what
//     tools/records-gate.py counts when computing
//     accepted-without-feat-evidence debt.
package policy

#BuildEvidence: {
	kind:          "governance.featBuildEvidence.v1"
	schemaVersion: "v1"
	evidenceId:    string & !=""
	packageId:     =~"^[a-z0-9][a-z0-9_-]*$"
	recordedAt:    string & !=""
	command:       string & !=""
	status:        "pass" | "fail"
	promotableBuildEvidence: bool
	executionProfile:        string & !=""
	finalNixStatus:          "pass" | "fail" | "not-run"
	requiredChecksObserved: [...string & !=""]
	requiredOutputsObserved: [...string & !=""]
	// preflight-profile fields (optional; absorb historical row variance).
	authorityBoundary?: string & !=""
	projectionDigest?:  =~"^[0-9a-f]{64}$"
	flakeCheckStatus?:  "pass" | "fail"
	if promotableBuildEvidence == true {
		// promotable evidence must come from a passing nix-final run and
		// pin the exact revisions/catalog it was verified against.
		status:          "pass"
		finalNixStatus:  "pass"
		opsBranch!:      string & !=""
		opsRev!:         =~"^[0-9a-f]{40}$"
		governanceRev!:  =~"^[0-9a-f]{40}$"
		catalogSha256!:  =~"^[0-9a-f]{64}$"
	}
	...
}

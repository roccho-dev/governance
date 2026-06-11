// records/decisions/*.jsonl — accepted governance decision records.
package policy

// records/decisions/specsless-final-cutover-acceptance.v1.jsonl
#SpecslessFinalCutoverAcceptance: {
	kind:       "governance.specslessFinalCutoverAcceptance.v1"
	recordId:   string & !=""
	recordedAt: string & !=""
	status:     "accepted"
	respondsTo: {
		issueLedger:   string & !=""
		issueId:       string & !=""
		closeCriteria: string & !=""
		...
	}
	readinessFinal: {
		mode:   "final"
		status: "pass"
		...
	}
	readinessWorkspace: {...}
	gates: {...}
	catalogSha256: {
		packageCatalog: =~"^[0-9a-f]{64}$"
		placementTable: =~"^[0-9a-f]{64}$"
		...
	}
	branches: {...}
	// specs repo physical deletion (task 9) is deferred to explicit user Go.
	deletionExecuted: bool
	deletionNote:     string
	evidenceArchive:  string & !=""
	...
}

// records/decisions/specs-main-proposal-admission.v1.jsonl
#SpecsMainProposalAdmissionDecision: {
	kind:              "governance.specsMainProposalAdmissionDecision.v1"
	decisionId:        string & !=""
	decision:          string & !=""
	rule:              string & !=""
	status:            "accepted"
	authority:         string & !=""
	scope:             string & !=""
	rationale:         string & !=""
	recordedAt:        string & !=""
	forbiddenPatterns: [...string]
	allowedExceptions: [...string]
	...
}

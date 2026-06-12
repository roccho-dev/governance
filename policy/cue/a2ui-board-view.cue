package policy

#A2uiBoardViewV3Gate: {
	kind: "governance.a2uiBoardViewV3Gate.v1"
	gateId: string & !=""
	requirementId: string & =~"^R[1-7]$"
	destructiveCaseIds: [...string]
	blocking: bool
	assertion: string & !=""
	evidence: [...{
		repo: string & !=""
		command: string & !=""
	}]
	...
}

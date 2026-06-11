// records/feat/breaking-change-evidence.v1.jsonl — feat verification evidence
// required by policy/promotion-policy.md for BREAKING changes (changes to an
// already-implemented accepted contract). Net-new acceptance does NOT require
// this record (gate + obligation-debt tracking only).
//
// The ledger is seeded with one self-describing schema-establishment row
// (G2 precedent: typed ledgers are never empty files); that row is excluded
// from the relational constraint breaking-change-without-feat-evidence
// (policy/cue/relational.cue #All; report-side query
// policy/sql/report/breaking-change-evidence.sql).
package policy

#BreakingChangeEvidence: {
	kind:       "governance.breakingChangeEvidence.v1"
	evidenceId: string & !=""
	recordedAt: string & !=""
	// discriminator: true only on the single schema-establishment row.
	schemaEstablishment: *false | bool
	if schemaEstablishment == true {
		schema!: {...}
	}
	if schemaEstablishment == false {
		// evidence row: binds the breaking contract revision to a passing feat gate.
		packageId!:   =~"^[a-z0-9][a-z0-9_-]*$"
		changeClass!: "breaking"
		// recordDigest of the previously implemented (superseded) contract row.
		baselineRecordDigest!: =~"^[0-9a-f]{64}$"
		// recordDigest of the new contract row this evidence admits.
		newRecordDigest!: =~"^[0-9a-f]{64}$"
		featGate!: {
			command: string & !=""
			status:  "pass"
			...
		}
	}
	...
}

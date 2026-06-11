// policy/cue/relational.cue — cross-ledger relational constraints (#All).
// CUE port of the former blocking DuckDB assertions (now report-only under
// policy/sql/report/): every "violations" list must be empty
// (list.MaxItems(0)); a non-empty list fails `cue vet` and prints the
// violating rows {rule, packageId, detail}.
//
// Vetted via the declaration-driven plumbing (policy/interface.json): the
// grouped jsonl ledgers are bundled into one labeled JSON
// {contracts, membership, placement, edges, evidence} and vetted with
//   cue vet policy/cue/*.cue all.json -d '#All'
//
// Relaxation level intentionally mirrors the SQL originals:
//   - membership admits contract status {accepted, planned}; the stricter
//     accepted-only target stays NON-blocking debt (records-gate --report,
//     debtClass membership-member-not-accepted).
//   - catalog-required-fields enforces 18 of the 21 nominally-required
//     projection fields; dependencyUse/publicInterface/checkPackageContract
//     have known historical gaps and stay debt (debtClass catalog-field-gap).
//   - breaking-change-evidence is a promotion-policy stub
//     (policy/promotion-policy.md): no current contract declares
//     lifecycle.changeClass=breaking, and the schema-establishment evidence
//     row is excluded from the admit set.
package policy

import "list"

#All: {
	contracts: [...{...}] // records/specs/package-contract.v1.jsonl
	membership: [...{...}] // records/specs/catalog-membership.v1.jsonl
	placement: [...{...}] // records/specs/repo-placement.v1.jsonl
	edges: [...{...}] // records/specs/dependency-edge.v1.jsonl
	evidence: [...{...}] // records/feat/breaking-change-evidence.v1.jsonl

	// ---- projected id sets -------------------------------------------------
	_contractIds: [for c in contracts {c.packageId}]
	_admissibleIds: [for c in contracts if c.status == "accepted" || c.status == "planned" {c.packageId}]
	_memberIds: [for m in membership if m.inSpecPackages == true {m.packageId}]
	_allMembershipIds: [for m in membership {m.packageId}]

	// catalog projection source fields machine-enforced for membership rows
	// (18 of the 21 nominally required; see header note).
	_catalogRequiredFields: ["packageRole", "responsibility", "mission", "provides",
		"requires", "envNeeds", "releaseNeeds", "artifactContract",
		"runtimeRequirements", "preflightRequiredTools",
		"officialOutput", "packageContents", "forbiddenOutputs",
		"allowedCompatCommands", "requiredCommands", "blockedWhen",
		"outputReviewGate", "requiredCheckPackages"]

	// every named violation list must be empty for the gate to pass.
	violations: [string]: list.MaxItems(0)

	// 1. membership-packageid-in-contract (was membership-packageid-in-contract.sql):
	//    every catalog member (inSpecPackages=true) references an existing
	//    package-contract row with admissible status {accepted, planned}.
	violations: "membership-packageid-in-contract": [
		for pid in _memberIds
		if !list.Contains(_admissibleIds, pid)
		let statuses = [for c in contracts if c.packageId == pid {c.status}] {
			{
				rule:      "membership-packageid-in-contract"
				packageId: pid
				detail:    *statuses[0] | "<missing-contract>"
			}
		},
	]

	// 2. membership-no-duplicates (was membership-no-duplicates.sql):
	//    the catalog-membership ledger has no duplicate packageId
	//    (the 126-member set is a set).
	violations: "membership-duplicate-packageid": [
		for i, pid in _allMembershipIds
		if list.Contains(list.Slice(_allMembershipIds, i+1, len(_allMembershipIds)), pid) {
			{rule: "membership-duplicate-packageid", packageId: pid, detail: "duplicate"}
		},
	]

	// 3. package-contract-integrity (was package-contract-integrity.sql):
	// 3a. package-contract packageId is unique.
	violations: "package-contract-duplicate-packageid": [
		for i, pid in _contractIds
		if list.Contains(list.Slice(_contractIds, i+1, len(_contractIds)), pid) {
			{rule: "package-contract-duplicate-packageid", packageId: pid, detail: "duplicate"}
		},
	]
	// 3b. package-contract recordDigest is a non-empty sha256 hex.
	violations: "package-contract-bad-record-digest": [
		for c in contracts
		let d = *(c.recordDigest & string) | null
		if d == null || !(d =~ "^[0-9a-f]{64}$") {
			{rule: "package-contract-bad-record-digest", packageId: c.packageId, detail: *d | "<null>"}
		},
	]

	// 4. repo-placement-packageid-in-contract (was
	//    repo-placement-packageid-in-contract.sql): every repo-placement row
	//    references an existing package-contract packageId.
	violations: "repo-placement-packageid-not-in-contract": [
		for p in placement
		if !list.Contains(_contractIds, p.packageId) {
			{rule: "repo-placement-packageid-not-in-contract", packageId: p.packageId, detail: "<missing-contract>"}
		},
	]

	// 5. dependency-edge-endpoints-in-contract (was
	//    dependency-edge-endpoints-in-contract.sql): edge endpoints resolve to
	//    existing package-contract packageIds.
	violations: "dependency-edge-from-not-in-contract": [
		for e in edges
		if !list.Contains(_contractIds, e.fromPackageId) {
			{rule: "dependency-edge-from-not-in-contract", packageId: e.fromPackageId, detail: "requires=\(e.requires)"}
		},
	]
	violations: "dependency-edge-to-not-in-contract": [
		for e in edges
		for t in e.toPackageIds
		if !list.Contains(_contractIds, t) {
			{rule: "dependency-edge-to-not-in-contract", packageId: t, detail: "from=\(e.fromPackageId)"}
		},
	]

	// 6. catalog-required-fields-nonnull (was
	//    catalog-required-fields-nonnull.sql): membership rows must carry an
	//    object source.rawDefinition (make-spec-catalog.py hard-fails
	//    otherwise) with the 18 enforced catalog source fields non-null.
	violations: "membership-rawdefinition-not-object": [
		for c in contracts
		if list.Contains(_memberIds, c.packageId)
		let rd = *(c.source.rawDefinition & {...}) | null
		if rd == null {
			{rule: "membership-rawdefinition-not-object", packageId: c.packageId, detail: "<not-object>"}
		},
	]
	violations: "catalog-required-field-null": [
		for c in contracts
		if list.Contains(_memberIds, c.packageId)
		let rd = *(c.source.rawDefinition & {...}) | null
		if rd != null
		for f in _catalogRequiredFields
		let present = [for k, v in rd if k == f && v != null {true}]
		if len(present) == 0 {
			{rule: "catalog-required-field-null", packageId: c.packageId, detail: f}
		},
	]

	// 7. breaking-change-evidence (was breaking-change-evidence.sql;
	//    promotion-policy stub): every contract declaring
	//    lifecycle.changeClass=breaking must be admitted by a
	//    non-schema-establishment breakingChangeEvidence row matching
	//    packageId + newRecordDigest. lifecycle is a plain string on all
	//    current rows; the default-disjunction below resolves to "<none>"
	//    whenever lifecycle is not a struct carrying changeClass.
	_breaking: [
		for c in contracts
		let cc = *(c.lifecycle & {changeClass!: string, ...}).changeClass | "<none>"
		if cc == "breaking" {
			{packageId: c.packageId, recordDigest: c.recordDigest}
		},
	]
	_evidenceAdmits: [
		for e in evidence
		let se = *(e.schemaEstablishment & bool) | false
		if se != true
		let pid = *(e.packageId & string) | null
		let nrd = *(e.newRecordDigest & string) | null
		if pid != null && nrd != null {
			"\(pid)::\(nrd)"
		},
	]
	violations: "breaking-change-without-feat-evidence": [
		for b in _breaking
		if !list.Contains(_evidenceAdmits, "\(b.packageId)::\(b.recordDigest)") {
			{rule: "breaking-change-without-feat-evidence", packageId: b.packageId, detail: "recordDigest=\(b.recordDigest)"}
		},
	]
}

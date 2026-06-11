// records/specs/package-contract.v1.jsonl — authoritative per-package contract.
// Vetted by tools/records-gate.py: cue vet -d '#PackageContract'.
package policy

#PackageContract: {
	kind:         "governance.packageContract.v1"
	packageId:    =~"^[a-z0-9][a-z0-9_-]*$"
	specId:       string & !=""
	status:       "accepted" | "planned"
	recordDigest: =~"^[0-9a-f]{64}$"
	authority:    string & !=""
	recordedAt:   string & !=""
	// curated feat-subset definition (consumed by make-feat-input.py).
	definition: {...}
	// source.rawDefinition carries the full original specs definition; it is
	// the catalog projection input for membership packages. Object-ness for
	// membership rows is enforced relationally in
	// policy/sql/assertions/catalog-required-fields-nonnull.sql.
	source: {...}
	lifecycle:     _
	schemaVersion: _
	...
}

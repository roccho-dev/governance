// records/specs/dependency-edge.v1.jsonl — package dependency lock edges.
// Cardinality contract (mirrors specsless_readiness.py):
//   externalOrNotYetModeled => toPackageIds == []
//   packageId | providedCapability => exactly one resolved target
package policy

#DependencyEdge: {
	kind:          "governance.dependencyEdge.v1"
	fromPackageId: =~"^[a-z0-9][a-z0-9_-]*$"
	requires:      string & !=""
	resolution:    "packageId" | "providedCapability" | "externalOrNotYetModeled"
	toPackageIds:  [...string]
	if resolution == "externalOrNotYetModeled" {
		toPackageIds: []
	}
	if resolution != "externalOrNotYetModeled" {
		toPackageIds: [=~"^[a-z0-9][a-z0-9_-]*$"]
	}
	recordedAt?:    string & !=""
	schemaVersion?: _
	...
}

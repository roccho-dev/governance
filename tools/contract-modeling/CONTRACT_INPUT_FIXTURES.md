# Contract input boundary: synthetic fixture slice

This slice supplies exact bytes to existing JSONL selection, the existing Ops
Required adapter, and the existing pure contract comparator. It adds two small
readers, not another meaning source, admission mechanism, comparator or service.

The trusted caller supplies source pins independently of the input producer and
chooses the executable adapter/comparator. The existing source-reference fields
remain `repository`, exact `revision`, `path`, and `digest`. A digest, Git-shaped
descriptor, or native object is integrity evidence, not authentication or
admission. Source-root ownership and actual admission remain caller obligations.

`BytesReader` wraps a callback that supplies bytes, source identity and acquisition
completeness. Its readback always says `retained=False`: matching bytes do not
prove a holding ref. `GitObjectReader` reuses the existing Cold native reader,
resolves the literal holding ref once, checks the selected commit/tree, and reads
regular blob bytes at that fixed commit. Its native readback includes the actual
holding ref, holding commit, selected commit/tree, blob and mode. Subsequent file
reads do not resolve the branch again.

`compare_inputs` passes packet and independently pinned admission unchanged to
the same existing comparator. CLOSED/OPEN/INVALID/UNKNOWN and exits 0/2/3/4 remain
that comparator's result. In particular `{}` admission stays UNKNOWN. Input
acquisition errors have an explicit non-PASS status; unexpected programming
exceptions are not converted to completion. No input field can choose validator
code, codec or admission configuration.

## What the fixture actually connects

The test creates only synthetic data in an owned directory below this worktree's
`.artifacts/contract-input-fixtures`. Its finite path is:

1. A synthetic `adr_raw_event.v1` meaning record is retained in fixture Git.
2. An independent source pin selects it through either reader.
3. The existing `tools/package_contract_targets/ops.py::required_contract` derives
   Required from the selected decision/rollout. Independent literal provision and
   expected contract values verify that derivation, rather than copying its output.
4. Synthetic Observation/Receipt and independently configured fixture admission
   feed the existing Ops comparator, loaded from fixed public Ops revision
   `5eb98c82417b399978c1e38aebab5e3fb39752d4`, core blob
   `9613c92deb6ee12b335863a36261268976ad9cc5`.
5. A derived same-record result references the original meaning source, Required
   and candidate. The fixture stores it in another native Git generation and
   rereads that fixed generation. The old inputs are recomputed before comparison.

Those holding refs exist in the owned temporary fixture repository during the
test. Cleanup removes that disposable repository; this is not a claim of durable
production capture or of evidence retained after the test's lifecycle.

The adapter's mandatory `real` receipt-grade string is a **synthetic claimed input
value** in this test, not a real provider execution. The comparator reports fixture
grade and non-authority. This proof creates no actual ADRS admission, execution
Receipt, production Current, operational adoption or real evidence retention.

```mermaid
flowchart TD
  A[Trusted caller: independent pins and fixed code] --> B[Fixture JSONL bytes via callback or fixed Git objects]
  B --> C[Select original; existing Ops adapter derives Required]
  C --> D[Independent provision and synthetic O/Receipt/admission]
  D --> E[One existing pure comparator; unchanged four states]
  E --> F[Same-record derived result; owned fixture Git retention]
  F --> R[Fixed-generation reread and recomputation; P independent rebuttal]
  R -->|Necessary fixture checks pass| Z[Fixture slice complete; real path unproved]
  B -->|Input or identity failure| I[Caller corrects the first invalid input]
  I -->|New valid fixture input| B
  C -->|Implementation defect| W[Same writer makes the smallest fix]
  E -->|Implementation defect| W
  R -->|Concrete source counterexample| W
  W -->|Actual corrected code| C
  I -->|Authority or capability unavailable| U[Explicit unmet reason and reentry condition; stop]
```

The fixture also covers altered bytes/source identity, stale candidate, missing
input/admission, partial collections/acquisition, JSON duplicate keys/conflicting
records, invalid UTF-8, path traversal, symlinks, wrong commit/tree, ref expressions,
branch movement, executable-input fields, and rehashed result substitution.
Network socket use and Git fetch/clone/push/ls-remote are forbidden during tests.
Cleanup validates the owned root before removing any recursive fixture directory.

## Local reproduction

Use the existing native Git and Python runtimes. Point
`CONTRACT_INPUT_RUNTIME_ROOT` at the existing **public Ops** fixed read view that
retains the revision above. The runner checks its native core blob before loading
it; it does not fetch dependencies or inspect private ADRS data.

```powershell
$env:CONTRACT_INPUT_GIT = '<existing absolute native git executable>'
$env:CONTRACT_INPUT_RUNTIME_ROOT = '<public Ops fixed read view>'
python -m unittest discover -s tools/contract-modeling/tests -p test_contract_input.py -v
```

The tests require that explicit runtime source; missing setup fails rather than
silently skipping the consumer proof. Existing Ops comparator regressions can be
run separately from its verified fixed read view. Reader parity is exact equality
of comparator results, while acquisition/retention readbacks intentionally differ.

Local validation on 2026-10-18: all 11 fixture tests passed without skips, including
the existing CLI's four exit states. The unchanged public Ops core/edge suite also
passed all 33 tests without skips. These are local synthetic proofs, not public CI
or private real-input validation.

## Publication and claim boundary

This work is local and fixture-only. Existing source/final/Cold implementations,
admitted meanings, previous finite proofs, and unrelated worktrees remain intact.
It does not make the entire existing Gov final path provider independent: that
path still accepts filesystem bundles and obtains some real evidence through
Release/Actions artifacts. Real evidence-to-native-Git retention and real consumer
binding require separate work and proof.

No new workflow or provider effect is added. Current public Normal CI can acquire
and upload private ADRS source. Therefore remote push, PR creation and CI execution
are deliberately outside this slice until their publication boundary is reviewed;
a future public synthetic runner must not stand in for necessary private-data
verification. Local fixture success is never reported as a real-data, Git-only,
all-provider, whole-foundation or adoption success.

# Recursive contract-modeling admission

This directory implements the deterministic production compiler tracked by
`roccho-dev/governance#153` and specified by accepted `roccho-dev/adrs#234`.

## Accepted authority pin

```text
ADRS_PR=roccho-dev/adrs#241
ADRS_MERGE=458ab4267882083de0593754d1bf9766bf8d54da
DECISION_ID=01K0E1CM000000000000000234
CORRECTION_DECISION_ID=01K0E1CM000000000000000235
DECISION_DIGEST=cc7ac3d6618b31eb0a0979b8aa0e2bfaf6abd95646e45c740d154c8204cd00d1
RELEASE=recursive-contract-modeling-v1.0.1
```

## Boundary

- ADRS owns meaning, purpose, policy, waivers, and cutover decisions.
- Owners submit claims and evidence, not trusted admission results.
- Governance validates, reduces, derives, projects, and reports without meaning authority.
- Ops or the owning repository performs external effects and returns exact-target readback.
- Deprecated spec repositories remain preserved evidence only.

## Data flow

```text
claims
→ closed validation
→ supersession and recursive containment
→ derived eight-way admission
→ promotion-only current epoch
→ DuckDB gates and stable ABI
→ responsibility closure and exact-SHA receipts
```

The production proof includes two unrelated required governance packages, one
bounded model-only package, 36 mapped legacy responsibilities with zero unexplained,
replay equality, query/raw-access enforcement, expected-reason destructive cases,
and immutable Nix store materialization.

## Production cutover

The only blocking provider check remains:

```text
gov-final-scope-purpose-join / gate
```

That gate verifies the accepted ADRS identity, final frozen legacy inventory,
active legacy consumer count zero in the accepted universe, anti-reintroduction,
current package receipts, and the exact governance candidate. Migration completion
becomes true only after the admitted merge is observed by the existing push-only
post-effect readback.

## Run

```text
python3 -m unittest discover -s tools/contract-modeling/tests -p 'test_*.py'
python3 tools/check-contract-modeling-production-migration.py selftest
CANDIDATE_SHA=$(git rev-parse HEAD) bash tools/contract-modeling/run-proof.sh
```

Technical migration closure does not claim all-repository enforcement, business
outcome achievement, or corporate-sale achievement.


## Contract-drift composition and canonical acquisition

The source/fixture stage is merged. Issue #215 adds only the missing bounded
acquisition/normalization path from the existing technical owners; it does not
create a second comparator/compiler, a new semantic registry, or a new ADRS/CUE
adoption prerequisite.

Canonical source pins for this slice are:

```text
ops/proposals  = 8c44728263a02c5d693d41078021af876420d4a4
envs/proposals = c1a7658f142c82af4ad5cdeba23ee893ef662868
selected DEPLOY = bce3daab76c9a4565902205cc59bb443f6e68009
```

These are distinct identities. The current ops source owns requirement projection; the selected DEPLOY revision identifies the already-reviewed execution tuple. Neither is substituted for the other, and envs `c1a7658...` is not aliased to its older source/review SHAs.

These are merge/canonical identities. They are intentionally not replaced by
the older review-PR heads even when their source trees are byte-equal.

`contract-drift-acquisition` reads the actual ops runtime requirement owner
and the actual envs public contract projection from those pinned sources. The
selected relation is bound only by stable technical row IDs:

```text
binding           = jev-api
consumer_boundary = ops.voice-ui.consumer
```

The obligation key is derived from those stable IDs only. Compared values such
as consumer, stage, capability, provider and target are not used to rediscover
the envs row and are not embedded into K.

The selected K/U/profile is derived **before R acquisition** from the existing
runtime requirement constants, the stable technical selector and the target
validated by the existing ops runtime target validator. The semantic digest is
therefore fixed before the requirement row exists. That digest is then passed
to the existing ops requirement generator and to the existing envs stable-ID
selector. A missing/empty R cannot erase U or vacuously close coverage.
The normalized R/P packet is passed to the existing
`bin/contract_drift_phase2.py::compose()`, which invokes the one pinned ops
`contract-diff` implementation.

Production acquisition is exposed through the Nix-built `contract-drift-acquire`
entry. That wrapper fixes the ops/envs source roots and revisions at evaluation
time; callers cannot supply `--ops-root`, `--envs-root`, or claimed source
revisions. The raw Python `acquire-fixture` command remains available only for
fixture/development checks and always emits fixture-grade composition.

A source-grade target is never accepted as raw target JSON. Production accepts
an optional closed `governance.voiceUiApprovedTargetSelection.v1` packet only
when its exact bytes match an independently admitted digest and it binds:

```text
selected_deploy_revision = bce3daab76c9a4565902205cc59bb443f6e68009
envs_revision            = c1a7658f142c82af4ad5cdeba23ee893ef662868
target                    = closed Workers target validated by the canonical ops contract
```

If that provenance-bearing target input is absent, acquisition is `UNKNOWN`;
shape-valid fixture/invented target JSON cannot enter the production source-grade
path.

Already-produced observations and receipts may be supplied as closed normalized
packets together with an admitted `receipt id -> sha256(receipt)` map. The
acquisition layer performs no provider effect. Missing O/H remains
`EVIDENCE_MISSING`; incomplete or unadmitted evidence provenance becomes
`UNKNOWN`; admitted but mismatched attempt/epoch/source/target/slot/grade remains
typed `EVIDENCE_DRIFT` in the existing ops comparator. A valid admitted H can
remove `EVIDENCE_MISSING` without hiding independent contract drift.

The source-level O/H inventory is empty unless real observations/receipts are
provided by their own later boundary. Therefore missing required evidence
remains `EVIDENCE_MISSING`; file/name presence is never promoted to real proof.
If the approved Workers target input is unavailable, acquisition returns
`UNKNOWN` and does not invent account/Worker identity from the current Pages
provision.

The acquisition selftest fixes these failure classes against the canonical
source bytes:

- selected relation with missing R cannot vacuously close;
- Workers expectation + current Pages provision is typed target drift;
- stage/consumer/capability drift keeps the same K and never becomes supply loss;
- true stable-relation absence becomes `SUPPLY_MISSING`;
- required evidence absence remains `EVIDENCE_MISSING`;
- unavailable approved target is `UNKNOWN`;
- raw fixture target cannot mint production source-grade acquisition;
- source root/revision is fixed by the Nix production wrapper;
- source identity mismatch is rejected;
- closed O/H intake removes `EVIDENCE_MISSING` only with admitted receipt digest provenance;
- untrusted evidence is `UNKNOWN`, while attempt/source/target mismatches remain typed drift;
- identical exact inputs replay byte-identically;
- candidate/source labels never set final admission;
- #543/#544, new ADRS/CUE source families, workflow revival and provider effects
  are not inputs to this bounded composition.

The legacy `contract-drift-phase2` V24-V28 selftest is retained. Both checks
are non-authoritative and effect-free. Existing governance gates still own final
grade/residual/closure. The separate live-selected-consumer Red and ADRS #443
real provider/readback/application-acceptance work remain required overall and
are not hidden by this source check.

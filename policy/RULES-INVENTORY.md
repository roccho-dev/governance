# RULES-INVENTORY — bespoke validator rules absorbed/absorbable by records-gate

棚卸し対象: governance records に対して規則を強制している既存 bespoke validator。
records-gate(`tools/records-gate.py` = CUE schema vet + DuckDB assertion)への
吸収対象 list。**退役はまだ行わない**(本 inventory は吸収マップであり、validator
削除の許可ではない)。

凡例 — Gate 列:
- `cue:<file>#<Def>` — policy/cue/ の schema で吸収済
- `sql:<file>` — policy/sql/assertions/ の assertion で吸収済
- `debt` — 非 blocking。records-gate `--report` の obligation-debt JSON で可視化
- `out-of-scope` — records 検査ではない(projection 実行・artifact 検査・workspace 配線等)。records-gate の対象外として残置

## 1. tools/make-spec-catalog.py(hard-fail 条件)

| # | 規則 | Gate |
|---|------|------|
| 1.1 | catalog-membership の kind は `specs.catalogMembership.v1` のみ | cue:catalog-membership.cue#CatalogMembership |
| 1.2 | membership set(inSpecPackages=true)は空であってはならない | sql:membership-packageid-in-contract.sql(空なら contracts との差が空でも emit 0 件 = make-spec-catalog 側で fail 継続)+ cue(required file) |
| 1.3 | membership packageId ⊆ package-contract(存在必須) | sql:membership-packageid-in-contract.sql |
| 1.4 | membership 対象 row は `source.rawDefinition` が dict でなければ catalog を emit しない(partial 拒否) | sql:catalog-required-fields-nonnull.sql(`membership-rawdefinition-not-object`) |
| 1.5 | JSONL parse 可能であること | cue vet(parse 不能なら vet 失敗)+ records-gate の JSONL reader |

## 2. ops-adr-specs-promotion core.py(diagnostics)

対象は「specs 昇格 kernel」の固定 fixture(特定 ADR/特定 package contract/特定 feat input)。
記録系規則のうち一般化可能なものを吸収、kernel 固有 binding 検査は out-of-scope(ops 側 check として存続)。

| # | 規則(diagnostic code) | Gate |
|---|------|------|
| 2.1 | missing-file / invalid-json / non-object-jsonl-row | cue vet + records-gate reader(required-record-file-missing) |
| 2.2 | invalid-adr-kind(raw ADR は adr.raw.v1) | cue:adr-ladder.cue#AdrRaw(legacy kind 2 種は append-only 保持のため許容に含む) |
| 2.3 | adr-contains-issue-lifecycle-field | 未吸収(kernel 固有; ops check 続投) |
| 2.4 | invalid-package-contract-kind(governance.packageContract.v1) | cue:package-contract.cue#PackageContract |
| 2.5 | package-contract-not-accepted(kernel 対象 contract は accepted) | sql:membership-packageid-in-contract.sql(admissible status)+ debt(membership-member-not-accepted) |
| 2.6 | missing-package-contract-definition(definition object 必須) | cue:package-contract.cue#PackageContract |
| 2.7 | wrong-contract-spec-id / repo-placement / implementation-package / output-binding / check-binding / accepted-authority / authority-collapse 群 / governance-records-binding / legacy-implements-reference | out-of-scope(kernel 固有 fixture 検査; ops checks.ops-adr-specs-promotion 続投) |
| 2.8 | feat input 検査群(check_feat_input) | out-of-scope(generated/ projection 出力検査; ops 側続投) |

## 3. tools/check-package-facet-proof.py

facet proof artifact(非権威 evidence)の整合検査。records 検査部のみ吸収対象。

| # | 規則 | Gate |
|---|------|------|
| 3.1 | JSONL: CRLF 禁止 / BOM 禁止 / parse 可能 / row は object | cue vet + records-gate reader(CRLF/BOM は未吸収 — 将来 sql/lint 追加候補) |
| 3.2 | facet proof record は 1 行のみ / status=poc-non-authority / duckdbRole=read model only | 未吸収(facet-proof 固有; validator 続投) |
| 3.3 | summary/manifest facet list・counts・proofResults・notRun 整合 | out-of-scope(artifact 検査) |
| 3.4 | manifest sha256 一致 / secrets facet に value 漏洩なし | out-of-scope(artifact 検査) |

## 4. specsless_readiness.py(record 検査部)

| # | 規則 | Gate |
|---|------|------|
| 4.1 | 全 .json/.jsonl parse 可能 | cue vet + reader(workspace 全域 rglob は out-of-scope) |
| 4.2 | provenance baseHash 固定値 / packageCount 整合 | 未吸収(workspace 配線前提; readiness 続投) |
| 4.3 | package status ∈ {accepted, planned}(top-level / definition) | cue:package-contract.cue#PackageContract(top-level)+ sql:membership-packageid-in-contract.sql |
| 4.4 | packageId / specId / officialOutput の重複なし | sql:package-contract-integrity.sql(packageId)。specId/officialOutput unique は未吸収(追加候補) |
| 4.5 | successorRepoId ∉ {specs, spec} | 未吸収(追加候補) |
| 4.6 | dependency-edge: external は toPackageIds=[] / それ以外は単一解決 | cue:dependency-edge.cue#DependencyEdge |
| 4.7 | dependency-edge endpoints の存在 | sql:dependency-edge-endpoints-in-contract.sql |
| 4.8 | feat input / projection digest の set・digest 整合 | out-of-scope(generated/ projection 検査; readiness 続投) |
| 4.9 | duplicate provide は factorization-allowance 必須 | 未吸収(追加候補) |
| 4.10 | destructive case / run / issue-ledger / purpose 整合 | out-of-scope(workspace 他 repo 参照) |

## 5. records-gate が新設する規則(bespoke validator に無かったもの)

| # | 規則 | Gate |
|---|------|------|
| 5.1 | recordDigest は sha256 hex(64) 非空(package-contract / projected repo-placement) | cue + sql:package-contract-integrity.sql |
| 5.2 | membership ledger に重複 packageId なし(126 集合は set) | sql:membership-no-duplicates.sql |
| 5.3 | repo-placement packageId ⊆ package-contract | sql:repo-placement-packageid-in-contract.sql |
| 5.4 | membership 対象 rawDefinition の catalog 必須 field non-null(機械強制 18/21) | sql:catalog-required-fields-nonnull.sql |
| 5.5 | breaking 契約変更は feat 検証 evidence record 必須(stub; policy/promotion-policy.md) | sql:breaking-change-evidence.sql + cue:feat-evidence.cue |
| 5.6 | decisions record の shape | cue:decisions.cue |

## 既知 data 逸脱(blocking にせず debt として追跡)

spec 上の理想形と現 data の差。assertion は現実に強制されている不変条件を
blocking とし、理想形との差は `records-gate --report` の obligation-debt JSON
で可視化する(非 blocking)。

1. **membership-member-not-accepted**: membership 126 のうち `claimd` は
   status=planned(accepted-only の理想形に対する逸脱 1 件)。
   make-spec-catalog は存在のみ要求し、readiness は {accepted, planned} を
   許容しており、期待 catalog sha256 も claimd 込みで確定済のため、blocking
   assertion は admissible status = {accepted, planned} とした。
2. **catalog-field-gap**: catalog 28 field のうち 1 は導出(package)、6 は
   default 宣言あり(implementationContract / migrationContract /
   acceptanceContract / namingContract / riskMitigationContract → null、
   usesExtensions → [])。名目必須 21 のうち 18 を non-null 機械強制。
   残 3(dependencyUse: 23 件 / publicInterface: 1 件 /
   checkPackageContract: 78 件 null)は移行 data に既知 gap があり debt 追跡。
3. **accepted-without-feat-evidence**: accepted 契約 189 件のうち promotable
   な feat build evidence(records/feat/build-evidence.v1.jsonl)を持つものは
   0 件。promotion-policy(net-new = gate のみ + 負債追跡)に基づき非 blocking。

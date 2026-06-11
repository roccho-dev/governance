# promotion-policy — records 受理規約

本 repo の records/ は権威台帳である。台帳への row 受理(promotion)は本規約に従う。
機械強制は records-gate(`tools/records-gate.py` — CUE schema vet + DuckDB
assertion、`flake.nix` checks.<system>.records-gate)が行う。

## 受理クラス

### 1. net-new(新規契約・新規 record)

- **要件: records-gate 緑のみ。**(schema 適合 + 関係不変条件 0 violation)
- feat 実証 evidence は受理の前提に**しない**。代わりに「accepted だが feat
  実証 evidence の無い義務」を **obligation debt** として追跡する:
  `tools/records-gate.py --report <path>` が
  `governance.obligationDebtReport.v1` JSON を出力する(非 blocking・可視化のみ)。
  - debtClass `accepted-without-feat-evidence`: status=accepted の
    package-contract のうち、records/feat/build-evidence.v1.jsonl に
    promotableBuildEvidence=true の row を持たないもの。
  - debtClass `membership-member-not-accepted` / `catalog-field-gap`:
    policy/RULES-INVENTORY.md「既知 data 逸脱」参照。

### 2. breaking(既実装契約の変更)

- 既に実装済(accepted かつ実装が存在する)契約の互換性を破る変更は、
  **feat 検証 evidence record 必須**。
- evidence record の kind: `governance.breakingChangeEvidence.v1`
  (CUE: `policy/cue/feat-evidence.cue` `#BreakingChangeEvidence`、
  台帳: `records/feat/breaking-change-evidence.v1.jsonl`)。
  - `packageId` — 対象 package
  - `changeClass: "breaking"`
  - `baselineRecordDigest` — 置換される既実装契約 row の recordDigest
  - `newRecordDigest` — 受理する新契約 row の recordDigest
  - `featGate: {command, status: "pass"}` — 新契約を実証した feat 検証 run
- 宣言方法: breaking な改訂 row は package-contract の
  `lifecycle.changeClass = "breaking"` を宣言する。
- 機械強制: `policy/sql/assertions/breaking-change-evidence.sql`。
  `lifecycle.changeClass = "breaking"` の contract row に対し、同 packageId
  かつ newRecordDigest = recordDigest の evidence row が無ければ violation
  (gate 赤 = 受理拒否)。現 data に breaking 宣言 row は 0 件のため stub と
  して pass する(初の breaking 改訂時に load-bearing になる)。

## 強制点

1. governance repo: `nix flake check`(checks.<system>.records-gate)。
2. ops(consumer)側: specCatalog derivation が catalog 生成**前**に
   records-gate を pin 済 governance に対して実行する(gate 赤 = build 失敗
   = catalog/placement が生成されない)。

## 非対象

- root file の互換 view、generated/ projection 出力、artifact 検査は本規約の
  受理対象外(各 validator / consumer gate が引き続き担当。
  policy/RULES-INVENTORY.md 参照)。

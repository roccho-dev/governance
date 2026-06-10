#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, hashlib
from typing import Any

EXPECTED_FACETS = [
    "contracts", "envs", "secrets", "runtimes", "disruptives", "dependencies",
    "capabilities", "storages", "migrations", "observability", "artifacts",
    "schedules", "configs", "entrypoints", "releases", "ownership",
]
PROOF_REL = pathlib.Path("artifacts/package-facet-promotion-compaction-proof-260606/package_facet_promotion_compaction_proof_260606")
RECORD_REL = pathlib.Path("governance-records-main/records/package-facets/package-facet-proof.v1.jsonl")

def fail(message: str) -> None:
    raise SystemExit("package-facet-proof:error:" + message)

def check(cond: bool, message: str) -> None:
    if not cond:
        fail(message)

def read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid-json:{path}:{exc}")

def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows=[]
    try:
        data=path.read_bytes()
    except FileNotFoundError:
        fail(f"missing-jsonl:{path}")
    check(b"\r" not in data, f"crlf-forbidden:{path}")
    check(not data.startswith(b"\xef\xbb\xbf"), f"bom-forbidden:{path}")
    for i,line in enumerate(data.decode("utf-8").split("\n"),1):
        if line == "":
            continue
        try:
            obj=json.loads(line)
        except Exception as exc:
            fail(f"invalid-jsonl:{path}:{i}:{exc}")
        check(isinstance(obj, dict), f"jsonl-row-not-object:{path}:{i}")
        rows.append(obj)
    return rows

def sha_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(root: pathlib.Path) -> dict[str, Any]:
    proof=root/PROOF_REL
    check(proof.is_dir(), "proof artifact directory missing")
    summary=read_json(proof/"dist/summary.json")
    manifest=read_json(proof/"dist/manifest.json")
    recs=read_jsonl(root/RECORD_REL)
    check(len(recs)==1, "expected one package facet proof record")
    rec=recs[0]
    check(rec.get("status")=="poc-non-authority", "facet proof must remain poc-non-authority")
    check(rec.get("authorityBoundary", {}).get("duckdbRole") == "read model / evaluator only", "DuckDB role must remain read-model/evaluator only")
    check(summary.get("facets") == EXPECTED_FACETS, "summary facet list mismatch")
    check(manifest.get("facets") == EXPECTED_FACETS, "manifest facet list mismatch")
    counts=summary.get("counts") or {}
    check(counts.get("facets_current") == len(EXPECTED_FACETS), "not every facet has current output")
    check(counts.get("blockers", 0) > 0, "blocker rows must be retained")
    check(counts.get("quarantine", 0) > 0, "quarantine rows must be retained")
    check(counts.get("tests_failed") == 0, "POC test rows failed")
    results=summary.get("proofResults") or {}
    for key in ["allCurrentFacetsPresent", "allJsonlParsed", "blockersExcludedFromCurrent", "deterministicRebuild", "incrementalEqualsFull", "destructiveFixturesGreen"]:
        check(results.get(key) is True, f"proof result not green: {key}")
    check("CUE input/output gate" in summary.get("notRun", []), "CUE gate limitation must be explicit")
    check("100k/1m/10m row perf" in summary.get("notRun", []), "scale limitation must be explicit")
    manifest_files={f["path"]: f for f in manifest.get("files", [])}
    check("engine/proof.duckdb" in manifest_files, "proof.duckdb must be tracked as non-authority evidence if present")
    for rel, meta in manifest_files.items():
        p=proof/rel
        check(p.exists(), f"manifest file missing:{rel}")
        check(sha_file(p)==meta.get("sha256"), f"manifest sha mismatch:{rel}")
    current_dir=proof/"dist/current"
    for facet in EXPECTED_FACETS:
        rows=read_jsonl(current_dir/f"{facet}.jsonl")
        check(rows, f"current facet output empty:{facet}")
    secret_rows=read_jsonl(current_dir/"secrets.jsonl")
    for row in secret_rows:
        text=json.dumps(row, ensure_ascii=False, sort_keys=True).lower()
        check('"value"' not in text and 'secretvalue' not in text, "secret value-like field leaked into current secrets facet")
    blockers=read_jsonl(proof/"dist/blockers.jsonl")
    quarantine=read_jsonl(proof/"dist/quarantine.jsonl")
    ledger=read_jsonl(proof/"dist/ledger/promotion_ledger.jsonl")
    check(len(blockers)==counts.get("blockers"), "blocker count mismatch")
    check(len(quarantine)==counts.get("quarantine"), "quarantine count mismatch")
    check(len(ledger)==counts.get("promotion_ledger"), "promotion ledger count mismatch")
    return {"status":"pass", "facets":len(EXPECTED_FACETS), "blockers":len(blockers), "quarantine":len(quarantine), "promotionLedgerRows":len(ledger), "deterministicRebuild":results.get("deterministicRebuild"), "incrementalEqualsFull":results.get("incrementalEqualsFull"), "authority":"poc-non-authority"}

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    args=ap.parse_args()
    result=run(pathlib.Path(args.root).resolve())
    text=json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.out).write_text(text+"\n", encoding="utf-8")
    print(text if args.json else "package-facet-proof:pass")

if __name__ == "__main__":
    main()

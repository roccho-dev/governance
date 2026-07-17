#!/usr/bin/env python3
from __future__ import annotations

import argparse, copy, importlib.util, json, re, sys
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "governance/ci-topology-150.jsonl"
PACKET = ROOT / "fixtures/final-ci-topology/governance-fixture.json"
CLAIM_COMPILER = ROOT / "tools/compile-claim-port-joins.py"
FINAL_CHECK = "gov-final-scope-purpose-join / gate"
CLASSES = {"accepted-meaning", "merge-admission", "effect", "evidence-only"}
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SECRET = re.compile(r"\$\{\{\s*secrets(?:\.([A-Za-z0-9_]+)|\[['\"]([^'\"]+)['\"]\])")
VARIABLE = re.compile(r"\$\{\{\s*vars(?:\.([A-Za-z0-9_]+)|\[['\"]([^'\"]+)['\"]\])")


class Error(RuntimeError):
    pass


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_of(value: Any) -> str:
    return "sha256:" + sha256(canon(value).encode()).hexdigest()


def json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise Error(f"invalid-input:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise Error(f"not-object:{path}")
    return value


def jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise Error(f"invalid-input:{path}:{exc}") from exc
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Error(f"invalid-jsonl:{path}:{number}") from exc
        if not isinstance(row, dict):
            raise Error(f"not-object:{path}:{number}")
        rows.append(row)
    return rows


def matches(text: str, pattern: re.Pattern[str]) -> list[str]:
    return sorted({m.group(1) or m.group(2) for m in pattern.finditer(text)})


def events(text: str) -> list[str]:
    found, active = [], False
    for line in text.splitlines():
        if line == "on:":
            active = True
            continue
        if active and line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z_]+):", line) if active else None
        if match:
            found.append(match.group(1))
    return sorted(set(found))


def inventory(path: Path = INVENTORY) -> dict[str, Any]:
    rows = jsonl(path)
    meta = [r for r in rows if r.get("kind") == "governance.ciTopologyInventory.meta.v1"]
    workflows = [r for r in rows if r.get("kind") == "governance.ciTopologyInventory.workflow.v1"]
    f: list[str] = []
    if len(meta) != 1: f.append("inventory-meta-count")
    if len(workflows) != 12: f.append("inventory-workflow-count")
    declared = [r.get("path") for r in workflows]
    actual = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / ".github/workflows").glob("*.yml"))
    if len(declared) != len(set(declared)): f.append("inventory-duplicate-path")
    if sorted(declared) != actual: f.append("inventory-workflow-set-drift")
    current, target, targets = 0, 0, set()
    for row in workflows:
        name = row.get("path")
        path_value = ROOT / name if isinstance(name, str) else None
        if path_value is None or not path_value.is_file():
            f.append(f"workflow-missing:{name}")
            continue
        text = path_value.read_text()
        checks = [
            (sorted(row.get("triggers", [])) == events(text), "trigger-drift"),
            (sorted(row.get("secrets", [])) == matches(text, SECRET), "secret-drift"),
            (sorted(row.get("variables", [])) == matches(text, VARIABLE), "variable-drift"),
            (bool(row.get("uploadsArtifact")) == ("actions/upload-artifact@" in text), "artifact-drift"),
            (bool(row.get("fallbackGreen")) == ("fallback" in text.lower()), "fallback-drift"),
        ]
        f.extend(f"{code}:{name}" for ok, code in checks if not ok)
        cur, tgt = row.get("currentAuthorityClass"), row.get("targetAuthorityClass")
        if cur not in CLASSES or tgt not in CLASSES: f.append(f"authority-class-unknown:{name}")
        if cur == "merge-admission": current += 1
        if tgt == "merge-admission": target += 1
        if cur != "evidence-only": f.append(f"pre-acceptance-authority:{name}")
        if row.get("preAcceptanceOperation") in {"delete", "cutover", "grant-authority"}:
            f.append(f"pre-acceptance-forbidden-operation:{name}")
        if row.get("postAcceptanceOperation") in {"merge", "delete"} and not (row.get("responsibilityDestination") and row.get("deletionProof")):
            f.append(f"incomplete-transfer-contract:{name}")
        if row.get("targetWorkflow"): targets.add(row["targetWorkflow"])
        for ref in row.get("rulesetReferences", []):
            if not (ROOT / ref).is_file(): f.append(f"ruleset-reference-missing:{name}:{ref}")
    m = meta[0] if len(meta) == 1 else {}
    if current != 0: f.append("current-merge-admission-count")
    if target != 1: f.append("target-merge-admission-count")
    if targets != {"gov-gate", "gov-canary"}: f.append("target-workflow-set")
    if m.get("defaultBranch") != "proposals": f.append("default-branch-drift")
    if m.get("finalCheckName") != FINAL_CHECK: f.append("final-check-name-drift")
    if m.get("acceptedDecisionState") != "proposed-not-authority": f.append("accepted-decision-boundary")
    if m.get("allRepositoriesEnforced") is not False: f.append("all-repositories-overclaim")
    return {"kind":"governance.ciTopologyInventory.report.v1","status":"fail" if f else "pass","workflowCount":len(workflows),"currentMergeAdmissionSurfaces":current,"targetMergeAdmissionSurfaces":target,"targetWorkflows":sorted(targets),"findings":sorted(f),"inventoryDigest":hash_of(rows),"authority":False,"allRepositoriesEnforced":False}


def candidate_tokens(value: Any, sha: str) -> Any:
    if isinstance(value, str): return sha if value == "@candidate" else value
    if isinstance(value, list): return [candidate_tokens(v, sha) for v in value]
    if isinstance(value, dict): return {k: candidate_tokens(v, sha) for k, v in value.items()}
    return value


def claim_result(packet: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    spec = importlib.util.spec_from_file_location("claim_join", CLAIM_COMPILER)
    if spec is None or spec.loader is None: raise Error("claim-compiler-load")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    admissions = module.compile_admissions([packet["grant"]], [packet["assertion"]], packet["receipts"])
    return (admissions[0].get("admissionResult", "missing") if len(admissions) == 1 else "cardinality", admissions)


def evaluate(raw: dict[str, Any], sha: str, inv: dict[str, Any]) -> dict[str, Any]:
    p, f = candidate_tokens(copy.deepcopy(raw), sha), []
    add = f.append
    if not SHA.fullmatch(sha): add("candidate-sha-invalid")
    if inv.get("status") != "pass": add("inventory-invalid")
    if p.get("kind") != "governance.finalCiGate.input.v1": add("packet-kind-invalid")
    if p.get("mode") != "fixture": add("fixture-as-production")
    decision = p.get("decision") if isinstance(p.get("decision"), dict) else {}
    if decision.get("status") != "proposed-fixture": add("missing-accepted-decision")
    if decision.get("acceptedReleaseDigest") is not None: add("fixture-claims-accepted-release")
    source, engine = p.get("source", {}), p.get("engine", {})
    for value, code in [(decision.get("sourceDigest"),"decision-source-digest-invalid"),(source.get("capturedDigest"),"source-captured-digest-invalid"),(source.get("currentDigest"),"source-current-digest-invalid"),(engine.get("contractDigest"),"engine-contract-digest-invalid"),(engine.get("capturedImplementationDigest"),"engine-captured-digest-invalid"),(engine.get("currentImplementationDigest"),"engine-current-digest-invalid")]:
        if not isinstance(value, str) or not DIGEST.fullmatch(value): add(code)
    if source.get("capturedDigest") != source.get("currentDigest"): add("source-mutated-during-evaluation")
    if engine.get("capturedImplementationDigest") != engine.get("currentImplementationDigest"): add("engine-mutated-during-evaluation")
    repo, candidate = p.get("repository"), p.get("candidate", {})
    for field in ("capturedSha", "observedSha", "evaluatedSha"):
        if candidate.get(field) != sha: add(f"candidate-{field}-mismatch")
    if candidate.get("writtenSha") is not None or candidate.get("readbackSha") is not None: add("fixture-effect-present")
    grant, assertion, receipts = p.get("grant"), p.get("assertion"), p.get("receipts")
    if not isinstance(grant, dict): add("missing-accepted-decision")
    if not isinstance(assertion, dict): add("missing-feature-assertion")
    else:
        if assertion.get("repository") != repo: add("assertion-repository-mismatch")
        if assertion.get("candidateSha") != sha: add("assertion-candidate-sha-mismatch")
    contract = p.get("receiptContract", {}).get("digest")
    if not isinstance(contract, str) or not DIGEST.fullmatch(contract): add("receipt-contract-digest-invalid")
    if not isinstance(receipts, list) or not receipts:
        add("missing-exact-sha-receipt"); receipts = []
    today = date.fromisoformat(p.get("evaluationDate", "1970-01-01"))
    for i, receipt in enumerate(receipts):
        if not isinstance(receipt, dict): add(f"receipt-malformed:{i}"); continue
        if receipt.get("repository") != repo: add(f"receipt-repository-mismatch:{i}")
        if receipt.get("candidateSha") != sha: add(f"receipt-candidate-sha-mismatch:{i}")
        if receipt.get("status") != "pass": add(f"receipt-not-pass:{i}")
        if receipt.get("contractDigest") != contract: add(f"receipt-contract-mismatch:{i}")
        try: expiry = date.fromisoformat(receipt["expiresOn"])
        except (KeyError, TypeError, ValueError): add(f"receipt-expiry-invalid:{i}")
        else:
            if expiry < today: add(f"receipt-expired:{i}")
    for field in ("scope", "package", "purpose"):
        if p.get("closure", {}).get(field) != "pass": add(f"closure-{field}-not-pass")
    authority = p.get("authorityModel", {})
    classes = authority.get("classes", [])
    if not isinstance(classes, list) or any(c not in CLASSES for c in classes): add("authority-class-unknown")
    elif len(classes) != len(set(classes)): add("authority-class-duplicate")
    if authority.get("governanceMeaningAuthority") is not False: add("governance-meaning-authority-collision")
    surfaces = authority.get("activeMergeAdmissionSurfaces", [])
    if not isinstance(surfaces, list): add("merge-admission-surface-invalid")
    elif len(surfaces) > 1: add("multiple-active-merge-admission-surfaces")
    elif surfaces: add("pre-acceptance-merge-admission-authority")
    if authority.get("effectAuthoritySurface") is not None: add("pre-acceptance-effect-authority")
    if p.get("stageSecurity", {}).get("candidateCodeWithWriteSecrets") is not False: add("candidate-code-write-secret-access")
    artifacts = p.get("artifacts", [])
    if not isinstance(artifacts, list) or any(isinstance(a, dict) and a.get("admissionEligible") is True for a in artifacts): add("artifact-offered-as-admission")
    if any(isinstance(a, dict) and a.get("mode") == "fallback" for a in artifacts if isinstance(artifacts, list)): add("fallback-artifact-present")
    lifecycle = p.get("lifecycle", {})
    for i, ex in enumerate(lifecycle.get("exceptions", [])):
        try: expired = date.fromisoformat(ex["expiresOn"]) < today
        except (KeyError, TypeError, ValueError): add(f"exception-invalid:{i}"); continue
        if expired: add(f"exception-expired:{i}")
        for field in ("owner","reason","returnCondition","blockingResidual"):
            if not ex.get(field): add(f"exception-contract-missing:{i}:{field}")
    for i, deletion in enumerate(lifecycle.get("deletions", [])):
        if deletion.get("rulesetReferences") or deletion.get("consumerReferences") or not deletion.get("responsibilityReadback"): add(f"deletion-residual:{i}")
    effect = p.get("effect", {})
    if effect.get("attempted"):
        if effect.get("admittedSha") != sha or effect.get("readbackSha") != sha: add("effect-readback-mismatch")
        add("fixture-effect-attempted")
    claims = p.get("claims", {})
    if claims.get("allRepositoriesEnforced") is not False: add("all-repositories-overclaim")
    if claims.get("businessOutcomeClosed") is not False: add("business-outcome-overclaim")
    admission, admissions = "not-run", []
    if isinstance(grant, dict) and isinstance(assertion, dict) and receipts and all(isinstance(r, dict) for r in receipts):
        admission, admissions = claim_result(p)
        if admission != "organization-active": add(f"claim-not-active:{admission}")
    f = sorted(set(f))
    return {"kind":"governance.finalCiGate.fixtureDecision.v1","status":"block" if f else "pass","decision":"block" if f else "fixture-pass","candidateSha":sha,"claimAdmission":admission,"admissions":admissions,"findings":f,"productionAdmission":False,"meaningAuthority":False,"mergeAdmissionAuthority":False,"effectAuthority":False,"evidenceOnly":True,"allRepositoriesEnforced":False,"inventoryDigest":inv.get("inventoryDigest"),"packetDigest":hash_of(p),"boundary":"ADRS #233 is proposed. This exact-SHA result is a non-authority migration fixture and cannot satisfy production admission or effect cutover."}


def cases() -> list[tuple[str, str, Callable[[dict[str, Any]], None]]]:
    return [
        ("missing-decision","missing-accepted-decision",lambda p:p["decision"].update(status="missing")),
        ("missing-assertion","missing-feature-assertion",lambda p:p.pop("assertion")),
        ("old-bundle","claim-not-active:stale-assertion",lambda p:p["assertion"].update(acceptedBundleDigest="sha256:"+"1"*64)),
        ("old-closure","claim-not-active:stale-assertion",lambda p:p["assertion"].update(sourceClosureDigest="sha256:"+"2"*64)),
        ("missing-receipt","missing-exact-sha-receipt",lambda p:p.update(receipts=[])),
        ("other-repo","receipt-repository-mismatch:0",lambda p:p["receipts"][0].update(repository="other/repo")),
        ("other-sha","receipt-candidate-sha-mismatch:0",lambda p:p["receipts"][0].update(candidateSha="0"*40)),
        ("failed-receipt","receipt-not-pass:0",lambda p:p["receipts"][0].update(status="fail")),
        ("malformed-receipt","receipt-malformed:0",lambda p:p.update(receipts=["bad"])),
        ("expired-receipt","receipt-expired:0",lambda p:p["receipts"][0].update(expiresOn="2026-07-17")),
        ("source-race","source-mutated-during-evaluation",lambda p:p["source"].update(currentDigest="sha256:"+"3"*64)),
        ("candidate-race","candidate-observedSha-mismatch",lambda p:p["candidate"].update(observedSha="0"*40)),
        ("unknown-authority","authority-class-unknown",lambda p:p["authorityModel"].update(classes=["unknown"])),
        ("duplicate-class","authority-class-duplicate",lambda p:p["authorityModel"].update(classes=["evidence-only","evidence-only"])),
        ("duplicate-surface","multiple-active-merge-admission-surfaces",lambda p:p["authorityModel"].update(activeMergeAdmissionSurfaces=["a","b"])),
        ("fallback","fallback-artifact-present",lambda p:p["artifacts"].append({"mode":"fallback","admissionEligible":False})),
        ("artifact-pass","artifact-offered-as-admission",lambda p:p["artifacts"][0].update(admissionEligible=True)),
        ("expired-exception","exception-expired:0",lambda p:p["lifecycle"].update(exceptions=[{"owner":"x","reason":"x","expiresOn":"2026-07-17","returnCondition":"x","blockingResidual":"x"}])),
        ("deletion-residual","deletion-residual:0",lambda p:p["lifecycle"].update(deletions=[{"rulesetReferences":["old"],"consumerReferences":[],"responsibilityReadback":False}])),
        ("effect-mismatch","effect-readback-mismatch",lambda p:p.update(effect={"attempted":True,"admittedSha":"@candidate","readbackSha":"0"*40})),
        ("write-secret","candidate-code-write-secret-access",lambda p:p["stageSecurity"].update(candidateCodeWithWriteSecrets=True)),
        ("meaning-collision","governance-meaning-authority-collision",lambda p:p["authorityModel"].update(governanceMeaningAuthority=True)),
        ("all-repos","all-repositories-overclaim",lambda p:p["claims"].update(allRepositoriesEnforced=True)),
        ("business","business-outcome-overclaim",lambda p:p["claims"].update(businessOutcomeClosed=True)),
        ("fixture-production","fixture-as-production",lambda p:p.update(mode="production")),
    ]


def selftest(inv_path: Path, packet_path: Path) -> dict[str, Any]:
    inv, base, sha = inventory(inv_path), json_file(packet_path), "a"*40
    if inv["status"] != "pass": raise Error(canon(inv))
    passed = evaluate(base, sha, inv)
    if passed["status"] != "pass": raise Error(canon(passed))
    results = []
    for name, expected, mutate in cases():
        packet = copy.deepcopy(base); mutate(packet); report = evaluate(packet, sha, inv)
        if report["status"] != "block" or expected not in report["findings"]: raise Error(canon({"case":name,"expected":expected,"report":report}))
        results.append({"case":name,"expectedFinding":expected,"status":"pass"})
    return {"kind":"governance.finalCiTopology.selftest.v1","status":"pass","authority":False,"positiveCases":1,"destructiveCases":len(results),"cases":results,"inventory":inv,"allRepositoriesEnforced":False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["selftest","inventory","gate"])
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--candidate-sha")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inventory": report = inventory(args.inventory)
        elif args.command == "selftest": report = selftest(args.inventory, args.packet)
        else:
            if not args.candidate_sha: parser.error("gate requires --candidate-sha")
            report = evaluate(json_file(args.packet), args.candidate_sha, inventory(args.inventory))
    except Error as exc: report = {"kind":"governance.finalCiTopology.error.v1","status":"fail","error":str(exc),"authority":False}
    print(canon(report) if args.json else f"final-ci-topology:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())

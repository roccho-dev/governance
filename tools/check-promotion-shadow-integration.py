#!/usr/bin/env python3
from __future__ import annotations

import argparse,copy,hashlib,json
from pathlib import Path
from typing import Any,Callable
from tools.promotion.core import Policy,PromotionError,digest,make_promotion_candidate
ROOT=Path(__file__).resolve().parents[1]; POLICY=ROOT/"tools/promotion/policy-shadow.v1.json"; BASELINE=ROOT/"governance/signed-promotion-baseline.v1.json"
ENGINE_FILES=["tools/promotion/core.py","tools/promotion/ed25519.py","tools/promotion/ports.py","tools/promotion/adapters.py","tools/promotion/cli.py"]
def need(ok:bool,code:str)->None:
 if not ok: raise PromotionError(code)
def read(path:Path)->dict[str,Any]:
 value=json.loads(path.read_text(encoding="utf-8")); need(isinstance(value,dict),f"not-object:{path}"); return value
def engine_digest()->str:
 return digest([{"path":relative,"sha256":hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()} for relative in ENGINE_FILES])
def validate_baseline(value:dict[str,Any])->None:
 need(value.get("kind")=="governance.signedPromotionBaseline.v1","baseline-kind"); need(value.get("status")=="current","baseline-status"); need(value.get("closureModel")=="signed-promotion","baseline-closure-model"); need(value.get("supersedesClosureModel")=="github-merge-protection","baseline-supersedes"); need(value.get("historicalClosureReceipts")=={"adrs223":"superseded","adrs233":"superseded","governance150":"superseded"},"baseline-old-closure"); need(value["governance"]["workflowCount"]==2,"baseline-workflow-count"); need(value["invariants"]["githubMergeHasAuthority"] is False,"baseline-github-merge"); need(value["invariants"]["githubRulesetRequired"] is False,"baseline-ruleset"); need(value["invariants"]["allRepositoriesEnforced"] is False,"baseline-all-repositories"); need(value["invariants"]["businessOutcomeAchieved"] is False,"baseline-business-outcome")
def validate_live(value:dict[str,Any])->tuple[str,str]:
 need(value.get("kind")=="governance.liveSelectedConsumerPacket.v1","live-kind"); need(value.get("status")=="pass","live-status"); need(value.get("artifactBodiesVerified") is True,"live-artifact-bodies"); need(value.get("receiptCandidateShaBound") is True,"live-receipt-sha"); rows=value.get("repositories"); need(isinstance(rows,list) and len(rows)==2,"live-repository-count"); need(len({row.get("repository") for row in rows if isinstance(row,dict)})==2,"live-duplicate-repository"); claims=[]; receipts=[]
 for row in sorted(rows,key=lambda item:item["repository"]):
  receipt=row.get("receipt",{}); need(row.get("runConclusion")=="success" and row.get("runEvent")=="push","live-run"); need(row.get("currentHead")==row.get("runHeadSha")==receipt.get("candidateSha"),"live-candidate-binding"); need(receipt.get("status")=="pass" and receipt.get("authority") is False,"live-receipt")
  for field in ["claimDigest","receiptDigest","artifactDigest"]: need(isinstance(row.get(field),str) and row[field].startswith("sha256:"),f"live-{field}")
  claims.append({"repository":row["repository"],"currentHead":row["currentHead"],"claimDigest":row["claimDigest"]}); receipts.append({"repository":row["repository"],"candidateSha":receipt["candidateSha"],"receiptDigest":row["receiptDigest"],"artifactDigest":row["artifactDigest"],"runId":row["runId"]})
 return digest(claims),digest(receipts)
def candidate(gate:dict[str,Any],live:dict[str,Any],candidate_sha:str)->dict[str,Any]:
 baseline=read(BASELINE); policy_value=read(POLICY); validate_baseline(baseline); policy=Policy.from_dict(policy_value); need(policy.production_key_provisioned is False,"shadow-production-key"); need(policy.accepted_decision_status=="proposed","shadow-decision-status"); claim_set,receipt_set=validate_live(live); packet=make_promotion_candidate(candidate_digest=candidate_sha,accepted_decision_digest=policy.contract_digest,gate_report=gate,claim_set_digest=claim_set,receipt_set_digest=receipt_set,engine_digest=engine_digest(),accepted_decision_status=policy.accepted_decision_status); need(packet["promotionAdmission"] is False and packet["decision"]=="shadow-allow","shadow-admission"); packet.update({"implementationMode":"shadow","adrsPullRequest":policy_value["adrsCandidate"]["pullRequest"],"adrsHead":policy_value["adrsCandidate"]["head"],"productionKeyProvisioned":False,"productionPromotionEffect":False,"unpromotedCommitHasEffect":False,"selectedStateChanged":False,"rulesetObservationSeverity":"information","blockingResidual":"owner-controlled Ed25519 public key digest is not provisioned"}); packet["packetDigest"]=digest({k:v for k,v in packet.items() if k!="packetDigest"}); return packet
def reject(name:str,fn:Callable[[],None])->dict[str,str]:
 try: fn()
 except (PromotionError,KeyError,TypeError,ValueError): return {"case":name,"status":"rejected"}
 raise PromotionError("destructive-case-passed:"+name)
def fixture()->tuple[dict[str,Any],dict[str,Any]]:
 sha="a"*40; gate={"kind":"governance.finalScopePurposeJoin.gate.v4","status":"pass","decision":"allow","candidateSha":sha}; rows=[]
 for repo,digit in [("roccho-dev/ops","1"),("roccho-dev/ui","2")]: rows.append({"repository":repo,"currentHead":digit*40,"runHeadSha":digit*40,"runConclusion":"success","runEvent":"push","runId":1,"claimDigest":"sha256:"+digit*64,"receiptDigest":"sha256:"+("3" if digit=="1" else "4")*64,"artifactDigest":"sha256:"+("5" if digit=="1" else "6")*64,"receipt":{"candidateSha":digit*40,"status":"pass","authority":False}})
 return gate,{"kind":"governance.liveSelectedConsumerPacket.v1","status":"pass","artifactBodiesVerified":True,"receiptCandidateShaBound":True,"repositories":rows}
def selftest()->dict[str,Any]:
 gate,live=fixture(); packet=candidate(gate,live,"a"*40); cases=[]; bad=copy.deepcopy(gate); bad["candidateSha"]="b"*40; cases.append(reject("gate-other-candidate",lambda:candidate(bad,live,"a"*40))); bad=copy.deepcopy(live); bad["artifactBodiesVerified"]=False; cases.append(reject("artifact-body-unverified",lambda:candidate(gate,bad,"a"*40))); bad=copy.deepcopy(live); bad["repositories"][0]["receipt"]["candidateSha"]="9"*40; cases.append(reject("receipt-other-candidate",lambda:candidate(gate,bad,"a"*40))); bad=copy.deepcopy(live); bad["repositories"].append(copy.deepcopy(bad["repositories"][0])); cases.append(reject("duplicate-consumer",lambda:candidate(gate,bad,"a"*40))); bad=read(BASELINE); bad["historicalClosureReceipts"]["governance150"]="completed"; cases.append(reject("old-closure-active",lambda:validate_baseline(bad))); workflows="\n".join(path.read_text(encoding="utf-8") for path in (ROOT/".github/workflows").glob("*.yml")); need("tools.promotion.cli publish" not in workflows and "--private-key-file" not in workflows,"candidate-workflow-publisher"); need(not list(ROOT.glob("**/*.key")),"private-key-in-repository"); return {"kind":"governance.promotionShadowIntegration.selftest.v1","status":"pass","positiveCases":1,"destructiveCases":len(cases),"cases":cases,"promotionAdmission":False,"productionPromotionEffect":False,"providerAuthority":False,"githubMergeHasAuthority":False,"githubRulesetRequired":False,"allRepositoriesEnforced":False,"businessOutcomeAchieved":False,"packet":packet}
def canary()->dict[str,Any]:
 policy=Policy.from_dict(read(POLICY)); validate_baseline(read(BASELINE)); return {"kind":"governance.promotionCanaryShadow.v1","status":"shadow-pass","promotionContractDigest":policy.contract_digest,"productionKeyProvisioned":policy.production_key_provisioned,"acceptedDecisionStatus":policy.accepted_decision_status,"promotionChainExists":False,"selectedStateChanged":False,"rulesetSeverity":"information","rulesetAffectsPromotionClosure":False,"blockingResidual":"owner-controlled Ed25519 public key digest is not provisioned","providerAuthority":False,"githubMergeHasAuthority":False,"allRepositoriesEnforced":False,"businessOutcomeAchieved":False}
def main()->int:
 parser=argparse.ArgumentParser(); parser.add_argument("command",choices=["candidate","selftest","canary"]); parser.add_argument("--gate",type=Path); parser.add_argument("--live-consumers",type=Path); parser.add_argument("--candidate-sha"); parser.add_argument("--out",type=Path); parser.add_argument("--json",action="store_true"); args=parser.parse_args()
 if args.command=="candidate":
  if not args.gate or not args.live_consumers or not args.candidate_sha: parser.error("candidate requires --gate --live-consumers --candidate-sha")
  report=candidate(read(args.gate),read(args.live_consumers),args.candidate_sha)
 elif args.command=="canary": report=canary()
 else: report=selftest()
 text=json.dumps(report,sort_keys=True,separators=(",", ":"))+"\n"
 if args.out: args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(text,encoding="utf-8")
 print(text,end=""); return 0
if __name__=="__main__": raise SystemExit(main())

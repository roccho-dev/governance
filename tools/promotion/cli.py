from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters import FileSource, FileWriter, GenericGitRemote
from .core import Policy, canonical, digest, key_id, make_promotion_candidate, reduce_selected


def read(path: Path) -> dict[str, Any]: return json.loads(path.read_text(encoding="utf-8"))
def write(path: Path|None,value:dict[str,Any])->None:
    text=json.dumps(value,sort_keys=True,separators=(",", ":"))+"\n"
    if path: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text,encoding="utf-8")
    print(text,end="")
def require_outside_repository(path:Path,root:Path)->None:
    try: path.resolve().relative_to(root.resolve())
    except ValueError: return
    raise SystemExit("private-key-path-inside-repository")

def main()->int:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="cmd",required=True)
    candidate=sub.add_parser("candidate"); candidate.add_argument("--gate",type=Path,required=True); candidate.add_argument("--candidate",required=True); candidate.add_argument("--accepted-decision-digest",required=True); candidate.add_argument("--accepted-decision-status",choices=["proposed","accepted"],required=True); candidate.add_argument("--claim-set-digest",required=True); candidate.add_argument("--receipt-set-digest",required=True); candidate.add_argument("--engine-digest",required=True); candidate.add_argument("--out",type=Path)
    verify=sub.add_parser("verify"); verify.add_argument("--policy",type=Path,required=True); verify.add_argument("--tree",type=Path,required=True); verify.add_argument("--out",type=Path)
    publish=sub.add_parser("publish"); publish.add_argument("--policy",type=Path,required=True); publish.add_argument("--candidate-packet",type=Path,required=True); publish.add_argument("--private-key-file",type=Path,required=True); publish.add_argument("--repo-root",type=Path,required=True); publish.add_argument("--tree",type=Path,required=True); publish.add_argument("--remote",required=True); publish.add_argument("--worktree",type=Path,required=True); publish.add_argument("--promotion-id",required=True); publish.add_argument("--subject",required=True); publish.add_argument("--sequence",type=int,required=True); publish.add_argument("--previous-digest",required=True); publish.add_argument("--operation",choices=["promote","rollback","revoke"],required=True); publish.add_argument("--bootstrap",action="store_true"); publish.add_argument("--out",type=Path)
    args=parser.parse_args()
    if args.cmd=="candidate":
        write(args.out,make_promotion_candidate(candidate_digest=args.candidate,accepted_decision_digest=args.accepted_decision_digest,gate_report=read(args.gate),claim_set_digest=args.claim_set_digest,receipt_set_digest=args.receipt_set_digest,engine_digest=args.engine_digest,accepted_decision_status=args.accepted_decision_status)); return 0
    policy=Policy.from_dict(read(args.policy))
    if args.cmd=="verify": write(args.out,reduce_selected(FileSource(args.tree).read_events(),policy)); return 0
    if not policy.production_key_provisioned or policy.accepted_decision_status!="accepted": raise SystemExit("production-policy-not-accepted")
    require_outside_repository(args.private_key_file,args.repo_root); key_bytes=args.private_key_file.read_bytes()
    if len(key_bytes)!=32: raise SystemExit("private-key-not-raw-ed25519-seed")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    except ImportError as exc: raise SystemExit("production-ed25519-implementation-missing") from exc
    private=Ed25519PrivateKey.from_private_bytes(key_bytes); public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    if public!=policy.public_key: raise SystemExit("private-key-does-not-match-policy")
    packet=read(args.candidate_packet)
    if packet.get("promotionAdmission") is not True: raise SystemExit("candidate-not-admitted")
    event={"kind":"promotion.v1","promotionId":args.promotion_id,"subject":args.subject,"sequence":args.sequence,"candidateDigest":packet["candidateDigest"],"acceptedDecisionDigest":packet["acceptedDecisionDigest"],"gateDecisionDigest":packet["gateDecisionDigest"],"claimSetDigest":packet["claimSetDigest"],"receiptSetDigest":packet["receiptSetDigest"],"previousPromotionDigest":args.previous_digest,"operation":args.operation,"bootstrap":args.bootstrap}
    event["publisherKeyId"]=key_id(public); event["signature"]=private.sign(canonical(event)).hex(); signature=bytes.fromhex(event["signature"])
    event_receipt={"kind":"promotionEventReceipt.v1","status":"pass","eventDigest":digest(event),"candidatePacketDigest":packet["packetDigest"],"authority":False}
    FileWriter(args.tree).append(event,signature,event_receipt); adapter=GenericGitRemote(args.remote); transport_commit=adapter.publish(args.tree,args.worktree); readback_root=args.worktree.parent/(args.worktree.name+".readback"); readback_commit=adapter.clone_readback(readback_root); projection=reduce_selected(FileSource(readback_root).read_events(),policy); selected=projection["selected"].get(args.subject)
    if args.operation in {"promote","rollback"}:
        if not selected or selected["candidateDigest"]!=packet["candidateDigest"]: raise SystemExit("selected-readback-mismatch")
    elif selected is not None: raise SystemExit("revoke-readback-mismatch")
    effect_receipt={"kind":"promotionEffectReadback.v1","status":"pass","eventDigest":digest(event),"candidatePacketDigest":packet["packetDigest"],"transportCommit":transport_commit,"readbackCommit":readback_commit,"transportReadbackMatches":transport_commit==readback_commit,"chainHeadDigest":projection["chainHeadDigest"],"selectedProjectionDigest":projection["projectionDigest"],"selectedStateReadback":True,"providerAuthority":False,"authority":False,"allRepositoriesEnforced":False,"businessOutcomeAchieved":False}
    if effect_receipt["transportReadbackMatches"] is not True: raise SystemExit("transport-readback-mismatch")
    write(args.out,effect_receipt); return 0
if __name__=="__main__": raise SystemExit(main())

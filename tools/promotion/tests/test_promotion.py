from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.promotion.adapters import FileSource, FileWriter, GenericGitRemote
from tools.promotion.core import Policy, PromotionError, ZERO_DIGEST, digest, key_id, make_promotion_candidate, raw_public, reduce_selected, sign_event

SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def policy(private: Ed25519PrivateKey) -> Policy:
    public = raw_public(private)
    return Policy("sha256:" + "1" * 64, public, key_id(public), True, "accepted", 1)


def event(private, *, pid, subject, sequence, candidate, previous, operation="promote", bootstrap=False):
    return sign_event({"kind":"promotion.v1","promotionId":pid,"subject":subject,"sequence":sequence,"candidateDigest":candidate,"acceptedDecisionDigest":"sha256:"+"1"*64,"gateDecisionDigest":"sha256:"+"2"*64,"claimSetDigest":"sha256:"+"3"*64,"receiptSetDigest":"sha256:"+"4"*64,"previousPromotionDigest":previous,"operation":operation,"bootstrap":bootstrap}, private)


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.from_private_bytes(SEED)
        self.policy = policy(self.private)

    def chain(self):
        genesis = event(self.private,pid="genesis",subject="system:promotion-policy",sequence=0,candidate="sha256:"+"1"*64,previous=ZERO_DIGEST)
        first = event(self.private,pid="gov-1",subject="repo:roccho-dev/governance",sequence=0,candidate="a"*40,previous=digest(genesis),bootstrap=True)
        second = event(self.private,pid="gov-2",subject="repo:roccho-dev/governance",sequence=1,candidate="b"*40,previous=digest(first))
        rollback = event(self.private,pid="gov-rb",subject="repo:roccho-dev/governance",sequence=2,candidate="a"*40,previous=digest(second),operation="rollback")
        return [genesis, first, second, rollback]

    def test_candidate_shadow_does_not_admit(self):
        gate={"status":"pass","decision":"allow","candidateSha":"a"*40}
        packet=make_promotion_candidate(candidate_digest="a"*40,accepted_decision_digest="sha256:"+"1"*64,gate_report=gate,claim_set_digest="sha256:"+"2"*64,receipt_set_digest="sha256:"+"3"*64,engine_digest="sha256:"+"4"*64,accepted_decision_status="proposed")
        self.assertFalse(packet["promotionAdmission"]); self.assertEqual(packet["decision"],"shadow-allow")

    def test_chain_and_rollback(self):
        projection=reduce_selected(reversed(self.chain()),self.policy)
        self.assertEqual(projection["selected"]["repo:roccho-dev/governance"]["candidateDigest"],"a"*40); self.assertTrue(projection["bootstrapConsumed"])

    def test_direct_branch_change_has_no_effect(self):
        before=reduce_selected(self.chain()[:2],self.policy); branch_tip="c"*40; after=reduce_selected(self.chain()[:2],self.policy)
        self.assertEqual(before["projectionDigest"],after["projectionDigest"]); self.assertNotEqual(branch_tip,after["selected"]["repo:roccho-dev/governance"]["candidateDigest"])

    def test_destructive_mutations(self):
        base=self.chain(); mutations=[]
        x=copy.deepcopy(base); x[1]["signature"]="00"+x[1]["signature"][2:]; mutations.append(x)
        x=copy.deepcopy(base); x[2]["candidateDigest"]="c"*40; mutations.append(x)
        x=copy.deepcopy(base); x[2]["previousPromotionDigest"]=ZERO_DIGEST; mutations.append(x)
        x=copy.deepcopy(base); x.append(copy.deepcopy(x[-1])); mutations.append(x)
        x=copy.deepcopy(base); x[2]["sequence"]=7; mutations.append(x)
        x=copy.deepcopy(base); x[2]["publisherKeyId"]="0"*64; mutations.append(x)
        x=copy.deepcopy(base); x[2]["acceptedDecisionDigest"]="sha256:"+"9"*64; mutations.append(x)
        x=copy.deepcopy(base); x[2]["gateDecisionDigest"]="sha256:"+"9"*64; mutations.append(x)
        x=copy.deepcopy(base); x[2]["claimSetDigest"]="sha256:"+"9"*64; mutations.append(x)
        x=copy.deepcopy(base); x[2]["receiptSetDigest"]="sha256:"+"9"*64; mutations.append(x)
        x=copy.deepcopy(base); x[2]["bootstrap"]=True; mutations.append(x)
        x=copy.deepcopy(base); x[-1]["candidateDigest"]="d"*40; mutations.append(x)
        x=copy.deepcopy(base); x.pop(1); mutations.append(x)
        for rows in mutations:
            with self.assertRaises(PromotionError): reduce_selected(rows,self.policy)

    def test_file_writer_is_append_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); row=self.chain()[0]; writer=FileWriter(root)
            writer.append(row,bytes.fromhex(row["signature"]),{"status":"pass"}); writer.append(row,bytes.fromhex(row["signature"]),{"status":"pass"})
            changed=copy.deepcopy(row); changed["candidateDigest"]="sha256:"+"9"*64
            with self.assertRaises(PromotionError): writer.append(changed,bytes.fromhex(changed["signature"]),{"status":"pass"})

    def test_local_bare_git_provider_invariant_and_fast_forward_append(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); projections=[]
            for remote_name in ["a.git","b.git"]:
                tree=root/(remote_name+".tree"); writer=FileWriter(tree); remote=root/remote_name
                subprocess.run(["git","init","--bare",remote],check=True,stdout=subprocess.PIPE); adapter=GenericGitRemote(str(remote)); chain=self.chain()
                for row in chain[:2]: writer.append(row,bytes.fromhex(row["signature"]),{"status":"pass"})
                first=adapter.publish(tree,root/(remote_name+".work1")); writer.append(chain[2],bytes.fromhex(chain[2]["signature"]),{"status":"pass"}); second=adapter.publish(tree,root/(remote_name+".work2"))
                self.assertNotEqual(first,second); clone=root/(remote_name+".clone"); adapter.clone_readback(clone)
                count=int(subprocess.check_output(["git","rev-list","--count","HEAD"],cwd=clone,text=True)); self.assertEqual(count,2)
                projections.append(reduce_selected(FileSource(clone).read_events(),self.policy))
            self.assertEqual(projections[0]["projectionDigest"],projections[1]["projectionDigest"])

    def test_remote_history_deletion_and_rewrite_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); tree=root/"tree"; writer=FileWriter(tree); rows=self.chain()[:2]
            for row in rows: writer.append(row,bytes.fromhex(row["signature"]),{"status":"pass"})
            remote=root/"remote.git"; subprocess.run(["git","init","--bare",remote],check=True,stdout=subprocess.PIPE); adapter=GenericGitRemote(str(remote)); adapter.publish(tree,root/"work1")
            event_path=tree/"events"/"genesis.json"; original=event_path.read_bytes(); event_path.unlink()
            with self.assertRaisesRegex(PromotionError,"history-deletion"): adapter.publish(tree,root/"work2")
            event_path.write_bytes(original+b" ")
            with self.assertRaisesRegex(PromotionError,"history-rewrite"): adapter.publish(tree,root/"work3")


if __name__ == "__main__": unittest.main()

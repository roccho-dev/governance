from __future__ import annotations
import importlib.util, json, pathlib, sys, tempfile, unittest

HERE=pathlib.Path(__file__).resolve()
spec=importlib.util.spec_from_file_location("decisionctl", HERE.parents[1]/"decisionctl.py")
d=importlib.util.module_from_spec(spec)
assert spec.loader
sys.modules[spec.name]=d
spec.loader.exec_module(d)

def e(event_id, decision_id="ADR-1", kind="propose", seq=1, actor="author", dtype="architecture", **kw):
    v={"schema":d.EVENT_SCHEMA,"event_id":event_id,"decision_id":decision_id,
       "decision_type":dtype,"kind":kind,"actor":actor,"seq":seq,
       "title":decision_id,"summary":kind}
    v.update(kw); return v

def grant(actor="owner", actions=None, types=None):
    return {"schema":d.GRANT_SCHEMA,"actor":actor,
            "actions":actions or sorted(d.PROTECTED),"decision_types":types or ["*"]}

class DecisionCtlTest(unittest.TestCase):
    def test_accept(self):
        rows, auth=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner")],[grant()])
        self.assertEqual(rows[0]["status"],"accepted"); self.assertTrue(auth[1]["authorized"])
    def test_unauthorized_accept_is_ignored(self):
        rows, auth=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="intruder")],[grant()])
        self.assertEqual(rows[0]["status"],"proposed"); self.assertFalse(auth[1]["authorized"])
    def test_pending_amendment(self):
        rows,_=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner"),e("m",kind="amend",seq=3,actor="owner")],[grant()])
        self.assertEqual(rows[0]["status"],"accepted-with-pending-amendment")
    def test_reject(self):
        rows,_=d.reduce([e("p"),e("r",kind="reject",seq=2,actor="owner")],[grant()])
        self.assertEqual(rows[0]["status"],"rejected")
    def test_revoke(self):
        rows,_=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner"),e("r",kind="revoke",seq=3,actor="owner")],[grant()])
        self.assertEqual(rows[0]["status"],"revoked")
    def test_conflict_same_seq(self):
        rows,_=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner"),e("r",kind="reject",seq=2,actor="owner")],[grant()])
        self.assertEqual(rows[0]["status"],"conflict")
    def test_duplicate_event_rejected(self):
        with self.assertRaises(d.ContractError): d.reduce([e("x"),e("x")],[])
    def test_unknown_schema_rejected(self):
        bad=e("x"); bad["schema"]="decisionEvent.v1"
        with self.assertRaises(d.ContractError): d.reduce([bad],[])
    def test_type_change_rejected(self):
        with self.assertRaises(d.ContractError): d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner",dtype="policy")],[grant()])
    def test_missing_proposal_rejected(self):
        with self.assertRaises(d.ContractError): d.reduce([e("a",kind="accept",actor="owner")],[grant()])
    def test_provider_fields_do_not_change_projection(self):
        a=e("p",provider={"comment_id":1,"page":1}); b=e("p",provider={"comment_id":99,"page":8})
        ra,_=d.reduce([a],[]); rb,_=d.reduce([b],[])
        self.assertEqual(ra,rb)
    def test_grant_type_scope(self):
        rows,auth=d.reduce([e("p"),e("a",kind="accept",seq=2,actor="owner")],[grant(types=["policy"])])
        self.assertEqual(rows[0]["status"],"proposed"); self.assertFalse(auth[1]["authorized"])
    def test_supersession_cycle_rejected(self):
        events=[e("p1","A"),e("p2","B"),e("a1","A","accept",2,"owner"),e("a2","B","accept",2,"owner"),
                e("s1","A","supersede",3,"owner",supersedes_decision_id="B"),
                e("s2","B","supersede",4,"owner",supersedes_decision_id="A")]
        with self.assertRaises(d.ContractError): d.reduce(events,[grant()])
    def test_missing_superseded_target(self):
        events=[e("p"),e("a",kind="accept",seq=2,actor="owner"),e("s",kind="supersede",seq=3,actor="owner",supersedes_decision_id="missing")]
        with self.assertRaises(d.ContractError): d.reduce(events,[grant()])
    def test_project_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); events=root/"events.jsonl"; grants=root/"grants.jsonl"; out=root/"out"
            events.write_text("\n".join(json.dumps(x) for x in [e("p"),e("a",kind="accept",seq=2,actor="owner")])+"\n")
            grants.write_text(json.dumps(grant())+"\n")
            receipt=d.project(events,grants,out); d.verify_dir(out)
            self.assertEqual(receipt["status"],"PASS")
            routes=json.loads((out/"routes.logical.json").read_text())["routes"]
            self.assertEqual(routes[0]["logical_route"],"decisions/architecture/accepted")
            self.assertNotIn("http",json.dumps(routes))
    def test_tamper_fails_verify(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); events=root/"events.jsonl"; grants=root/"grants.jsonl"; out=root/"out"
            events.write_text(json.dumps(e("p"))+"\n"); grants.write_text("")
            d.project(events,grants,out); (out/"decisions.current.jsonl").write_text("{}\n")
            with self.assertRaises(d.ContractError): d.verify_dir(out)
    def test_deterministic_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); events=root/"events.jsonl"; grants=root/"grants.jsonl"
            events.write_text("\n".join(json.dumps(x) for x in [e("p"),e("a",kind="accept",seq=2,actor="owner")])+"\n")
            grants.write_text(json.dumps(grant())+"\n")
            d.project(events,grants,root/"a"); d.project(events,grants,root/"b")
            for rel in ["decisions.current.jsonl","authority.results.jsonl","routes.logical.json","receipt.json"]:
                self.assertEqual((root/"a"/rel).read_bytes(),(root/"b"/rel).read_bytes())

if __name__=="__main__": unittest.main()

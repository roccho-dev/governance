#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "package-responsibility-closure"
OBLIGATION_KINDS = {"packageObligation.v1","governance.packageObligation.v1","adrs.packageObligation.v1"}
RESPONSE_KINDS = {"packageResponse.v1","governance.packageResponse.v1","ops.packageResponse.v1","ui.packageResponse.v1","deploy.packageResponse.v1"}
CLOSED = {"implemented","adopted","closed","complete","pass","ok"}
BLOCKED = {"blocked","pending","incomplete"}
EXCLUDE = {"artifacts","artifact","generated","dist","build",".git","node_modules"}

def emit(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",",":"))
def dgst(x): return "sha256:" + hashlib.sha256(emit(x).encode()).hexdigest()
def t(row,*keys,default=""):
    for k in keys:
        v = row.get(k)
        if isinstance(v,str) and v.strip(): return v.strip()
    return default
def vals(v):
    if v is None: return []
    if isinstance(v,str): return [p for p in re.split(r"[, ]+", v.strip()) if p]
    if isinstance(v,list):
        out=[]
        for x in v:
            if isinstance(x,str) and x.strip(): out.append(x.strip())
            elif isinstance(x,dict):
                y=t(x,"id","testId","requiredTestId","path")
                if y: out.append(y)
        return out
    return []
def first(row,*keys):
    for k in keys:
        v=vals(row.get(k))
        if v: return sorted(set(v))
    return []
def read_jl(path):
    if not path.exists(): raise SystemExit(f"missing input:{path}")
    data=path.read_bytes()
    if b"\r" in data or data.startswith(b"\xef\xbb\xbf"): raise SystemExit(f"non-deterministic jsonl bytes:{path}")
    rows=[]
    for n,line in enumerate(data.decode().split("\n"),1):
        if not line.strip(): continue
        obj=json.loads(line)
        if not isinstance(obj,dict): raise SystemExit(f"{path}:{n}: row must be object")
        rows.append(obj)
    return rows
def write_jl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(emit(r)+"\n" for r in sorted(rows,key=emit)), encoding="utf-8")
def write_json(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
def pid_from_path(path):
    parts=[p for p in Path(path).parts if p and p!="."]
    return (parts[-1] if parts else "root").replace("_","-").lower()
def diag(code, repo, pid, src, cur, ideal):
    r={"kind":"governance.packageDiagnostic.v1","diagnostic":code,"repoLocator":repo,"packageId":pid,"source":src,"current":cur,"ideal":ideal,"authority":False}
    r["driftId"]=dgst(r); return r

def norm_obligation(row, src):
    pid=t(row,"package_id","packageId","package","packageIdCandidate")
    path=t(row,"package_path","packagePath","path")
    repo=t(row,"repo_locator","repoLocator","repo",default="repo:unknown")
    tests=first(row,"required_tests","requiredTests","requiredTestIds","required_test","requiredTestId")
    ref=t(row,"adrs_ref","adrsRef","sourceRef",default=src)
    oid=t(row,"obligation_id","obligationId",default=f"{ref}#{pid or pid_from_path(path)}")
    owner=t(row,"owner_role","ownerRole","owner",default="unknown")
    universe=t(row,"target_universe","targetUniverse",default="selected")
    out=[]; provisional=pid or (pid_from_path(path) if path else "unknown")
    if not pid: out.append(diag("package-id-missing",repo,provisional,src,"obligation lacks package id","add stable packageId")); pid=provisional
    if not path: out.append(diag("package-path-missing",repo,pid,src,"obligation lacks path","add packagePath"))
    if not tests: out.append(diag("required-test-missing",repo,pid,src,"obligation lacks required test","add requiredTests"))
    if universe in {"","unknown"}: out.append(diag("target-universe-unknown",repo,pid,src,"target universe unknown","bind selected universe"))
    r={"kind":"governance.packageObligation.v1","obligationId":oid,"repoLocator":repo,"packageId":pid,"packagePath":path,"requiredTests":tests,"ownerRole":owner,"targetUniverse":universe,"adrsRef":ref,"source":src,"authority":False}
    r["digest"]=dgst(r); return r,out
def parse_md(path):
    lines=path.read_text(encoding="utf-8").splitlines(); rows=[]
    for i,line in enumerate(lines[:-1]):
        heads=[c.strip().lower().replace(" ","_") for c in line.strip().strip("|").split("|")]
        if "|" not in line or ("package_id" not in heads and "packageid" not in heads): continue
        sep=lines[i+1].strip()
        if not sep.startswith("|") or set(sep.replace("|","").replace(":","").replace("-","").strip()): continue
        for body in lines[i+2:]:
            if "|" not in body or body.strip().startswith("#"): break
            cells=[c.strip() for c in body.strip().strip("|").split("|")]
            if len(cells)!=len(heads): continue
            m=dict(zip(heads,cells))
            rows.append({"kind":"packageObligation.v1","package_id":m.get("package_id") or m.get("packageid"),"package_path":m.get("package_path") or m.get("packagepath"),"required_test":m.get("required_test") or m.get("required_tests"),"repo_locator":m.get("repo_locator") or m.get("repo") or "repo:unknown","owner_role":m.get("owner_role") or m.get("owner") or "unknown","adrs_ref":str(path)})
    return rows
def obligations(root):
    rows=[]; diags=[]
    paths=[root] if root.is_file() else sorted(p for p in root.rglob("*") if p.suffix in {".jsonl",".md"} and ".git" not in p.parts)
    for p in paths:
        raw=read_jl(p) if p.suffix==".jsonl" else parse_md(p)
        for row in raw:
            if row.get("kind") in OBLIGATION_KINDS or any(k in row for k in ("packageId","package_id","packagePath","package_path")):
                r,d=norm_obligation(row,str(p)); rows.append(r); diags += d
    return sorted(rows,key=emit), sorted(diags,key=emit)

def read_json(path): return json.loads(path.read_text(encoding="utf-8"))
def inv_row(repo, p, kind):
    rel=str(p.relative_to(repo)); pkg=p/"package.json"; pid=pid_from_path(rel); tests=[]; entries=[]
    if pkg.exists():
        data=read_json(pkg); pid=t(data,"name",default=pid).split("/")[-1]
        if t(data,"main"): entries.append(t(data,"main"))
        scripts=data.get("scripts") if isinstance(data.get("scripts"),dict) else {}
        if "test" in scripts: tests.append("npm-test")
    r={"kind":"governance.packageInventory.v1","repoLocator":f"repo:{repo.name}","packagePath":rel,"packageIdCandidate":pid,"sourceKind":kind,"entrypoints":sorted(set(entries)),"tests":sorted(set(tests)),"confidence":"high" if pkg.exists() else "medium","discoveredBy":"package-responsibility-closure-scanner","authority":False}
    r["digest"]=dgst(r); return r
def generated_like(p): return any(x in EXCLUDE for x in p.parts)
def inventory(repo):
    rows={}; diags=[]; pd=repo/"packages"
    if pd.is_dir():
        for p in sorted(x for x in pd.iterdir() if x.is_dir()):
            r=inv_row(repo,p,"packages-dir"); rows[r["packagePath"]]=r
    elif (repo/"package.json").exists():
        r=inv_row(repo,repo,"package-json-root"); rows[r["packagePath"]]=r
    build=repo/"build"/"packages.jsonl"
    if build.exists():
        for x in read_jl(build):
            path=t(x,"packagePath","package_path","path"); pid=t(x,"packageId","package_id","packageIdCandidate",default=pid_from_path(path))
            r={"kind":"governance.packageInventory.v1","repoLocator":t(x,"repoLocator","repo_locator",default=f"repo:{repo.name}"),"packagePath":path,"packageIdCandidate":pid,"sourceKind":t(x,"sourceKind","source_kind",default="build-packages-jsonl"),"entrypoints":first(x,"entrypoints"),"tests":first(x,"tests","requiredTests"),"confidence":t(x,"confidence",default="high"),"discoveredBy":"package-responsibility-closure-scanner","authority":False}
            r["digest"]=dgst(r); rows.setdefault(path,r)
    for pkg in sorted(repo.rglob("package.json")):
        rel=pkg.parent.relative_to(repo)
        if rel!=Path(".") and generated_like(rel) and "packages" not in rel.parts:
            diags.append(diag("generated-artifact-misclassified",f"repo:{repo.name}",pid_from_path(str(rel)),str(pkg),"generated output looks package-like","exclude generated artifacts from source inventory"))
    return sorted(rows.values(),key=emit), sorted(diags,key=emit)

def norm_response(row, src):
    pid=t(row,"package_id","packageId","package","packageIdCandidate")
    repo=t(row,"repo_locator","repoLocator","repo",default="repo:unknown")
    tests=first(row,"required_tests","requiredTests","requiredTestIds","required_test","requiredTestId","tests")
    receipts=first(row,"receipts","receiptIds","receipt","receiptId"); residuals=first(row,"residuals","residualIds","residual","residualId")
    status=t(row,"status","adoptionStatus","closureStatus",default="unknown"); oid=t(row,"obligation_id","obligationId"); ref=t(row,"adrs_ref","adrsRef","sourceRef")
    out=[]
    if not pid: pid="unknown"; out.append(diag("response-shape-invalid",repo,pid,src,"response lacks package id","add packageId"))
    if not oid and not ref: out.append(diag("response-obligation-missing",repo,pid,src,"response lacks obligation link","add obligationId or adrsRef"))
    if not tests: out.append(diag("response-test-missing",repo,pid,src,"response cites no required tests","cite requiredTests"))
    if status in CLOSED and not receipts: out.append(diag("response-receipt-missing",repo,pid,src,"closure claim lacks receipt","attach receipt"))
    if status in BLOCKED and not residuals: out.append(diag("response-residual-hidden",repo,pid,src,"incomplete response hides residual","return residual"))
    auth=row.get("authority") is True or str(row.get("meaningAuthority","")).lower()=="true"
    r={"kind":"governance.packageResponse.v1","responseId":t(row,"response_id","responseId",default=f"{src}#{pid}"),"repoLocator":repo,"packageId":pid,"obligationId":oid,"adrsRef":ref,"requiredTests":tests,"receipts":receipts,"residuals":residuals,"ownerRole":t(row,"owner_role","ownerRole","owner",default="unknown"),"status":status,"sourceKind":t(row,"sourceKind","source_kind","kind",default="packageResponse.v1"),"authority":auth,"claims":first(row,"claims","claimIds"),"source":src}
    r["digest"]=dgst(r); return r,out
def responses(root):
    rows=[]; diags=[]; paths=[root] if root.is_file() else sorted(p for p in root.rglob("*.jsonl"))
    for p in paths:
        for row in read_jl(p):
            if row.get("kind") in RESPONSE_KINDS or any(k in row for k in ("packageId","package_id","obligationId","obligation_id")):
                r,d=norm_response(row,str(p)); rows.append(r); diags += d
    return sorted(rows,key=emit), sorted(diags,key=emit)

def drift(code,pid,repo,cur,ideal,oid="",inv="",resp=""):
    r={"kind":"governance.packageDrift.v1","diagnostic":code,"packageId":pid,"repoLocator":repo,"current":cur,"ideal":ideal,"obligationId":oid,"inventoryDigest":inv,"responseId":resp,"authority":False}
    r["driftId"]=dgst(r); return r
def join(obs, invs, resps):
    ob={r["packageId"]:r for r in obs}; inv={r["packageIdCandidate"]:r for r in invs}; rr={}
    for r in resps: rr.setdefault(r["packageId"],[]).append(r)
    out=[]
    for pid in sorted(set(ob)|set(inv)|set(rr)):
        o=ob.get(pid); i=inv.get(pid); rs=rr.get(pid,[]); r=rs[0] if rs else None
        repo=t(o or i or r or {},"repoLocator",default="repo:unknown"); oid=t(o or {},"obligationId"); invd=t(i or {},"digest"); rid=t(r or {},"responseId")
        if o and not i: out.append(drift("registered-package-missing-on-disk",pid,repo,f"ADRS path {t(o,'packagePath')} not found","create path or update ADRS with receipt",oid=oid,resp=rid))
        if i and not o: out.append(drift("unregistered-package",pid,repo,f"inventory path {t(i,'packagePath')} has no ADRS obligation","add ADRS obligation or exclude non-package",inv=invd,resp=rid))
        if o and not rs: out.append(drift("claim-missing",pid,repo,"obligation has no package response","target repo must emit packageResponse.v1",oid=oid,inv=invd))
        if r and not o: out.append(drift("extra-response",pid,repo,"response exists without ADRS obligation","bind response or remove overclaim",inv=invd,resp=rid))
        if o and i and t(o,"packagePath") and t(o,"packagePath")!=t(i,"packagePath") and not any("move" in x or "path" in x for x in first(r or {},"receipts")):
            out.append(drift("package-path-drift",pid,repo,f"ADRS={t(o,'packagePath')} inventory={t(i,'packagePath')}","add move receipt or update ADRS path",oid=oid,inv=invd,resp=rid))
        if o and r:
            req=set(first(o,"requiredTests")); cited=set(first(r,"requiredTests"))
            if req and not req<=cited: out.append(drift("required-test-missing",pid,repo,f"missing tests {sorted(req-cited)}","cite every required test",oid=oid,inv=invd,resp=rid))
            if t(r,"status") in CLOSED and not first(r,"receipts"): out.append(drift("receipt-missing",pid,repo,"closed response has no receipt","attach receipt",oid=oid,inv=invd,resp=rid))
            if t(r,"status") in BLOCKED and not first(r,"residuals"): out.append(drift("residual-hidden",pid,repo,"blocked response hides residual","return residual for next gap loop",oid=oid,inv=invd,resp=rid))
            if t(o,"ownerRole",default="unknown")!="unknown" and t(r,"ownerRole",default="unknown")!="unknown" and t(o,"ownerRole")!=t(r,"ownerRole"): out.append(drift("owner-role-mismatch",pid,repo,f"obligation owner={t(o,'ownerRole')} response owner={t(r,'ownerRole')}","correct owner role must answer",oid=oid,inv=invd,resp=rid))
            if r.get("authority") is True: out.append(drift("authority-collision",pid,repo,"response marks itself as authority","responses must remain non-authority receipts",oid=oid,inv=invd,resp=rid))
            allowed=req|{oid,t(o,"adrsRef")}; extra={x for x in first(r,"claims") if x not in allowed}
            if extra: out.append(drift("overclaim",pid,repo,f"unexpected claims {sorted(extra)}","claim only accepted obligation/test boundary",oid=oid,inv=invd,resp=rid))
    return sorted(out,key=emit)

def scope(code):
    return {"registered-package-missing-on-disk":"create package or update ADRS path with receipt","unregistered-package":"add ADRS obligation or exclude non-source package","claim-missing":"emit packageResponse.v1","extra-response":"bind/remove response","overclaim":"reduce response boundary","package-path-drift":"add move receipt or update ADRS path","required-test-missing":"add/cite required test","receipt-missing":"attach closure receipt","residual-hidden":"return residual rows","owner-role-mismatch":"route to correct owner role","authority-collision":"remove authority claim","generated-artifact-misclassified":"exclude generated artifact"}.get(code,"inspect diagnostic")
def work(rows):
    out=[]
    for r in rows:
        code=t(r,"diagnostic"); pid=t(r,"packageId",default="unknown"); repo=t(r,"repoLocator",default="repo:unknown")
        w={"kind":"governance.packageWorkOrder.v1","primary_gap_id":f"package-closure:{repo}:{pid}:{code}","repo_locator":repo,"package_id":pid,"diagnostic":code,"current":t(r,"current"),"ideal":t(r,"ideal"),"suggested_pr_title":f"Close package responsibility gap for {pid}: {code}","suggested_scope":scope(code),"proof_required":["updated package closure compiler output"],"receipt_required":code in {"receipt-missing","package-path-drift","registered-package-missing-on-disk","required-test-missing","owner-role-mismatch","authority-collision","overclaim"},"residual_policy":"must return residual when not fully closed","blocking_level":"warning" if code=="generated-artifact-misclassified" else "blocking","authority":False}
        w["digest"]=dgst(w); out.append(w)
    return sorted(out,key=emit)

def compile_all(adrs, repo, resp):
    obs,od=obligations(adrs); invs,idg=inventory(repo); rs,rd=responses(resp); dr=join(obs,invs,rs)
    diagnostics=sorted([*od,*idg,*rd,*dr],key=emit)
    return {"obligations":obs,"inventory":invs,"responses":rs,"diagnostics":diagnostics,"drifts":dr,"work_orders":work(diagnostics)}
def write_outputs(out,result):
    names={"obligations":"package-obligations.jsonl","inventory":"package-inventory.jsonl","responses":"package-responses.jsonl","diagnostics":"package-diagnostics.jsonl","drifts":"package-drifts.jsonl","work_orders":"package-work-orders.jsonl"}
    for k,n in names.items(): write_jl(out/n,result[k])
    summary={"kind":"governance.packageResponsibilityClosure.summary.v1","status":"pass","authority":False,"counts":{k:len(v) for k,v in result.items()},"diagnostics":sorted({t(r,"diagnostic") for r in result["diagnostics"]})}
    summary["digest"]=dgst(summary); write_json(out/"summary.json",summary)
def selftest():
    r=compile_all(FIXTURE/"adrs",FIXTURE/"repo",FIXTURE/"responses")
    got={t(x,"diagnostic") for x in r["diagnostics"]}
    need={"registered-package-missing-on-disk","unregistered-package","claim-missing","extra-response","package-path-drift","required-test-missing","receipt-missing","residual-hidden","owner-role-mismatch","authority-collision","generated-artifact-misclassified","response-obligation-missing"}
    if need-got: raise SystemExit(emit({"missingDiagnostics":sorted(need-got),"got":sorted(got)}))
    with tempfile.TemporaryDirectory() as d:
        out=Path(d)/"out"; write_outputs(out,r); a=(out/"package-work-orders.jsonl").read_text(); write_outputs(out,r); b=(out/"package-work-orders.jsonl").read_text()
        if a!=b: raise SystemExit("non-deterministic work order output")
    print(emit({"kind":"governance.packageResponsibilityClosure.selftest.v1","status":"pass","authority":False,"diagnosticCount":len(r["diagnostics"]),"workOrderCount":len(r["work_orders"]),"diagnostics":sorted(got)}))
    return 0
def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",nargs="?",choices=["build","selftest"],default="build")
    p.add_argument("--adrs",type=Path,default=FIXTURE/"adrs"); p.add_argument("--repo",type=Path,default=FIXTURE/"repo"); p.add_argument("--responses",type=Path,default=FIXTURE/"responses"); p.add_argument("--out-dir",type=Path)
    a=p.parse_args()
    if a.command=="selftest": return selftest()
    r=compile_all(a.adrs,a.repo,a.responses)
    if a.out_dir: write_outputs(a.out_dir,r)
    else:
        for x in r["work_orders"]: print(emit(x))
    return 0
if __name__ == "__main__": raise SystemExit(main())

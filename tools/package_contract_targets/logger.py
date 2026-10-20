#!/usr/bin/env python3
from __future__ import annotations

import copy, hashlib, json, shutil, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable

TARGET_ID="logger"; LOGICAL_REPOSITORY="roccho-org/ops+roccho-dev/apps"; PROVIDER_REPOSITORY="roccho-org/ops"
CLAIM_CEILING="LOGGER_SELECTED_SCOPE_ESTABLISHED_NOT_OPERATIONAL_ADOPTION"
OBLIGATION_ID="ops.logger-language-neutral-design.v1"; SUBJECT_KEY="design:logger-language-neutral"
ROLE="logger-establishment"; EPOCH="logger-language-neutral-establishment-v1"; SCOPE_CANDIDATE_FIELD="retainedKCandidate"
REQUIREMENT_PATH="decisions/logger-language-neutral-contract-admission-261020.jsonl"
RAW_ID="raw.adrs.logger_language_neutral_contract_admission.261020.02"
MEANING="sha256:ab3c271e57ba33a7e663f99d417680f6044cc59c099e5223978e2e4ef6811e3c"
K_ROOT="packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment"
SOURCE_PATHS={
 "retainedManifest":f"{K_ROOT}/manifest.json","retainedArtifact":f"{K_ROOT}/technical-closure.zip",
 "independentJudgment":f"{K_ROOT}/r-v32-capture.json","independentJudgmentOriginal":f"{K_ROOT}/r-v32-comment.md",
 "comparatorCli":"packages/contract-diff/bin/contract-diff.py","comparatorCore":"packages/contract-diff/core.py"}
ACCEPTED_FILES={"acceptedDecision":REQUIREMENT_PATH,"acceptedRollout":REQUIREMENT_PATH}
EXPECTED_NEGATIVE={"contract-drift":"OPEN","missing-observation":"OPEN","wrong-candidate":"OPEN","missing-admission":"UNKNOWN"}
STATUS_EXIT={"CLOSED":0,"OPEN":2,"INVALID":3,"UNKNOWN":4}
REQUIRED_SOURCE_ROLE="acceptedRollout"; PROVIDED_SOURCE_ROLE="retainedManifest"; RECEIPT_SOURCE_ROLE="independentJudgment"
EXPECTED_REQUIRED=["purpose_scope_coverage","shared_meaning","cross_language_interoperability","pure_application_boundary","environment_transport","host_context_ownership","supply_consumption_binding","actual_data_use","traceable_evidence","bounded_safe_failure","compatibility","causal_design_closure","small_extensible_design"]
EXPECTED_PROFILES={"cli_batch":"implemented_observed","library":"implemented_observed","browser":"implemented_observed","service":"supported_design_only","worker":"supported_design_only"}
EXPECTED_OLD_UNMET=["cross_language_interoperability","environment_transport","supply_consumption_binding","bounded_safe_failure","causal_design_closure"]
EXPECTED_OBSERVATION={"repository":"roccho-org/ops","revision":"3372357c67803d0b8c0875eea70bcc642391fa5a","tree":"19f38cc4ea3eef3cb7a99bfb1823455aa53dce11"}
EXPECTED_PROVIDER={"repository":"roccho-org/ops","role":"provider","revision":"fe968fc6b8919fed48151a57f421667bce0aac87","tree":"b306bf999aba32a678ac48b5a56e4b4a0a3c0cf8"}
EXPECTED_CONSUMER={"repository":"roccho-dev/apps","role":"consumer","revision":"17c0108a5c2549ffaf7cef791a569f2e1926659f","tree":"3d603665d54c83dd770873870c66863959904b42"}
OLD={"applicable":13,"evaluated":13,"met":8,"unmet":5,"unknown":0,"conflict":0,"stale":0}
CURRENT={"applicable":13,"evaluated":13,"met":13,"unmet":0,"unknown":0,"conflict":0,"stale":0,"residual":0}
ARTIFACT_SHA="sha256:5ac5df9deb5bf6c9a36de31e6d534b23673f0d5016ae7d576b2cd716741000a7"; ARTIFACT_BYTES=98368
R_BODY_SHA="sha256:56945f7657ae16089fa299dead5dfbd50b462196fc3976cb2c6b056cf71021f4"
ENTRY={"SHA256SUMS":"sha256:464f61fd6e4e3c31cae10750fee75c08eb1d6d3535b82bc7ca04ae003551eb19","finding.json":"sha256:1ecdcc85fc40c84c86ae270d59725ce579b0c555f1d33247b19cfab13981f10f","closure.json":"sha256:ca8d98049d5e4ecca0ad79ecc2fd838bf4dfda3fb585ea38ac23489f6cff96c6","metadata.json":"sha256:75cb7d697919fe759e483c5e774891387217f6ffb6fec69a4e1f48ec3b73fa78","browser.json":"sha256:85e4e5e0881d2522bafcbeb50f00bb9c79387ee12bc4f3c9dafc42a202bf5d01","interoperability.json":"sha256:f44513b701211e39221f7f0bf95608e9a317b14ff9b1c73e101260633ef29cc9"}

def _canonical(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def _digest(v:Any)->str:return "sha256:"+hashlib.sha256(_canonical(v).encode()).hexdigest()
def _sha_bytes(v:bytes)->str:return "sha256:"+hashlib.sha256(v).hexdigest()
def _sha_file(p:Path)->str:return _sha_bytes(p.read_bytes())
def _need(ok:bool,code:str,detail:Any=None)->None:
 if not ok: raise ValueError("logger-adapter:"+code+("" if detail is None else ":"+_canonical(detail)))
def _read(p:Path)->Any:return json.loads(p.read_text(encoding="utf-8"))
def _read_one(p:Path)->dict[str,Any]:
 rows=[json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x];_need(len(rows)==1 and isinstance(rows[0],dict),"single-row",p.as_posix());return rows[0]
def _write(p:Path,v:Any)->None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(_canonical(v)+"\n",encoding="utf-8")
def _run(a:list[str],cwd:Path):return subprocess.run(a,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
def _source(repo:str,rev:str,rel:str,native:Path)->dict[str,str]:_need(native.is_file() and not native.is_symlink(),"source-missing",rel);return {"repository":repo,"revision":rev,"path":rel,"digest":_sha_file(native)}
def _copy(repo:str,rev:str,rel:str,native:Path,bundle:Path,dst:str)->dict[str,Any]:
 out=bundle/dst;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(native,out);return {"source":_source(repo,rev,rel,native),"bundlePath":dst}

def _semantic(row:dict[str,Any])->dict[str,Any]:
 _need(row.get("schema")=="adr_raw_event.v1" and row.get("raw_id")==RAW_ID and row.get("subject_key")==SUBJECT_KEY,"admission-identity")
 a=row.get("authority");m=row.get("meaning_identity");i=row.get("meaning_identity_contract");s=row.get("admission_scope")
 _need(isinstance(a,dict) and a.get("meaning_admitted") is True and a.get("current_selected") is True,"admission-authority")
 _need(all(isinstance(x,dict) for x in (m,i,s)),"admission-shape")
 r=m.get("required");_need(m.get("subject",{}).get("obligation_id")==OBLIGATION_ID and i.get("meaning_digest")==MEANING,"meaning")
 _need(isinstance(r,dict) and list(r)==EXPECTED_REQUIRED and s.get("applicable_required")==EXPECTED_REQUIRED,"required-universe")
 _need(s.get("profile_targets")==EXPECTED_PROFILES and s.get("technical_observation")==EXPECTED_OBSERVATION and s.get("repaired_tree_set")==[EXPECTED_PROVIDER,EXPECTED_CONSUMER],"admission-scope")
 return {"meaningSha256":MEANING,"obligationId":OBLIGATION_ID,"required":r,"profileTargets":EXPECTED_PROFILES,"targetRepositories":m["subject"].get("target_repositories"),"technicalObservation":EXPECTED_OBSERVATION,"repairedTreeSet":[EXPECTED_PROVIDER,EXPECTED_CONSUMER]}
def _contract(row:dict[str,Any],digest:Callable[[Any],str])->dict[str,Any]:
 semantic=_semantic(row);return {"obligation_digest":digest(semantic),"capability":"logger-language-neutral-design","consumer":LOGICAL_REPOSITORY,"stage":"contract-establishment","target":{"provider":"github","resource":"logger-language-neutral-design","account":"selected-scope"},"slot":OBLIGATION_ID,"binding":MEANING,"profile":[{"role":ROLE,"operation":"logger-language-neutral-establishment","readback":True,"grade":"real"}]}
def describe()->dict[str,Any]:return {"targetId":TARGET_ID,"logicalRepository":LOGICAL_REPOSITORY,"providerRepository":PROVIDER_REPOSITORY,"claimCeiling":CLAIM_CEILING,"obligationId":OBLIGATION_ID,"lowerVerifierPath":None,"sourcePaths":SOURCE_PATHS,"acceptedFiles":ACCEPTED_FILES,"expectedNegative":EXPECTED_NEGATIVE,"statusExit":STATUS_EXIT}
def required_contract(decision:dict[str,Any],rollout:dict[str,Any],digest:Callable[[Any],str],check_token:Callable[[str],str]):del check_token;_need(decision==rollout,"accepted-source-role-drift");return decision,_contract(decision,digest)

def _safe(name:str)->str:
 p=PurePosixPath(name);_need(name!="" and not p.is_absolute() and ".." not in p.parts and "\\" not in name,"k-archive-path",name);return name
def _checks(raw:bytes)->dict[str,str]:
 out={}
 for line in raw.decode().splitlines():
  _need(len(line)>68 and line[64:67]=="  ./","k-checksum-row",line[:80]);d,n=line[:64],line[67:];_safe(n);_need(len(d)==64 and all(c in "0123456789abcdef" for c in d) and n not in out,"k-checksum");out[n]="sha256:"+d
 return out

def _verify_k(manifest_path:Path,artifact_path:Path,judgment_path:Path,original_path:Path)->dict[str,Any]:
 manifest=_read(manifest_path);judgment=_read(judgment_path);original=original_path.read_text(encoding="utf-8")
 _need(manifest.get("schema")=="ops.logger-language-neutral.retained-k/3" and manifest.get("authority") is False,"k-manifest")
 _need(manifest.get("canonicalMeaning")=={"repository":"roccho-dev/adrs","revision":"6e4abcd22dbee397105625b6041ce1a0d4720182","tree":"cf28509d770022d2be6e4d172b0ce8b9486cced1","path":REQUIREMENT_PATH,"gitBlob":"9371fed680451f58976a00fda0a71e4fbb54f68f","rawId":RAW_ID,"meaningSha256":MEANING,"obligationId":OBLIGATION_ID},"k-canonical")
 oa=manifest.get("originalArtifact",{});_need(oa.get("artifactId")==12240652155 and oa.get("bytes")==ARTIFACT_BYTES and oa.get("sha256")==ARTIFACT_SHA and oa.get("entries")==ENTRY,"k-artifact-declaration")
 _need(artifact_path.stat().st_size==ARTIFACT_BYTES and _sha_file(artifact_path)==ARTIFACT_SHA,"k-artifact-native")
 with zipfile.ZipFile(artifact_path) as z:
  names=z.namelist();_need(len(names)==len(set(names)) and "SHA256SUMS" in names,"k-archive-universe");[_safe(n) for n in names]
  checks=_checks(z.read("SHA256SUMS"));_need(set(checks)==set(names)-{"SHA256SUMS"},"k-checksum-universe")
  _need(_sha_bytes(z.read("SHA256SUMS"))==ENTRY["SHA256SUMS"],"k-checksum-body")
  for n,d in checks.items():_need(_sha_bytes(z.read(n))==d,"k-entry-digest",n)
  for n,d in ENTRY.items():_need(n in names and _sha_bytes(z.read(n))==d,"k-required-entry",n)
  finding=json.loads(z.read("finding.json"));closure=json.loads(z.read("closure.json"));metadata=json.loads(z.read("metadata.json"));browser=json.loads(z.read("browser.json"));interop=json.loads(z.read("interoperability.json"))
 _need(finding.get("candidate",{}).get("meaningSha256")==MEANING and finding.get("coverage")==OLD and finding.get("finding",{}).get("unmet")==EXPECTED_OLD_UNMET,"k-old-finding")
 sm=finding.get("supportMatrix",{});profiles=sm.get("runtimeProfiles",{});_need(sm.get("frozenBeforeFinding") is True and {n:profiles.get(n,{}).get("targetState") for n in EXPECTED_PROFILES}==EXPECTED_PROFILES,"k-matrix")
 _need(closure.get("schema")=="ops.logger-language-neutral.closure/1" and closure.get("authority") is False and closure.get("admitted") is False,"k-closure-boundary")
 _need(closure.get("contract",{}).get("meaningSha256")==MEANING and closure.get("old",{}).get("findingSha256")==ENTRY["finding.json"] and closure.get("old",{}).get("coverage")==OLD,"k-closure-old")
 _need(closure.get("coverage")==CURRENT and closure.get("status")=="CONFORMANT","k-closure-current")
 met=closure.get("finding",{}).get("met",[]);obs=closure.get("obligations",{});_need(len(met)==13 and set(met)==set(EXPECTED_REQUIRED) and set(obs)==set(EXPECTED_REQUIRED) and all(x.get("status")=="met" for x in obs.values()),"k-obligations")
 rep=closure.get("repaired",{});_need(rep.get("observation")=={"revision":EXPECTED_OBSERVATION["revision"],"tree":EXPECTED_OBSERVATION["tree"]},"k-observation")
 _need({k:rep.get("provider",{}).get(k) for k in ("repository","revision","tree")}=={k:EXPECTED_PROVIDER[k] for k in ("repository","revision","tree")},"k-provider")
 _need({k:rep.get("consumer",{}).get(k) for k in ("repository","revision","tree")}=={k:EXPECTED_CONSUMER[k] for k in ("repository","revision","tree")},"k-consumer")
 _need(set(closure.get("decisions",{}))==set(EXPECTED_OLD_UNMET) and closure.get("independentMateriality",{}).get("verdict")=="TRUE POSITIVE / MATERIAL","k-causality")
 _need(metadata.get("candidateMeaningSha256")==MEANING and metadata.get("observationHead")==EXPECTED_OBSERVATION["revision"] and metadata.get("observationTree")==EXPECTED_OBSERVATION["tree"] and metadata.get("repairedTreeSet")==[EXPECTED_PROVIDER,EXPECTED_CONSUMER] and metadata.get("actualInterchangeExecution") is True and metadata.get("actualBrowserExecution") is True and metadata.get("actualFailureStateExecution") is True and metadata.get("technicalConformance") is True and metadata.get("admitted") is False,"k-metadata")
 _need(browser.get("status")=="PASS" and browser.get("authority") is False and browser.get("providerRevision")==EXPECTED_PROVIDER["revision"] and browser.get("action")=="inspect-judgment-provider" and browser.get("actualFailureState")=={"state":"failed","primaryResult":"failed","transport":"accepted"} and browser.get("controls")==["wrong-source","wrong-code","invalid-diagnostic","transport-preserved-primary"],"k-browser")
 _need(interop.get("status")=="PASS" and interop.get("authority") is False and interop.get("implementation",{}).get("pythonDelegatesToNode") is False and interop.get("interchange")=={"javascriptToPython":"byte-identical","pythonToJavascript":"byte-identical","rows":16} and interop.get("counts",{}).get("accepted")==16 and interop.get("counts",{}).get("rejected")==16 and interop.get("browser")=={"callbackWrites":1,"invalidPartialWrites":0,"transportRejectionPropagated":True},"k-interchange")
 ij=manifest.get("independentJudgment",{});_need(ij.get("originalBodyPath")=="r-v32-comment.md" and ij.get("originalBodyBytes")==9488 and ij.get("originalBodySha256")==R_BODY_SHA and ij.get("sourceCommentId")==6283358664,"k-r-declaration")
 _need(original_path.stat().st_size==9488 and _sha_file(original_path)==R_BODY_SHA,"k-r-native")
 for marker in ("### R v32","fixed T0 8 MET / 5 UNMET preservation       = PASS","fixed 13 obligations current evaluation      = 13 / 13 MET","finite corrected-scope technical closure      = TRUE","13/13 CONFORMANT・residual 0"): _need(marker in original,"k-r-marker",marker)
 _need(judgment.get("source",{}).get("commentId")==6283358664 and judgment.get("target",{}).get("meaningSha256")==MEANING and judgment.get("verdict",{}).get("fixedT0")=={"applicable":13,"met":8,"unmet":5,"unknown":0,"conflict":0,"stale":0} and judgment.get("verdict",{}).get("repaired")=={**CURRENT,"status":"CONFORMANT"},"k-r-capture")
 return {"kind":"governance.loggerRetainedKReadback.v3","status":"PASS","authority":False,"manifestDigest":_sha_file(manifest_path),"artifactDigest":_sha_file(artifact_path),"artifactBytes":artifact_path.stat().st_size,"archiveEntriesVerified":len(names),"archiveChecksumsVerified":len(checks),"findingDigest":ENTRY["finding.json"],"closureDigest":ENTRY["closure.json"],"judgmentDigest":_sha_file(judgment_path),"judgmentOriginalDigest":_sha_file(original_path),"oldCoverage":OLD,"currentCoverage":CURRENT,"profiles":EXPECTED_PROFILES,"meaningSha256":MEANING,"causality":EXPECTED_OLD_UNMET}

def _compare(cli:Path,packet:Path,admission:Path,cwd:Path):
 p=_run([sys.executable,str(cli),"--input",str(packet),"--admission",str(admission)],cwd);_need(p.stdout.strip()!="","contract-diff-empty",{"exit":p.returncode,"stderr":p.stderr[-2000:]});return p.returncode,json.loads(p.stdout)
def _bundle(bundle:Path,bindings:dict[str,Any],role:str)->Path:
 value=bindings.get(role);_need(isinstance(value,dict) and isinstance(value.get("bundlePath"),str),"bundle-source-binding",role);p=bundle/value["bundlePath"];_need(p.is_file() and not p.is_symlink(),"bundle-source-file",role);return p

def expected_evidence(*,scope:dict[str,Any],sources:dict[str,dict[str,Any]],bindings:dict[str,Any],bundle:Path,receipt_rows:list[dict[str,Any]],read_object:Callable[[Path,str],dict[str,Any]],sha256_file:Callable[[Path],str],digest:Callable[[Any],str],required_contract:dict[str,Any])->dict[str,Any]:
 del sha256_file
 k=_verify_k(_bundle(bundle,bindings,"retainedManifest"),_bundle(bundle,bindings,"retainedArtifact"),_bundle(bundle,bindings,"independentJudgment"),_bundle(bundle,bindings,"independentJudgmentOriginal"));_need(read_object(bundle/"logger-k-readback.json","logger-k")==k,"evidence-k-reconstruction")
 canonical=read_object(bundle/"logger-canonical-source-readback.json","logger-canonical");accepted=read_object(_bundle(bundle,bindings,"acceptedDecision"),"accepted-decision")
 _need(canonical.get("status")=="PASS" and canonical.get("rawId")==RAW_ID and canonical.get("meaningSha256")==MEANING and canonical.get("objectDigest")==digest(accepted) and canonical.get("semanticDigest")==digest(_semantic(accepted)) and canonical.get("selection")=="existing-cold-select-record" and canonical.get("codecBlob")=="f861d0019667ee679da3d374dac8e117adae05d0","evidence-cold-route")
 return {"kind":"governance.loggerLanguageNeutralEstablishmentEvidence.v2","status":"PASS","authority":False,"adoption":False,"releasePublished":False,"claimCeiling":CLAIM_CEILING,"scope":scope,"acceptedRequirement":{"source":sources["acceptedRollout"],"decisionSource":sources["acceptedDecision"],"obligationId":OBLIGATION_ID,"contract":required_contract},"provided":{"source":sources["retainedManifest"],"artifactSource":sources["retainedArtifact"],"contract":required_contract},"observation":{"source":sources["observer"],"candidate":scope[SCOPE_CANDIDATE_FIELD]},"receipt":{"source":sources["independentJudgment"],"originalSource":sources["independentJudgmentOriginal"],"normalizedReceiptDigest":digest(receipt_rows[0]),"role":ROLE,"operation":"logger-language-neutral-establishment","grade":"real","readback":True},"retainedK":k,"canonicalSource":canonical,"comparator":{"source":sources["comparatorCore"],"positive":read_object(bundle/"contract-diff-positive.json","positive"),"negative":{n:read_object(bundle/f"contract-diff-negative-{n}.json","negative:"+n) for n in EXPECTED_NEGATIVE}},"remaining":0}

def produce(context:dict[str,Any])->dict[str,Any]:
 from tools.package_contract_port_cold import select_cold_record
 bundle=Path(context["bundle"]).resolve();target=Path(context["targetSourceRoot"]).resolve();accepted=Path(context["acceptedRequirementRoot"]).resolve();runtime=Path(context["contractRuntimeRoot"]).resolve();observer=Path(context["observerRoot"]).resolve();candidate=str(context["targetCandidate"]);accepted_revision=str(context["acceptedRequirementRevision"]);governance=str(context["governanceCandidate"]);adapter=str(context["adapterPath"]);executor=context["evidenceExecutor"]
 _need(not bundle.exists(),"bundle-exists");bundle.mkdir(parents=True)
 selected=select_cold_record(root=accepted,code_root=accepted,git="git",reference="HEAD",revision=accepted_revision,path=REQUIREMENT_PATH,record_id=RAW_ID);requirement_path=accepted/REQUIREMENT_PATH;requirement=_read_one(requirement_path);_need(selected.get("object")==requirement,"cold-selected-object");required=_contract(requirement,_digest)
 k=_verify_k(target/SOURCE_PATHS["retainedManifest"],target/SOURCE_PATHS["retainedArtifact"],target/SOURCE_PATHS["independentJudgment"],target/SOURCE_PATHS["independentJudgmentOriginal"]);_write(bundle/"logger-k-readback.json",k)
 ss=selected.get("source",{});canonical={"kind":"governance.loggerCanonicalAcceptedSourceReadback.v2","status":"PASS","authority":False,"selection":"existing-cold-select-record","repository":"roccho-dev/adrs","revision":accepted_revision,"holdingRevision":ss.get("holdingRevision"),"tree":ss.get("tree"),"path":REQUIREMENT_PATH,"gitBlob":ss.get("gitBlob"),"rawId":RAW_ID,"codecBlob":selected.get("codecBlob"),"objectDigest":_digest(requirement),"semanticDigest":_digest(_semantic(requirement)),"meaningSha256":MEANING};_need(canonical["holdingRevision"]==accepted_revision and canonical["gitBlob"]=="9371fed680451f58976a00fda0a71e4fbb54f68f","cold-selected-source");_write(bundle/"logger-canonical-source-readback.json",canonical)
 bindings={
  "retainedManifest":_copy(PROVIDER_REPOSITORY,candidate,SOURCE_PATHS["retainedManifest"],target/SOURCE_PATHS["retainedManifest"],bundle,"sources/ops/retained-k-manifest.json"),"retainedArtifact":_copy(PROVIDER_REPOSITORY,candidate,SOURCE_PATHS["retainedArtifact"],target/SOURCE_PATHS["retainedArtifact"],bundle,"sources/ops/technical-closure.zip"),"independentJudgment":_copy(PROVIDER_REPOSITORY,candidate,SOURCE_PATHS["independentJudgment"],target/SOURCE_PATHS["independentJudgment"],bundle,"sources/ops/r-v32-capture.json"),"independentJudgmentOriginal":_copy(PROVIDER_REPOSITORY,candidate,SOURCE_PATHS["independentJudgmentOriginal"],target/SOURCE_PATHS["independentJudgmentOriginal"],bundle,"sources/ops/r-v32-comment.md"),
  "comparatorCli":_copy("roccho-org/ops","5eb98c82417b399978c1e38aebab5e3fb39752d4",SOURCE_PATHS["comparatorCli"],runtime/SOURCE_PATHS["comparatorCli"],bundle,"sources/runtime/contract-diff.py"),"comparatorCore":_copy("roccho-org/ops","5eb98c82417b399978c1e38aebab5e3fb39752d4",SOURCE_PATHS["comparatorCore"],runtime/SOURCE_PATHS["comparatorCore"],bundle,"sources/runtime/contract-diff-core.py"),
  "acceptedDecision":_copy("roccho-dev/adrs",accepted_revision,REQUIREMENT_PATH,requirement_path,bundle,"sources/adrs/logger-admission-decision.jsonl"),"acceptedRollout":_copy("roccho-dev/adrs",accepted_revision,REQUIREMENT_PATH,requirement_path,bundle,"sources/adrs/logger-admission-rollout.jsonl"),"observer":_copy("roccho-dev/governance",governance,adapter,observer/adapter,bundle,"sources/observer/source")}
 _write(bundle/"source-bindings.json",bindings)
 rid=f"receipt:{candidate}:{ROLE}";receipt={"id":rid,"obligation_id":OBLIGATION_ID,"role":ROLE,"attempt":candidate,"epoch":EPOCH,"source":bindings["retainedManifest"]["source"],"target":required["target"],"slot":required["slot"],"operation":executor["operation"],"status":"PASS","readback":"PASS","grade":executor["grade"]}
 packet={"kind":"contractDiffInput.v1","required":{"source":bindings["acceptedRollout"]["source"],"rows":[{"id":OBLIGATION_ID,"contract":copy.deepcopy(required)}]},"provided":{"source":bindings["retainedManifest"]["source"],"rows":[{"id":OBLIGATION_ID,"contract":copy.deepcopy(required),"evidence_refs":{ROLE:rid}}]},"observations":{"source":bindings["observer"]["source"],"rows":[{"id":OBLIGATION_ID,"attempt":candidate,"epoch":EPOCH,"refs":{ROLE:rid}}]},"receipts":{"source":bindings["independentJudgment"]["source"],"rows":[receipt]}}
 admission={"kind":"contractDiffAdmission.v1","scope":{"id":"logger-language-neutral-establishment","authority":bindings["acceptedDecision"]["source"],"epoch":EPOCH,"allow_empty":False,"grade":"source","excluded_ids":[]},"universe":[{"id":OBLIGATION_ID,"obligation_digest":required["obligation_digest"],"profile":required["profile"]}],"inventory":{},"evidence":{rid:_digest(receipt)}}
 for name in ("required","provided","observations","receipts"):
  rows=sorted(packet[name]["rows"],key=lambda x:x["id"]);admission["inventory"][name]={"source":packet[name]["source"],"rows_digest":_digest(rows),"count":len(rows)}
 _write(bundle/"contract-diff-input.json",packet);_write(bundle/"contract-diff-admission.json",admission);cli=runtime/SOURCE_PATHS["comparatorCli"];code,positive=_compare(cli,bundle/"contract-diff-input.json",bundle/"contract-diff-admission.json",runtime);_need(code==0 and positive.get("status")=="CLOSED" and positive.get("findings")==[],"positive",positive);_write(bundle/"contract-diff-positive.json",positive)
 cases={};drift=copy.deepcopy(packet);drift["provided"]["rows"][0]["contract"]["target"]["resource"]="wrong-logger-design";da=copy.deepcopy(admission);rows=sorted(drift["provided"]["rows"],key=lambda x:x["id"]);da["inventory"]["provided"]={"source":drift["provided"]["source"],"rows_digest":_digest(rows),"count":len(rows)};cases["contract-drift"]=(drift,da,"OPEN")
 missing=copy.deepcopy(packet);missing["observations"]["rows"]=[];ma=copy.deepcopy(admission);ma["inventory"]["observations"]={"source":missing["observations"]["source"],"rows_digest":_digest([]),"count":0};cases["missing-observation"]=(missing,ma,"OPEN")
 stale=copy.deepcopy(packet);stale["observations"]["rows"][0]["attempt"]="0"*40;sa=copy.deepcopy(admission);rows=sorted(stale["observations"]["rows"],key=lambda x:x["id"]);sa["inventory"]["observations"]={"source":stale["observations"]["source"],"rows_digest":_digest(rows),"count":len(rows)};cases["wrong-candidate"]=(stale,sa,"OPEN");cases["missing-admission"]=(packet,{},"UNKNOWN")
 for name,(bad,adm,expected) in cases.items():
  pp=bundle/f"negative-{name}-input.json";ap=bundle/f"negative-{name}-admission.json";_write(pp,bad);_write(ap,adm);exit_code,result=_compare(cli,pp,ap,runtime);_need(exit_code==STATUS_EXIT[expected] and result.get("status")==expected,"negative",{"case":name,"exit":exit_code,"result":result});_write(bundle/f"contract-diff-negative-{name}.json",result)
 scope={"kind":"governance.loggerLanguageNeutralEstablishmentScope.v1","authority":False,"scopeId":"logger-language-neutral-establishment","selectedObligations":[OBLIGATION_ID],SCOPE_CANDIDATE_FIELD:candidate,"subjectKey":SUBJECT_KEY,"governanceRevision":"692013f50581437fb9004cdedafedbb4a7a271de","acceptedRequirementDigest":required["obligation_digest"],"requiredEvidenceTypes":[ROLE]};_write(bundle/"run-scope.json",scope)
 evidence=expected_evidence(scope=scope,sources={k:v["source"] for k,v in bindings.items()},bindings=bindings,bundle=bundle,receipt_rows=[receipt],read_object=lambda p,l:_read(p),sha256_file=_sha_file,digest=_digest,required_contract=required);_write(bundle/"phase4-evidence.json",evidence)
 manifest=[{"path":p.relative_to(bundle).as_posix(),"sha256":_sha_file(p)} for p in sorted(bundle.rglob("*")) if p.is_file() and p.name!="bundle-manifest.json"];_write(bundle/"bundle-manifest.json",manifest)
 return {"kind":"governance.packageContractTargetMaterials.v1","targetId":TARGET_ID,"bundle":str(bundle),"producerFiles":["logger-k-readback.json","logger-canonical-source-readback.json"],"authority":False}

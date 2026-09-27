#!/usr/bin/env python3
"""Provider-neutral ADR lifecycle reducer and typed-view projector.

GitHub/provider fields are accepted only as transport annotations and are excluded
from semantic digests. The source of truth remains the append event ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

EVENT_SCHEMA = "adrs.lifecycleEvent.v1"
GRANT_SCHEMA = "adrs.authorityGrant.v1"
AUTH_SCHEMA = "adrs.authorityResult.v1"
CURRENT_SCHEMA = "adrs.currentDecision.v1"
VIEW_SCHEMA = "adrs.decisionView.v1"
ROUTES_SCHEMA = "adrs.logicalRoutes.v1"
RECEIPT_SCHEMA = "adrs.decisionProjectionReceipt.v1"

KINDS = {"propose", "accept", "amend", "reject", "revoke", "supersede"}
PROTECTED = {"accept", "amend", "reject", "revoke", "supersede"}
STATUSES = {
    "proposed", "accepted", "accepted-with-pending-amendment", "rejected",
    "revoked", "superseded", "conflict",
}
SAFE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
IGNORED_SEMANTIC_KEYS = {
    "provider", "transport", "source_locator", "source_url", "comment_id",
    "issue_id", "page", "page_index", "fetched_at", "etag",
}

class ContractError(ValueError):
    pass

def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()

def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()

def file_sha(path: pathlib.Path) -> str:
    return sha(path.read_bytes())

def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{path}:{n}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractError(f"{path}:{n}: record must be object")
        out.append(value)
    return out

def write_jsonl(path: pathlib.Path, rows: Iterable[dict[str, Any]]) -> str:
    data = b"".join(canonical(row) for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha(data)

def clean_semantic(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: clean_semantic(v) for k, v in value.items()
                if k not in IGNORED_SEMANTIC_KEYS and k != "projection_digest"}
    if isinstance(value, list):
        return [clean_semantic(x) for x in value]
    return value

def validate_event(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema") != EVENT_SCHEMA:
        raise ContractError(f"event schema must be {EVENT_SCHEMA}")
    required = ("event_id", "decision_id", "decision_type", "kind", "actor", "seq")
    for key in required:
        if key not in raw:
            raise ContractError(f"event missing {key}")
    for key in ("event_id", "decision_id", "actor"):
        if not isinstance(raw[key], str) or not ID.fullmatch(raw[key]):
            raise ContractError(f"invalid {key}: {raw[key]!r}")
    if not isinstance(raw["decision_type"], str) or not SAFE.fullmatch(raw["decision_type"]):
        raise ContractError(f"invalid decision_type: {raw['decision_type']!r}")
    if raw["kind"] not in KINDS:
        raise ContractError(f"unknown event kind: {raw['kind']!r}")
    if not isinstance(raw["seq"], int) or raw["seq"] < 0:
        raise ContractError("seq must be non-negative integer")
    if raw["kind"] == "supersede":
        target = raw.get("supersedes_decision_id")
        if not isinstance(target, str) or not ID.fullmatch(target):
            raise ContractError("supersede requires supersedes_decision_id")
        if target == raw["decision_id"]:
            raise ContractError("decision cannot supersede itself")
    return clean_semantic(raw)

def validate_grant(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema") != GRANT_SCHEMA:
        raise ContractError(f"grant schema must be {GRANT_SCHEMA}")
    actor = raw.get("actor")
    if not isinstance(actor, str) or not ID.fullmatch(actor):
        raise ContractError("invalid grant actor")
    actions = raw.get("actions")
    types = raw.get("decision_types", ["*"])
    if not isinstance(actions, list) or not actions or any(x not in PROTECTED for x in actions):
        raise ContractError("grant actions invalid")
    if not isinstance(types, list) or not types or any(x != "*" and not SAFE.fullmatch(x) for x in types):
        raise ContractError("grant decision_types invalid")
    return {
        "schema": GRANT_SCHEMA, "actor": actor,
        "actions": sorted(set(actions)), "decision_types": sorted(set(types)),
        "valid": raw.get("valid", True) is True,
        "grant_id": raw.get("grant_id", actor + ":default"),
        "evidence_digest": raw.get("evidence_digest"),
    }

def authorized(grants: list[dict[str, Any]], event: dict[str, Any]) -> tuple[bool, str | None]:
    if event["kind"] not in PROTECTED:
        return True, None
    for grant in grants:
        if not grant["valid"] or grant["actor"] != event["actor"]:
            continue
        if event["kind"] not in grant["actions"]:
            continue
        if "*" not in grant["decision_types"] and event["decision_type"] not in grant["decision_types"]:
            continue
        return True, grant["grant_id"]
    return False, None

def ensure_acyclic_supersession(events: list[dict[str, Any]]) -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for event in events:
        if event["kind"] == "supersede":
            graph[event["decision_id"]].add(event["supersedes_decision_id"])
    visiting: set[str] = set(); done: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting:
            raise ContractError("supersession cycle")
        if node in done:
            return
        visiting.add(node)
        for child in graph.get(node, ()):
            visit(child)
        visiting.remove(node); done.add(node)
    for node in graph:
        visit(node)

@dataclass
class State:
    decision_id: str
    decision_type: str
    title: str = ""
    summary: str = ""
    status: str = "proposed"
    current_event_id: str = ""
    effective_event_ids: list[str] = None
    conflicts: list[str] = None
    pending_amendment_event_id: str | None = None
    superseded_by: str | None = None
    def __post_init__(self) -> None:
        self.effective_event_ids = self.effective_event_ids or []
        self.conflicts = self.conflicts or []

def transition(state: State | None, event: dict[str, Any]) -> State:
    kind = event["kind"]
    if state is None:
        if kind != "propose":
            raise ContractError(f"{event['event_id']}: {kind} before propose")
        state = State(event["decision_id"], event["decision_type"])
    if state.decision_type != event["decision_type"]:
        raise ContractError(f"{event['decision_id']}: decision_type changed")
    if kind == "propose":
        if state.effective_event_ids:
            raise ContractError(f"{event['decision_id']}: duplicate proposal")
        state.status = "proposed"
    elif kind == "accept":
        if state.status not in {"proposed", "accepted-with-pending-amendment"}:
            raise ContractError(f"{event['event_id']}: cannot accept from {state.status}")
        state.status = "accepted"; state.pending_amendment_event_id = None
    elif kind == "amend":
        if state.status != "accepted":
            raise ContractError(f"{event['event_id']}: cannot amend from {state.status}")
        state.status = "accepted-with-pending-amendment"
        state.pending_amendment_event_id = event["event_id"]
    elif kind == "reject":
        if state.status not in {"proposed", "accepted-with-pending-amendment"}:
            raise ContractError(f"{event['event_id']}: cannot reject from {state.status}")
        state.status = "rejected"; state.pending_amendment_event_id = None
    elif kind == "revoke":
        if state.status not in {"accepted", "accepted-with-pending-amendment"}:
            raise ContractError(f"{event['event_id']}: cannot revoke from {state.status}")
        state.status = "revoked"; state.pending_amendment_event_id = None
    elif kind == "supersede":
        if state.status not in {"accepted", "accepted-with-pending-amendment"}:
            raise ContractError(f"{event['event_id']}: cannot supersede from {state.status}")
        state.status = "superseded"
        state.superseded_by = event["decision_id"]
    state.current_event_id = event["event_id"]
    state.effective_event_ids.append(event["event_id"])
    state.title = str(event.get("title", state.title))
    state.summary = str(event.get("summary", state.summary))
    return state

def reduce(events_raw: list[dict[str, Any]], grants_raw: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = [validate_event(x) for x in events_raw]
    grants = [validate_grant(x) for x in grants_raw]
    ids = [x["event_id"] for x in events]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate event_id")
    ensure_acyclic_supersession(events)
    known_decisions = {x["decision_id"] for x in events if x["kind"] == "propose"}
    for x in events:
        if x["kind"] == "supersede" and x["supersedes_decision_id"] not in known_decisions:
            raise ContractError(f"missing superseded decision: {x['supersedes_decision_id']}")

    events.sort(key=lambda x: (x["seq"], x["event_id"]))
    auth_rows: list[dict[str, Any]] = []
    effective: list[dict[str, Any]] = []
    for event in events:
        ok, grant_id = authorized(grants, event)
        auth_rows.append({
            "schema": AUTH_SCHEMA, "event_id": event["event_id"],
            "decision_id": event["decision_id"], "kind": event["kind"],
            "authorized": ok, "reason": "authorized" if ok else "no-matching-grant",
            "grant_id": grant_id,
        })
        if ok:
            effective.append(event)

    states: dict[str, State] = {}
    by_seq: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in effective:
        by_seq[(event["decision_id"], event["seq"])].append(event)
    conflicted = {
        key: rows for key, rows in by_seq.items()
        if len(rows) > 1 and len({r["kind"] for r in rows}) > 1
    }
    for event in effective:
        key = (event["decision_id"], event["seq"])
        if key in conflicted:
            state = states.get(event["decision_id"])
            if state is None:
                proposal = next((r for r in conflicted[key] if r["kind"] == "propose"), None)
                if proposal is None:
                    raise ContractError(f"{event['decision_id']}: conflict before proposal")
                state = State(event["decision_id"], event["decision_type"])
            state.status = "conflict"
            state.conflicts = sorted(r["event_id"] for r in conflicted[key])
            state.current_event_id = state.conflicts[-1]
            state.effective_event_ids.extend(x for x in state.conflicts if x not in state.effective_event_ids)
            states[event["decision_id"]] = state
            continue
        if states.get(event["decision_id"]) and states[event["decision_id"]].status == "conflict":
            continue
        states[event["decision_id"]] = transition(states.get(event["decision_id"]), event)

    for event in effective:
        if event["kind"] != "supersede":
            continue
        target = states[event["supersedes_decision_id"]]
        if target.status not in {"accepted", "accepted-with-pending-amendment", "superseded"}:
            raise ContractError(f"{event['event_id']}: target not supersedable")
        target.status = "superseded"; target.superseded_by = event["decision_id"]
        if event["event_id"] not in target.effective_event_ids:
            target.effective_event_ids.append(event["event_id"])
        target.current_event_id = event["event_id"]

    rows: list[dict[str, Any]] = []
    for decision_id in sorted(states):
        s = states[decision_id]
        if s.status not in STATUSES:
            raise ContractError(f"unsupported status: {s.status}")
        row: dict[str, Any] = {
            "schema": CURRENT_SCHEMA, "decision_id": s.decision_id,
            "decision_type": s.decision_type, "status": s.status,
            "title": s.title, "summary": s.summary,
            "current_event_id": s.current_event_id,
            "effective_event_ids": sorted(set(s.effective_event_ids)),
            "conflict_event_ids": sorted(set(s.conflicts)),
            "pending_amendment_event_id": s.pending_amendment_event_id,
            "superseded_by": s.superseded_by,
        }
        row["projection_digest"] = sha(canonical(clean_semantic(row)))
        rows.append(row)
    return rows, auth_rows

def project(events_path: pathlib.Path, grants_path: pathlib.Path, out: pathlib.Path) -> dict[str, Any]:
    current, auth_rows = reduce(load_jsonl(events_path), load_jsonl(grants_path))
    staging = pathlib.Path(tempfile.mkdtemp(prefix="decisionctl-", dir=out.parent if out.parent.exists() else None))
    try:
        current_digest = write_jsonl(staging / "decisions.current.jsonl", current)
        authority_digest = write_jsonl(staging / "authority.results.jsonl", auth_rows)
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in current:
            view = {
                "schema": VIEW_SCHEMA,
                "decision_id": row["decision_id"], "decision_type": row["decision_type"],
                "status": row["status"], "title": row["title"], "summary": row["summary"],
                "current_event_id": row["current_event_id"],
                "projection_digest": row["projection_digest"],
                "conflict_event_ids": row["conflict_event_ids"],
                "pending_amendment_event_id": row["pending_amendment_event_id"],
            }
            grouped[(row["decision_type"], row["status"])].append(view)
        routes=[]; view_digests=[]
        for (dtype, status), rows in sorted(grouped.items()):
            rel = pathlib.Path("views") / dtype / f"{status}.jsonl"
            digest = write_jsonl(staging / rel, sorted(rows, key=lambda x: x["decision_id"]))
            view_digests.append({"path": rel.as_posix(), "digest": digest})
            routes.append({
                "decision_type": dtype, "status": status,
                "logical_route": f"decisions/{dtype}/{status}",
                "renderer_id": "decision-list/1", "data_path": rel.as_posix(),
                "data_digest": digest, "projection_contract": VIEW_SCHEMA,
            })
        routes_obj = {"schema": ROUTES_SCHEMA, "routes": routes}
        routes_digest = sha(canonical(routes_obj))
        (staging / "routes.logical.json").write_bytes(canonical(routes_obj))
        receipt = {
            "schema": RECEIPT_SCHEMA, "status": "PASS", "cutover": False,
            "input_digest": file_sha(events_path), "grants_digest": file_sha(grants_path),
            "authority_results_digest": authority_digest,
            "current_projection_digest": current_digest,
            "view_set": view_digests, "logical_routes_digest": routes_digest,
        }
        (staging / "receipt.json").write_bytes(canonical(receipt))
        verify_dir(staging)
        if out.exists():
            shutil.rmtree(out)
        staging.rename(out)
        return receipt
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

def verify_dir(out: pathlib.Path) -> None:
    receipt = json.loads((out / "receipt.json").read_text())
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise ContractError("invalid receipt")
    if file_sha(out / "authority.results.jsonl") != receipt["authority_results_digest"]:
        raise ContractError("authority digest mismatch")
    if file_sha(out / "decisions.current.jsonl") != receipt["current_projection_digest"]:
        raise ContractError("current digest mismatch")
    routes = json.loads((out / "routes.logical.json").read_text())
    if sha(canonical(routes)) != receipt["logical_routes_digest"]:
        raise ContractError("routes digest mismatch")
    declared = {x["path"]: x["digest"] for x in receipt["view_set"]}
    for rel, digest in declared.items():
        if file_sha(out / rel) != digest:
            raise ContractError(f"view digest mismatch: {rel}")
    for route in routes["routes"]:
        if route["data_path"] not in declared or route["data_digest"] != declared[route["data_path"]]:
            raise ContractError("route references undeclared view")

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="decisionctl")
    sub = p.add_subparsers(dest="cmd", required=True)
    runp = sub.add_parser("run")
    runp.add_argument("--events", required=True, type=pathlib.Path)
    runp.add_argument("--grants", required=True, type=pathlib.Path)
    runp.add_argument("--out", required=True, type=pathlib.Path)
    ver = sub.add_parser("verify")
    ver.add_argument("--out", required=True, type=pathlib.Path)
    args = p.parse_args(argv)
    try:
        if args.cmd == "run":
            print(json.dumps(project(args.events, args.grants, args.out), sort_keys=True))
        else:
            verify_dir(args.out); print("PASS")
        return 0
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"decisionctl: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

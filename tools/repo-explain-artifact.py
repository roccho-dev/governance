#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def read_jsonl(path: Path):
    files = sorted(path.rglob("*.jsonl")) if path.is_dir() else [path]
    rows = []
    for file in files:
        with file.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def choose(rows, repo, root, audience):
    decisions = [
        r for r in rows
        if r.get("kind") == "adrs.repoResponsibilityDecision.v1"
        and r.get("scope", {}).get("repo") == repo
        and r.get("state") == "accepted"
        and r.get("lifecycle") == "active"
    ]
    if len(decisions) != 1:
        raise SystemExit("expected exactly one active accepted responsibility decision for repo")
    decision = decisions[0]
    responsibilities = [r for r in rows if r.get("kind") == "adrs.repoResponsibility.v1" and r.get("id") == decision.get("subjectId")]
    if len(responsibilities) != 1:
        raise SystemExit("expected exactly one responsibility row for decision subject")
    responsibility = responsibilities[0]
    if responsibility.get("repo") != repo:
        raise SystemExit("responsibility repo mismatch")
    if audience == "public" and responsibility.get("audience", "internal") != "public":
        raise SystemExit("public artifact cannot use internal responsibility row")

    purposes = {r.get("id"): r for r in rows if r.get("kind") == "adrs.purpose.v1"}
    chain = []
    seen = set()
    current = responsibility.get("purposeId")
    while current is not None:
        if current in seen:
            raise SystemExit("purpose cycle: " + current)
        seen.add(current)
        purpose = purposes.get(current)
        if purpose is None:
            raise SystemExit("missing purpose: " + str(current))
        chain.append(purpose)
        current = purpose.get("parentId")
        if len(chain) > 32:
            raise SystemExit("purpose chain too deep")
    if chain[-1].get("id") != root:
        raise SystemExit("purpose root mismatch")
    return decision, responsibility, chain


def get_path(data, dotted):
    value = data
    for part in dotted.split("."):
        value = value[part]
    return value


def render(template_rows, data):
    out = []
    blocks = [r for r in template_rows if r.get("kind") == "governance.mdTemplate.block.v1"]
    for block in sorted(blocks, key=lambda r: r["order"]):
        kind = block.get("block")
        if kind == "title":
            out += ["# " + str(get_path(data, block["field"])), ""]
        elif kind == "quote":
            out += ["> " + line for line in block.get("lines", [])] + [""]
        elif kind == "heading":
            out += ["#" * int(block["level"]) + " " + block["text"], ""]
        elif kind == "kv":
            out += ["- " + item["label"] + ": " + str(get_path(data, item["field"])) for item in block.get("entries", [])] + [""]
        elif kind == "list":
            values = get_path(data, block["field"])
            out += (["- " + str(v) for v in values] if values else ["- " + block.get("empty", "None")]) + [""]
        else:
            raise SystemExit("unknown markdown template block: " + str(kind))
    return "\n".join(out).rstrip() + "\n"


def build(args):
    rows = read_jsonl(Path(args.input))
    template_rows = read_jsonl(Path(args.template))
    decision, responsibility, chain = choose(rows, args.repo, args.required_root, args.audience)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source_rows = chain + [responsibility, decision]
    sources = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in source_rows)
    (out / "sources.jsonl").write_text(sources, encoding="utf-8")
    source_sha = sha256_text(sources)

    data = {
        "repoTitle": args.repo.split("/")[-1],
        "purpose": {"direct": chain[0]["statement"], "highest": chain[-1]["statement"], "depth": len(chain) - 1},
        "responsibility": {
            "role": responsibility["role"],
            "lifecycle": decision["lifecycle"],
            "audience": responsibility["audience"],
            "summary": responsibility["summary"],
            "owns": responsibility["owns"],
            "mustNotOwn": responsibility["mustNotOwn"],
            "inputs": responsibility["inputs"],
            "outputs": responsibility["outputs"],
            "effects": responsibility.get("effects", []),
        },
        "provenance": {
            "repository": args.repo,
            "responsibility": responsibility["id"],
            "decision": decision["id"],
            "sourceClosure": "sha256:" + source_sha,
            "projector": "repo-explain-artifact.v1",
        },
    }

    readme = render(template_rows, data)
    (out / "README.md").write_text(readme, encoding="utf-8")
    template_text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in template_rows)
    manifest = {
        "kind": "governance.repoExplainArtifact.manifest.v1",
        "nonAuthority": True,
        "projector": "repo-explain-artifact.v1",
        "repo": args.repo,
        "audience": args.audience,
        "purposeRootId": args.required_root,
        "purposeDepth": len(chain) - 1,
        "responsibilityId": responsibility["id"],
        "decisionId": decision["id"],
        "role": responsibility["role"],
        "lifecycle": decision["lifecycle"],
        "sourceClosureSha256": "sha256:" + source_sha,
        "templateSha256": "sha256:" + sha256_text(template_text),
        "files": {
            "README.md": {"sha256": sha256_text(readme)},
            "sources.jsonl": {"sha256": source_sha},
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("[OK] repo explanation artifact: " + str(out))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--input", required=True)
    b.add_argument("--repo", required=True)
    b.add_argument("--required-root", required=True)
    b.add_argument("--audience", choices=["public", "internal"], required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--template", default=str(Path(__file__).resolve().parents[1] / "templates/repo-explain/readme.md.template.v1.jsonl"))
    args = parser.parse_args()
    if args.command == "build":
        build(args)


if __name__ == "__main__":
    main()

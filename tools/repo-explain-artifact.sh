#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: repo-explain-artifact build --input PATH --repo OWNER/REPO --required-root PURPOSE_ID --audience public|internal --out DIR [--template PATH]

Build a non-authority Markdown repository explanation artifact from ADR-derived JSONL rows and a Markdown template JSONL.
EOF
  exit 2
}

if [ "${1:-}" != "build" ]; then usage; fi
shift
input="" repo="" required_root="" audience="" out="" template=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    --repo) repo="$2"; shift 2 ;;
    --required-root) required_root="$2"; shift 2 ;;
    --audience) audience="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    --template) template="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$input" ] && [ -n "$repo" ] && [ -n "$required_root" ] && [ -n "$audience" ] && [ -n "$out" ] || usage
case "$audience" in public|internal) ;; *) echo "invalid audience: $audience" >&2; exit 2 ;; esac
[ -e "$input" ] || { echo "missing input: $input" >&2; exit 1; }
if [ -z "$template" ]; then
  template="$(cd "$(dirname "$0")/.." && pwd)/templates/repo-explain/readme.md.template.v1.jsonl"
fi
[ -f "$template" ] || { echo "missing markdown template: $template" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
rows="$work/rows.jsonl"
if [ -d "$input" ]; then
  find "$input" -type f -name '*.jsonl' -print | LC_ALL=C sort | while IFS= read -r f; do cat "$f"; printf '\n'; done > "$rows"
else
  cat "$input" > "$rows"
fi

jq -c . "$rows" > "$work/normalized.jsonl"
jq -c . "$template" > "$work/template.jsonl"

jq -s --arg repo "$repo" --arg root "$required_root" --arg audience "$audience" '
  def fail($m): error($m);
  def pubok($a): ($audience == "internal") or ($a == "public");
  def uniq_by_id: unique_by(.id);
  . as $rows
  | ($rows | map(select(.kind=="adrs.repoResponsibilityDecision.v1" and .scope.repo==$repo and .state=="accepted" and .lifecycle=="active"))) as $decisions
  | if ($decisions|length) != 1 then fail("expected exactly one active accepted responsibility decision for repo") else . end
  | ($decisions[0]) as $decision
  | ($rows | map(select(.kind=="adrs.repoResponsibility.v1" and .id==$decision.subjectId))) as $rs
  | if ($rs|length) != 1 then fail("expected exactly one responsibility row for decision subject") else . end
  | ($rs[0]) as $r
  | if ($r.repo != $repo) then fail("responsibility repo mismatch") else . end
  | if (pubok($r.audience // "internal") | not) then fail("public artifact cannot use internal responsibility row") else . end
  | ($rows | map(select(.kind=="adrs.purpose.v1")) | uniq_by_id) as $purposes
  | def purpose($id): ($purposes | map(select(.id==$id)) | if length==1 then .[0] else fail("missing or duplicate purpose: "+$id) end);
  | def chain($id; $seen):
      if ($seen|index($id)) then fail("purpose cycle: "+$id)
      else (purpose($id)) as $p
        | if $p.parentId == null then [$p]
          elif ($seen|length) > 32 then fail("purpose chain too deep")
          else [$p] + chain($p.parentId; $seen + [$id])
          end
      end;
  | (chain($r.purposeId; [])) as $chain
  | if ($chain[-1].id != $root) then fail("purpose root mismatch") else . end
  | {
      kind:"governance.repoExplainArtifact.selected.v1",
      repo:$repo,
      audience:$audience,
      decision:$decision,
      responsibility:$r,
      purposeChain:$chain,
      nonAuthority:true,
      projector:"repo-explain-artifact.v1"
    }
' "$work/normalized.jsonl" > "$work/selected.json"

mkdir -p "$out"
jq -cS '.purposeChain[], .responsibility, .decision' "$work/selected.json" > "$out/sources.jsonl"
source_sha="$(sha256sum "$out/sources.jsonl" | awk '{print $1}')"

jq --arg sourceClosure "sha256:$source_sha" '
  {
    repoTitle:(.repo | split("/")[-1]),
    purpose:{direct:.purposeChain[0].statement, highest:.purposeChain[-1].statement, depth:(.purposeChain|length - 1)},
    responsibility:{role:.responsibility.role, lifecycle:.decision.lifecycle, audience:.responsibility.audience, summary:.responsibility.summary, owns:.responsibility.owns, mustNotOwn:.responsibility.mustNotOwn, inputs:.responsibility.inputs, outputs:.responsibility.outputs, effects:.responsibility.effects},
    provenance:{repository:.repo, responsibility:.responsibility.id, decision:.decision.id, sourceClosure:$sourceClosure, projector:"repo-explain-artifact.v1"}
  }
' "$work/selected.json" > "$work/readme-data.json"

jq -s -r --slurpfile data "$work/readme-data.json" '
  ($data[0]) as $d
  | def get($field): $d | getpath($field | split("."));
    def marks($n): reduce range(0; $n) as $i (""; . + "#");
    def scalar($field): get($field) | tostring;
    def render:
      if .block == "title" then "# \(scalar(.field))\n\n"
      elif .block == "quote" then ((.lines | map("> " + .) | join("\n")) + "\n\n")
      elif .block == "heading" then "\(marks(.level)) \(.text)\n\n"
      elif .block == "kv" then ((.entries | map("- \(.label): \(scalar(.field))") | join("\n")) + "\n\n")
      elif .block == "list" then ((get(.field)) as $xs | (if ($xs|length)==0 then ["- \(.empty // "None")"] else ($xs | map("- " + .)) end | join("\n")) + "\n\n")
      else error("unknown markdown template block: " + (.block // "null")) end;
    sort_by(.order)[] | select(.kind=="governance.mdTemplate.block.v1") | render
' "$work/template.jsonl" > "$out/README.md"
readme_sha="$(sha256sum "$out/README.md" | awk '{print $1}')"
template_sha="$(sha256sum "$work/template.jsonl" | awk '{print $1}')"

jq -nS \
  --arg kind 'governance.repoExplainArtifact.manifest.v1' \
  --arg repo "$repo" \
  --arg audience "$audience" \
  --arg root "$required_root" \
  --arg sourceSha "sha256:$source_sha" \
  --arg templateSha "sha256:$template_sha" \
  --arg readmeSha "$readme_sha" \
  --arg sourcesSha "$source_sha" \
  --arg responsibilityId "$(jq -r '.responsibility.id' "$work/selected.json")" \
  --arg decisionId "$(jq -r '.decision.id' "$work/selected.json")" \
  --arg role "$(jq -r '.responsibility.role' "$work/selected.json")" \
  --arg lifecycle "$(jq -r '.decision.lifecycle' "$work/selected.json")" \
  --argjson depth "$(jq '.purposeChain|length - 1' "$work/selected.json")" \
  '{kind:$kind,nonAuthority:true,projector:"repo-explain-artifact.v1",repo:$repo,audience:$audience,purposeRootId:$root,purposeDepth:$depth,responsibilityId:$responsibilityId,decisionId:$decisionId,role:$role,lifecycle:$lifecycle,sourceClosureSha256:$sourceSha,templateSha256:$templateSha,files:{"README.md":{sha256:$readmeSha},"sources.jsonl":{sha256:$sourcesSha}}}' \
  > "$out/manifest.json"

echo "[OK] repo explanation artifact: $out"

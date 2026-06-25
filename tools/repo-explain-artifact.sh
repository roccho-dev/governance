#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: repo-explain-artifact build --input PATH --repo OWNER/REPO --required-root PURPOSE_ID --audience public|internal --out DIR

Build a non-authority repository explanation artifact from ADR-derived JSONL rows.
EOF
  exit 2
}

if [ "${1:-}" != "build" ]; then usage; fi
shift
input="" repo="" required_root="" audience="" out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --input) input="$2"; shift 2 ;;
    --repo) repo="$2"; shift 2 ;;
    --required-root) required_root="$2"; shift 2 ;;
    --audience) audience="$2"; shift 2 ;;
    --out) out="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$input" ] && [ -n "$repo" ] && [ -n "$required_root" ] && [ -n "$audience" ] && [ -n "$out" ] || usage
case "$audience" in public|internal) ;; *) echo "invalid audience: $audience" >&2; exit 2 ;; esac
[ -e "$input" ] || { echo "missing input: $input" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
rows="$work/rows.jsonl"
if [ -d "$input" ]; then
  find "$input" -type f -name '*.jsonl' -print | LC_ALL=C sort | while IFS= read -r f; do cat "$f"; printf '\n'; done > "$rows"
else
  cat "$input" > "$rows"
fi

jq -c . "$rows" > "$work/normalized.jsonl"

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
readme="$out/README.md"
{
  repo_title="$(jq -r '.repo' "$work/selected.json" | sed 's#.*/##')"
  echo "# $repo_title"
  echo
  echo "> Generated non-authority repository explanation. Do not edit this artifact."
  echo "> It states accepted intended responsibility; it does not prove implementation or runtime conformity."
  echo
  echo "## Purpose"
  echo
  echo "- Direct: $(jq -r '.purposeChain[0].statement' "$work/selected.json")"
  echo "- Highest: $(jq -r '.purposeChain[-1].statement' "$work/selected.json")"
  echo "- Lineage depth: $(jq -r '.purposeChain|length - 1' "$work/selected.json")"
  echo
  echo "## Responsibility"
  echo
  echo "- Role: \`$(jq -r '.responsibility.role' "$work/selected.json")\`"
  echo "- Lifecycle: \`$(jq -r '.decision.lifecycle' "$work/selected.json")\`"
  echo "- Audience: \`$(jq -r '.responsibility.audience' "$work/selected.json")\`"
  echo "- Summary: $(jq -r '.responsibility.summary' "$work/selected.json")"
  echo
  echo "### Owns"
  echo
  jq -r '.responsibility.owns[] | "- " + .' "$work/selected.json"
  echo
  echo "### Must not own"
  echo
  jq -r '.responsibility.mustNotOwn[] | "- " + .' "$work/selected.json"
  echo
  echo "## Contract"
  echo
  echo "### Inputs"
  echo
  jq -r '.responsibility.inputs[] | "- " + .' "$work/selected.json"
  echo
  echo "### Outputs"
  echo
  jq -r '.responsibility.outputs[] | "- " + .' "$work/selected.json"
  echo
  echo "### Effects"
  echo
  if [ "$(jq '.responsibility.effects|length' "$work/selected.json")" = "0" ]; then echo "- None"; else jq -r '.responsibility.effects[] | "- " + .' "$work/selected.json"; fi
  echo
  echo "## Provenance"
  echo
  echo "- Repository: \`$(jq -r '.repo' "$work/selected.json")\`"
  echo "- Responsibility: \`$(jq -r '.responsibility.id' "$work/selected.json")\`"
  echo "- Decision: \`$(jq -r '.decision.id' "$work/selected.json")\`"
  echo "- Source closure: \`sha256:$source_sha\`"
  echo "- Projector: \`repo-explain-artifact.v1\`"
} > "$readme"
readme_sha="$(sha256sum "$readme" | awk '{print $1}')"

jq -nS \
  --arg kind 'governance.repoExplainArtifact.manifest.v1' \
  --arg repo "$repo" \
  --arg audience "$audience" \
  --arg root "$required_root" \
  --arg sourceSha "sha256:$source_sha" \
  --arg readmeSha "$readme_sha" \
  --arg sourcesSha "$source_sha" \
  --arg responsibilityId "$(jq -r '.responsibility.id' "$work/selected.json")" \
  --arg decisionId "$(jq -r '.decision.id' "$work/selected.json")" \
  --arg role "$(jq -r '.responsibility.role' "$work/selected.json")" \
  --arg lifecycle "$(jq -r '.decision.lifecycle' "$work/selected.json")" \
  --argjson depth "$(jq '.purposeChain|length - 1' "$work/selected.json")" \
  '{kind:$kind,nonAuthority:true,projector:"repo-explain-artifact.v1",repo:$repo,audience:$audience,purposeRootId:$root,purposeDepth:$depth,responsibilityId:$responsibilityId,decisionId:$decisionId,role:$role,lifecycle:$lifecycle,sourceClosureSha256:$sourceSha,files:{"README.md":{sha256:$readmeSha},"sources.jsonl":{sha256:$sourcesSha}}}' \
  > "$out/manifest.json"

echo "[OK] repo explanation artifact: $out"
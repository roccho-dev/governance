#!/usr/bin/env python3
"""Route exact synthetic-only deltas, never issue release eligibility."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

POLICY = "tools/contract-input-fixture-ci.py"
WORKFLOW = ".github/workflows/gov-final-scope-purpose-join.yml"
INTENT = "ci.intent.v1.jsonl"
FIXTURES = {
    "tools/contract_input.py",
    "tools/contract-modeling/tests/test_contract_input.py",
    "tools/contract-modeling/tests/test_contract_input_scope.py",
    "tools/contract-modeling/CONTRACT_INPUT_FIXTURES.md",
}
SUFFIX = "; exact synthetic-only input deltas use a distinct fixture check without release eligibility"
BEGIN, END = "  # BEGIN synthetic input routing\n", "  # END synthetic input routing\n"
RUNTIME = """      - name: Read public fixed Ops runtime for input regression
        uses: actions/checkout@v4
        with:
          repository: roccho-org/ops
          ref: 5eb98c82417b399978c1e38aebab5e3fb39752d4
          path: _fixture-public-ops
          fetch-depth: 0
          persist-credentials: false
"""
ROUTES = (
    ("  gate:\n    name: gate\n", "  gate:\n    name: ${{ needs.input_scope.outputs.mode == 'real' && 'gate' || 'real-data gate not evaluated' }}\n"),
    ("  capture:\n", "  capture:\n    needs: input_scope\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("    needs: capture\n", "    needs: [input_scope, capture]\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("  live-consumers:\n", "  live-consumers:\n    needs: input_scope\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("  control-plane-observation:\n", "  control-plane-observation:\n    needs: input_scope\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("    needs: source-capture\n", "    needs: [input_scope, source-capture]\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("    needs: [capture, regression, live-consumers]\n", "    needs: [input_scope, capture, regression, live-consumers]\n    if: needs.input_scope.outputs.mode == 'real'\n"),
    ("    needs: gate\n", "    needs: [input_scope, gate]\n"),
    ("    if: github.event_name == 'push' && github.ref == 'refs/heads/proposals'\n",
     "    if: needs.input_scope.outputs.mode == 'real' && github.event_name == 'push' && github.ref == 'refs/heads/proposals'\n"),
)


class ScopeError(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise ScopeError(reason)


def git(root, *args):
    result = subprocess.run([os.environ.get("CONTRACT_INPUT_GIT", "git"), "--no-optional-locks", "-c", "core.autocrlf=false", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
        "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    need(result.returncode == 0, "scope-git:" + args[0])
    return result.stdout


def read(root, revision, path):
    return git(root, "show", revision + ":" + path)


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def public_jobs(policy_blob):
    return BEGIN + """  input_scope:
    name: exact input scope
    runs-on: ubuntu-latest
    outputs:
      mode: ${{ steps.scope.outputs.mode }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          persist-credentials: false
      - name: Use immutable base policy or the reviewed bootstrap blob
        id: scope
        env:
          EVENT: ${{ github.event_name }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}
          BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before || github.sha }}
        run: |
          set -euo pipefail
          [[ "$BASE_SHA" =~ ^[0-9a-f]{40}$ && "$BASE_SHA" != 0000000000000000000000000000000000000000 ]]
          test "$(git rev-parse HEAD)" = "$HEAD_SHA"
          git cat-file -e "$BASE_SHA^{commit}"
          policy="$RUNNER_TEMP/contract-input-fixture-ci.py"
          if git cat-file -e "$BASE_SHA:tools/contract-input-fixture-ci.py" 2>/dev/null; then
            git show "$BASE_SHA:tools/contract-input-fixture-ci.py" > "$policy"
          else
            test "$(git rev-parse "$HEAD_SHA:tools/contract-input-fixture-ci.py")" = __POLICY_BLOB__
            git show "$HEAD_SHA:tools/contract-input-fixture-ci.py" > "$policy"
          fi
          python3 "$policy" --root "$PWD" --event "$EVENT" --base "$BASE_SHA" --head "$HEAD_SHA" --github-output "$GITHUB_OUTPUT"

  input-fixtures:
    name: synthetic contract input fixtures
    needs: input_scope
    if: needs.input_scope.outputs.mode == 'fixture-only'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          persist-credentials: false
      - name: Read the fixed public comparator
        uses: actions/checkout@v4
        with:
          repository: roccho-org/ops
          ref: 5eb98c82417b399978c1e38aebab5e3fb39752d4
          path: _fixture-public-ops
          fetch-depth: 0
          persist-credentials: false
      - name: Run synthetic input and routing proofs
        env:
          CONTRACT_INPUT_RUNTIME_ROOT: ${{ github.workspace }}/_fixture-public-ops
          PYTHONDONTWRITEBYTECODE: '1'
        run: |
          set -euo pipefail
          python3 -m unittest discover -s tools/contract-modeling/tests -p test_contract_input.py -v
          python3 -m unittest discover -s tools/contract-modeling/tests -p test_contract_input_scope.py -v
          (cd _fixture-public-ops && python3 -m unittest discover -s packages/contract-diff/tests -p 'test_*.py' -v)
          echo '{"authority":false,"releaseEligible":false,"releaseEligibilityEvaluated":false,"realEvidenceNotEvaluated":true,"grade":"fixture"}'
          echo 'Synthetic fixture proof only. Legacy gate was not evaluated; release eligibility and adoption are not established.' >> "$GITHUB_STEP_SUMMARY"

""".replace("__POLICY_BLOB__", policy_blob) + END


def replace_once(text, before, after):
    need(text.count(before) == 1, "workflow-wiring-anchor")
    return text.replace(before, after, 1)


def wire_workflow(legacy, policy_blob):
    need(BEGIN not in legacy and END not in legacy, "workflow-already-routed")
    text = replace_once(legacy, "jobs:\n", "jobs:\n" + public_jobs(policy_blob))
    for before, after in ROUTES:
        text = replace_once(text, before, after)
    anchor = "      - name: Run Python, contract-modeling, and gov release regression\n"
    text = replace_once(text, anchor, RUNTIME + anchor)
    text = replace_once(text, anchor + "        env:\n", anchor + "        env:\n          CONTRACT_INPUT_RUNTIME_ROOT: ${{ github.workspace }}/_fixture-public-ops\n")
    return text


def legacy_workflow(text, policy_blob):
    if BEGIN not in text:
        need(END not in text, "workflow-routing-markers")
        return text
    need(text.count(BEGIN) == 1 and text.count(END) == 1, "workflow-routing-markers")
    expected = public_jobs(policy_blob)
    need(expected in text, "workflow-public-jobs-differ")
    text = text.replace(expected, "", 1)
    for before, after in ROUTES:
        text = replace_once(text, after, before)
    text = replace_once(text, RUNTIME, "")
    text = replace_once(text, "          CONTRACT_INPUT_RUNTIME_ROOT: ${{ github.workspace }}/_fixture-public-ops\n", "")
    return text


def wire_intent(raw):
    rows = raw.splitlines(keepends=True)
    matched = 0
    for i, line in enumerate(rows):
        value = json.loads(line)
        if value.get("path") == WORKFLOW:
            matched += 1
            old = value["entrypoint"]
            need(not old.endswith(SUFFIX), "intent-already-routed")
            # Preserve all other row bytes, rather than rewriting declarations.
            rows[i] = line.replace(json.dumps(old, ensure_ascii=False), json.dumps(old + SUFFIX, ensure_ascii=False), 1)
    need(matched == 1, "intent-primary-count")
    return "".join(rows)


def classify(root, event, base, head):
    need(event in {"pull_request", "push", "workflow_dispatch"}, "scope-event-unknown")
    for revision in (base, head):
        need(isinstance(revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", revision))
             and revision != "0" * 40, "scope-exact-revision")
        need(git(root, "cat-file", "-t", revision).strip() == b"commit", "scope-commit-required")
    git(root, "merge-base", "--is-ancestor", base, head)
    if event == "workflow_dispatch":
        return {"mode": "real", "event": event, "base": base, "head": head}
    changes = git(root, "diff", "--name-status", "--no-renames", base, head).decode().splitlines()
    need(bool(changes), "scope-empty-delta")
    changed = []
    for line in changes:
        status, path = line.split("\t")
        need(status in {"A", "M"}, "scope-deletion-or-unknown-change")
        entry = git(root, "ls-tree", head, "--", path).decode()
        need(entry.startswith(("100644 blob ", "100755 blob ")), "scope-nonregular-file")
        changed.append(path)
    candidate_policy = read(root, head, POLICY)
    base_entry = git(root, "ls-tree", base, "--", POLICY)
    base_policy = read(root, base, POLICY) if base_entry else None
    if base_policy is not None:
        need(base_policy == candidate_policy, "scope-policy-change-needs-review")
    allowed = FIXTURES | {POLICY, WORKFLOW, INTENT}
    if not set(changed) <= allowed:
        return {"mode": "real", "event": event, "base": base, "head": head, "changed": changed}
    for path in changed:
        need(git(root, "ls-tree", head, "--", path).startswith(b"100644 blob "), "scope-fixture-mode")
    before, after = read(root, base, WORKFLOW).decode(), read(root, head, WORKFLOW).decode()
    old_blob = blob(base_policy) if base_policy is not None else blob(candidate_policy)
    legacy = legacy_workflow(before, old_blob)
    need(after == wire_workflow(legacy, blob(candidate_policy)), "scope-workflow-diff-needs-review")
    before_intent, after_intent = read(root, base, INTENT).decode(), read(root, head, INTENT).decode()
    expected_intent = before_intent if SUFFIX in before_intent else wire_intent(before_intent)
    need(after_intent == expected_intent, "scope-intent-diff-needs-review")
    return {"mode": "fixture-only", "event": event, "base": base, "head": head,
            "changed": changed, "releaseEligibilityEvaluated": False, "releaseEligible": False,
            "realEvidenceNotEvaluated": True, "authority": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    result = classify(args.root, args.event, args.base, args.head)
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write("mode=" + result["mode"] + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

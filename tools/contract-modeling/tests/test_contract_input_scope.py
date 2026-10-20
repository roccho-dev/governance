"""Public synthetic routing proof; no private source or provider access."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "tools/contract-input-fixture-ci.py"
GIT = os.environ.get("CONTRACT_INPUT_GIT", shutil.which("git") or "git")
OWNED = ROOT / ".artifacts/fixture-scope-tests"
WORKFLOW_BLOB = "020cc9704beda23f313ee1dd39d6debec979b5c4"
INTENT_BLOB = "f27da44e1a3283e2ca93865688f577ef683cb48a"
POLICY_BLOB = "b8543b41e29e24f51905b35fc570087ed5354a41"
spec = importlib.util.spec_from_file_location("fixture_scope", POLICY)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def git(root, *args):
    result = subprocess.run([GIT, "--no-optional-locks", "-c", "core.autocrlf=false",
        "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.invalid", "-C", str(root), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return result.stdout


def commit(root, files):
    for path, body in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body.encode() if isinstance(body, str) else body)
    git(root, "add", "--", *files)
    git(root, "commit", "--quiet", "--allow-empty", "-m", "Synthetic routing generation")
    return git(root, "rev-parse", "HEAD").decode().strip()


def unwire_intent(raw):
    rows = raw.splitlines(keepends=True)
    matched = 0
    for index, line in enumerate(rows):
        value = json.loads(line)
        if value.get("path") != scope.WORKFLOW:
            continue
        matched += 1
        entrypoint = value["entrypoint"]
        if not entrypoint.endswith(scope.SUFFIX):
            raise AssertionError("current intent is not the exact routed projection")
        legacy = entrypoint[:-len(scope.SUFFIX)]
        rows[index] = line.replace(
            json.dumps(entrypoint, ensure_ascii=False),
            json.dumps(legacy, ensure_ascii=False),
            1,
        )
    if matched != 1:
        raise AssertionError("current intent must contain exactly one routed workflow row")
    return "".join(rows)


class FixtureScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fixed current public Gov objects are present in every shallow checkout.
        # Their pinned Git blobs prevent a candidate-generated workflow/intent oracle.
        actual = {
            "workflow": git(ROOT, "rev-parse", "HEAD:" + scope.WORKFLOW).decode().strip(),
            "intent": git(ROOT, "rev-parse", "HEAD:" + scope.INTENT).decode().strip(),
            "policy": git(ROOT, "rev-parse", "HEAD:" + scope.POLICY).decode().strip(),
        }
        expected = {"workflow": WORKFLOW_BLOB, "intent": INTENT_BLOB, "policy": POLICY_BLOB}
        if actual != expected:
            raise AssertionError("fixed public routing source drift:" + json.dumps(actual, sort_keys=True))

        cls.policy = POLICY.read_bytes()
        current_workflow = (ROOT / scope.WORKFLOW).read_text(encoding="utf-8")
        current_intent = (ROOT / scope.INTENT).read_text(encoding="utf-8")
        cls.original = scope.legacy_workflow(current_workflow, scope.blob(cls.policy))
        cls.intent = unwire_intent(current_intent)
        cls.wired = scope.wire_workflow(cls.original, scope.blob(cls.policy))
        cls.routed_intent = scope.wire_intent(cls.intent)
        if cls.wired != current_workflow or cls.routed_intent != current_intent:
            raise AssertionError("current public routing projection is not reversible")

    def setUp(self):
        OWNED.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=OWNED)
        self.root = Path(self.temp.name).resolve()
        git(self.root, "init", "--quiet")
        self.base = commit(self.root, {scope.WORKFLOW: self.original,
            scope.INTENT: self.intent, "tools/real-source.py": "value = 1\n"})
        self.head = commit(self.root, {scope.POLICY: self.policy,
            scope.WORKFLOW: self.wired, scope.INTENT: self.routed_intent,
            "tools/contract_input.py": "# Synthetic-only scope file\n"})

    def tearDown(self):
        # Only disposable fixture repositories inside this owned worktree.
        if self.root.parent != OWNED.resolve() or not self.root.is_relative_to(ROOT.resolve()):
            raise AssertionError("fixture cleanup escaped owned root")
        self.temp.cleanup()

    def classify(self, event="pull_request", base=None, head=None):
        return scope.classify(self.root, event, base or self.base, head or self.head)

    def rejected(self, *, head=None, base=None, event="pull_request"):
        with self.assertRaises(scope.ScopeError):
            self.classify(event, base, head)

    def test_bootstrap_pr_and_push_exact_scope(self):
        for event in ("pull_request", "push"):
            result = self.classify(event)
            self.assertEqual(result["mode"], "fixture-only")
            self.assertFalse(result["releaseEligible"])
            self.assertFalse(result["releaseEligibilityEvaluated"])
            self.assertTrue(result["realEvidenceNotEvaluated"])
            self.assertFalse(result["authority"])

    def test_fixed_base_policy_then_fixture_only_change(self):
        newer = commit(self.root, {"tools/contract_input.py": "# Next synthetic generation\n"})
        self.assertEqual(self.classify(base=self.head, head=newer)["mode"], "fixture-only")

    def test_real_or_mixed_source_delta_preserves_real_route(self):
        mixed = commit(self.root, {"tools/real-source.py": "value = 2\n"})
        self.assertEqual(self.classify(head=mixed)["mode"], "real")
        self.assertEqual(self.classify(base=self.head, head=mixed)["mode"], "real")

    def test_dispatch_is_always_real(self):
        self.assertEqual(self.classify("workflow_dispatch")["mode"], "real")

    def test_legacy_workflow_step_edit_cannot_use_fixture_route(self):
        changed = commit(self.root, {scope.WORKFLOW:
            self.wired.replace("test \"$OUTCOME\" = success", "true", 1)})
        self.rejected(head=changed)

    def test_intent_edit_cannot_use_fixture_route(self):
        changed = commit(self.root, {scope.INTENT: self.routed_intent.replace(
            '"all_repositories_enforced":false', '"all_repositories_enforced":true', 1)})
        # Verify the counterexample actually changes a declaration.
        self.assertNotEqual(scope.read(self.root, changed, scope.INTENT), self.routed_intent.encode())
        self.rejected(head=changed)

    def test_policy_change_after_bootstrap_fails_closed(self):
        changed = commit(self.root, {scope.POLICY: self.policy + b"\n# Unreviewed policy\n"})
        self.rejected(base=self.head, head=changed)

    def test_missing_zero_expressions_unknown_event_and_empty_fail(self):
        self.rejected(base="0" * 40)
        self.rejected(base="f" * 40)
        self.rejected(base="HEAD~1")
        self.rejected(event="unknown")
        self.rejected(base=self.head)

    def test_deleted_file_and_renamed_file_fail_closed(self):
        git(self.root, "rm", "--", "tools/contract_input.py")
        git(self.root, "commit", "--quiet", "-m", "Synthetic deletion")
        self.rejected(base=self.head, head=git(self.root, "rev-parse", "HEAD").decode().strip())
        git(self.root, "reset", "--hard", self.head)
        git(self.root, "mv", "tools/contract_input.py", "tools/moved.py")
        git(self.root, "commit", "--quiet", "-m", "Synthetic rename")
        self.rejected(base=self.head, head=git(self.root, "rev-parse", "HEAD").decode().strip())

    def test_fixed_revisions_survive_ref_movement(self):
        before = self.classify()
        commit(self.root, {"tools/real-source.py": "value = 99\n"})
        self.assertEqual(self.classify(), before)

    def test_real_executable_changes_not_misclassified_as_fixture(self):
        git(self.root, "update-index", "--chmod=+x", "tools/real-source.py")
        git(self.root, "commit", "--quiet", "-m", "Real executable mode")
        newer = git(self.root, "rev-parse", "HEAD").decode().strip()
        self.assertEqual(self.classify(head=newer)["mode"], "real")

    def test_fixture_executable_mode_and_symlink_rejected(self):
        git(self.root, "update-index", "--chmod=+x", "tools/contract_input.py")
        git(self.root, "commit", "--quiet", "-m", "Fixture executable mode")
        self.rejected(head=git(self.root, "rev-parse", "HEAD").decode().strip())
        git(self.root, "reset", "--hard", self.head)
        # Index-only synthetic symlink avoids Windows symlink privileges.
        obj = git(self.root, "hash-object", "-w", "--", "tools/contract_input.py").decode().strip()
        git(self.root, "update-index", "--cacheinfo", "120000," + obj + ",tools/contract_input.py")
        git(self.root, "commit", "--quiet", "-m", "Fixture symlink mode")
        self.rejected(head=git(self.root, "rev-parse", "HEAD").decode().strip())

    def test_merge_parents_use_complete_delta(self):
        git(self.root, "checkout", "--quiet", "--detach", self.base)
        side = commit(self.root, {"tools/contract-modeling/CONTRACT_INPUT_FIXTURES.md": "Synthetic only\n"})
        git(self.root, "checkout", "--quiet", "--detach", self.head)
        git(self.root, "merge", "--quiet", "--no-ff", side, "-m", "Synthetic merge")
        merged = git(self.root, "rev-parse", "HEAD").decode().strip()
        self.assertEqual(self.classify(head=merged)["mode"], "fixture-only")
        # A real source hidden in another parent is still part of the full delta.
        git(self.root, "checkout", "--quiet", "--detach", self.base)
        real = commit(self.root, {"tools/real-source.py": "value = 3\n"})
        git(self.root, "checkout", "--quiet", "--detach", merged)
        git(self.root, "merge", "--quiet", "--no-ff", real, "-m", "Mixed merge")
        self.assertEqual(self.classify(head=git(self.root, "rev-parse", "HEAD").decode().strip())["mode"], "real")

    def test_unrelated_base_is_not_assumed_safe(self):
        git(self.root, "checkout", "--quiet", "--orphan", "unrelated")
        unrelated = commit(self.root, {"unrelated.txt": "Synthetic unrelated root\n"})
        self.rejected(base=unrelated)

    def test_error_produces_no_mode_output(self):
        output = self.root / "job-output"
        proc = subprocess.run([sys.executable, str(POLICY), "--root", str(self.root),
            "--event", "push", "--base", "f" * 40, "--head", self.head,
            "--github-output", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(output.exists())

    def test_projection_preserves_legacy_and_has_no_private_fixture_steps(self):
        self.assertEqual(scope.legacy_workflow(self.wired, scope.blob(self.policy)), self.original)
        # Independent statements about generated jobs, rather than round-trip alone.
        public = scope.public_jobs(scope.blob(self.policy))
        for forbidden in ("secrets", "create-github-app-token", "upload-artifact", "download-artifact", "roccho-dev/adrs"):
            self.assertNotIn(forbidden, public)
        self.assertIn("repository: roccho-org/ops", public)
        self.assertIn("ref: 5eb98c82417b399978c1e38aebab5e3fb39752d4", public)
        self.assertIn('git show "$BASE_SHA:tools/contract-input-fixture-ci.py"', public)
        self.assertIn('test "$(git rev-parse "$HEAD_SHA:tools/contract-input-fixture-ci.py")" = ' + scope.blob(self.policy), public)
        self.assertIn("name: ${{ needs.input_scope.outputs.mode == 'real' && 'gate' || 'real-data gate not evaluated' }}", self.wired)
        for job in ("capture", "live-consumers", "control-plane-observation"):
            self.assertIn("  " + job + ":\n    needs: input_scope\n    if: needs.input_scope.outputs.mode == 'real'", self.wired)
        self.assertNotIn("releaseEligible\":true", public)
        # The intent delta is explanatory only; every other field remains exact.
        before = [json.loads(line) for line in self.intent.splitlines()]
        after = [json.loads(line) for line in self.routed_intent.splitlines()]
        for old, new in zip(before, after, strict=True):
            expected = dict(old)
            if old.get("path") == scope.WORKFLOW:
                expected["entrypoint"] += scope.SUFFIX
            self.assertEqual(new, expected)


if __name__ == "__main__":
    unittest.main()

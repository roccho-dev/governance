#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTOR = ROOT / "tools" / "project-readme-govlib.py"
SLOTS = ["Purpose", "Authority boundary", "Inputs", "Outputs / artifacts", "Checks", "Ownership / handoff"]
DIGEST = "sha256:fixture-readme-boundary"
VERSION = "govlib-readme-artifact.v1"


def put(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bundle(**extra: object) -> dict:
    value = {
        "kind": "adrs.acceptedReadmeArtifactBoundaryBundle.v1",
        "uri": "doc://adrs/readme-artifact-library-boundaries",
        "status": "Accepted",
        "source_digest": DIGEST,
        "policy_facts": {"required_slots": SLOTS},
    }
    value.update(extra)
    return value


def manifest(**extra: object) -> dict:
    value = {
        "kind": "repo.readmeArtifactConsumerManifest.v1",
        "repo": "roccho-dev/fixture",
        "profile": "library",
        "severity": "blocking",
        "capsule_digest": DIGEST,
        "projector_version": VERSION,
    }
    value.update(extra)
    return value


def run(case: Path, b: dict, m: dict) -> subprocess.CompletedProcess[str]:
    put(case / "accepted-adr-bundle.json", b)
    put(case / "repo-manifest.json", m)
    return subprocess.run(
        [sys.executable, str(PROJECTOR), "--accepted-bundle", str(case / "accepted-adr-bundle.json"), "--manifest", str(case / "repo-manifest.json"), "--out", str(case / "out")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ok = root / "ok"
        res = run(ok, bundle(), manifest())
        assert res.returncode == 0, res.stderr
        actual = {p.name for p in (ok / "out").iterdir()}
        assert {"readme.policy.capsule.json", "repo.explain.model.json", "diagnostics.jsonl", "source-closure.jsonl"}.issubset(actual), actual
        assert "README.md" not in actual and "rendered.md" not in actual and "artifact.zip" not in actual, actual
        capsule = json.loads((ok / "out" / "readme.policy.capsule.json").read_text(encoding="utf-8"))
        assert capsule["kind"] == "governance.readmePolicyCapsule.v1"
        assert capsule["required_slots"] == SLOTS
        cases = [
            (bundle(status="Proposed"), manifest()),
            (bundle(raw_rows=[{"kind": "row"}]), manifest()),
            (bundle(unknown_policy_inputs=["x"]), manifest()),
            (bundle(), manifest(capsule_digest="sha256:stale")),
        ]
        missing = bundle()
        missing["policy_facts"] = {"required_slots": SLOTS[:-1]}
        cases.append((missing, manifest()))
        for idx, (b, m) in enumerate(cases):
            bad = root / f"bad-{idx}"
            res = run(bad, b, m)
            assert res.returncode != 0, f"bad case {idx} passed"
    print(json.dumps({"status": "readme-govlib-contract-pass"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

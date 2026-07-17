#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
PYTHON=${PYTHON:-python3}
NIX_BIN=${NIX_BIN:-nix}
EXPECTED_LEDGER=723ac930fbd5e1a85de8fc552e49d8477568c8da1c7acd58e0db34b29490338b
EXPECTED_SCHEMA=6d48c6cf59a84a7940fc8aac4b193f6e9d4f267727e61c50286ea3155f3862cb
EXPECTED_TREE=fbae94090ad8ee0e08f64b268d2efa6b8b34121d099d978d3c94deed6654e361
EXPECTED_SEMANTIC=e7df1eceb56e00ab06f2e9d887aa74857b704adbd934f96c9408c1a37ca61b32

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export PROOF_PYTHON="$PYTHON"
export NIX_BIN

rm -rf "$ROOT/out"
mkdir -p "$ROOT/out/transports" "$ROOT/out/sources" "$ROOT/out/evaluations"

"$PYTHON" -m adapters.github_issue \
  --repository roccho-dev/adrs \
  --issue 231 \
  --trusted-actor roccho-dev \
  --expected-event-count 9 \
  --expected-row-count 52 \
  --expected-ledger-sha256 "$EXPECTED_LEDGER" \
  --output "$ROOT/out/transports/live"

test "$(sha256sum "$ROOT/schema.json" | awk '{print $1}')" = "$EXPECTED_SCHEMA"

"$PYTHON" "$ROOT/tests/generate_transport_fixtures.py" \
  --ledger "$ROOT/out/transports/live/ledger.jsonl" \
  --output "$ROOT/out/generated"

"$PYTHON" -m adapters.github_pages \
  --pages "$ROOT/out/generated/github-a-previous" \
  --repository fixture/a --issue 1 \
  --trusted-actor fixture-writer-a \
  --output "$ROOT/out/transports/synthetic-a-previous"

"$PYTHON" -m adapters.github_pages \
  --pages "$ROOT/out/generated/github-a" \
  --repository fixture/a --issue 1 \
  --trusted-actor fixture-writer-a \
  --previous-receipt "$ROOT/out/transports/synthetic-a-previous/transport-receipt.json" \
  --output "$ROOT/out/transports/synthetic-a"

"$PYTHON" -m adapters.github_pages \
  --pages "$ROOT/out/generated/github-b" \
  --repository fixture/b --issue 2 \
  --trusted-actor fixture-writer-b \
  --output "$ROOT/out/transports/synthetic-b"

"$PYTHON" -m adapters.file_jsonl \
  --source "$ROOT/out/generated/ledger/variant.jsonl" \
  --output "$ROOT/out/transports/file"

for candidate in synthetic-a synthetic-b file; do
  cmp "$ROOT/out/transports/live/ledger.jsonl" "$ROOT/out/transports/$candidate/ledger.jsonl"
done

"$PYTHON" -m adapters.local_tree \
  --source-root "$ROOT" --include fixtures/code \
  --output "$ROOT/out/sources/local"

test "$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["tree_sha256"])' "$ROOT/out/sources/local/tree.json")" = "$EXPECTED_TREE"

mkdir -p "$ROOT/out/git-origin/fixtures"
cp -a "$ROOT/fixtures/code" "$ROOT/out/git-origin/fixtures/code"
(
  cd "$ROOT/out/git-origin"
  git init -q
  git config user.name 'Proof Bot'
  git config user.email 'proof@example.invalid'
  git add fixtures/code
  GIT_AUTHOR_DATE='2026-01-01T00:00:00Z' \
  GIT_COMMITTER_DATE='2026-01-01T00:00:00Z' \
    git commit -q -m fixture
)
REVISION=$(git -C "$ROOT/out/git-origin" rev-parse HEAD)

"$PYTHON" -m adapters.git_tree \
  --locator "$ROOT/out/git-origin" --revision "$REVISION" \
  --include fixtures/code --output "$ROOT/out/sources/git-path"

"$PYTHON" -m adapters.git_tree \
  --locator "file://$ROOT/out/git-origin" --revision "$REVISION" \
  --include fixtures/code --output "$ROOT/out/sources/git-file"

cmp "$ROOT/out/sources/local/tree.json" "$ROOT/out/sources/git-path/tree.json"
cmp "$ROOT/out/sources/local/tree.json" "$ROOT/out/sources/git-file/tree.json"

"$PYTHON" -m engine.pipeline \
  --ledger "$ROOT/out/transports/live/ledger.jsonl" \
  --schema "$ROOT/schema.json" \
  --project-root "$ROOT/out/sources/local/snapshot" \
  --output "$ROOT/out/evaluations/live-local"

"$PYTHON" -m engine.pipeline \
  --ledger "$ROOT/out/transports/synthetic-b/ledger.jsonl" \
  --schema "$ROOT/schema.json" \
  --project-root "$ROOT/out/sources/git-path/snapshot" \
  --output "$ROOT/out/evaluations/synthetic-b-git-path"

CI=true UNRELATED_ENV=ignored PYTHON="$PYTHON" "$ROOT/ci/run-evaluate.sh" \
  --ledger "$ROOT/out/transports/file/ledger.jsonl" \
  --schema "$ROOT/schema.json" \
  --project-root "$ROOT/out/sources/git-file/snapshot" \
  --output "$ROOT/out/evaluations/file-git-file"

for candidate in synthetic-b-git-path file-git-file; do
  cmp "$ROOT/out/evaluations/live-local/semantic-packet.json" \
      "$ROOT/out/evaluations/$candidate/semantic-packet.json"
done

test "$(sha256sum "$ROOT/out/evaluations/live-local/semantic-packet.json" | awk '{print $1}')" = "$EXPECTED_SEMANTIC"

"$PYTHON" -m unittest discover -s "$ROOT/tests" -p 'test_proof.py' -v \
  > "$ROOT/out/tests.log" 2>&1

materialize() {
  local packet=$1
  local materializer
  materializer=$(realpath "$ROOT/nix/materialize.nix")
  packet=$(realpath "$packet")
  "$NIX_BIN" eval --offline --impure --raw --expr \
    "(import $materializer { packet = $packet; })"
}

NIX_LIVE=$(materialize "$ROOT/out/evaluations/live-local/semantic-packet.json")
NIX_SYNTHETIC=$(materialize "$ROOT/out/evaluations/synthetic-b-git-path/semantic-packet.json")
NIX_FILE=$(materialize "$ROOT/out/evaluations/file-git-file/semantic-packet.json")
[[ "$NIX_LIVE" == "$NIX_SYNTHETIC" && "$NIX_LIVE" == "$NIX_FILE" ]]
cmp "$ROOT/out/evaluations/live-local/semantic-packet.json" "$NIX_LIVE"
cp "$NIX_LIVE" "$ROOT/out/nix-output.json"

"$PYTHON" - "$ROOT" "$NIX_BIN" "$NIX_LIVE" "$REVISION" <<'PY'
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
nix_bin = sys.argv[2]
nix_path = Path(sys.argv[3])
revision = sys.argv[4]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


log = (root / "out/tests.log").read_text(encoding="utf-8")
match = re.search(r"Ran (\d+) tests", log)
if not match or "OK" not in log:
    raise SystemExit("test suite did not pass")

packet = root / "out/evaluations/live-local/semantic-packet.json"
ledger = root / "out/transports/live/ledger.jsonl"
tree = load(root / "out/sources/local/tree.json")
live_transport = load(root / "out/transports/live/transport-receipt.json")
receipt = {
    "kind": "provider-detached-live-adrs-proof-receipt.v1",
    "status": "pass",
    "authority": False,
    "scope": {
        "live_remote_api": True,
        "live_ci_service": os.environ.get("GITHUB_ACTIONS") == "true",
        "live_ssh_transport": False,
        "production_write_boundary": False,
    },
    "source": {
        "provider": "transport-only",
        "selected_event_count": live_transport["selected_event_count"],
        "row_count": live_transport["row_count"],
    },
    "claims": {
        "transport_metadata_separated": True,
        "canonical_ledger_transport_invariant": True,
        "canonical_tree_locator_invariant": True,
        "semantic_packet_transport_invariant": True,
        "nix_store_path_transport_invariant": True,
        "engine_has_no_provider_specific_vocabulary": True,
        "engine_imports_no_transport_adapter_or_network_client": True,
        "schema_closed": True,
        "reducer_order_invariant": True,
        "append_continuity_fail_closed_for_fixture_transport": True,
        "purpose_structure_closed": True,
        "positive_negative_code_fixtures_match": True,
        "semantic_mutation_changes_output": True,
        "transport_mutation_does_not_change_output": True,
        "direct_and_ci_wrapper_outputs_equal": True,
        "causal_support_verified": False,
        "top_purpose_achieved": False,
        "production_authority": False,
        "all_repositories_enforced": False,
    },
    "versions": {
        "python": sys.version.split()[0],
        "ast_grep_py": importlib.metadata.version("ast-grep-py"),
        "jsonschema": importlib.metadata.version("jsonschema"),
        "go": subprocess.run(["go", "version"], text=True, capture_output=True, check=True).stdout.strip(),
        "git": subprocess.run(["git", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "nix": subprocess.run([nix_bin, "--version"], text=True, capture_output=True, check=True).stdout.strip(),
    },
    "tests": {"count": int(match.group(1)), "log_sha256": digest(root / "out/tests.log")},
    "digests": {
        "schema_sha256": digest(root / "schema.json"),
        "canonical_ledger_sha256": digest(ledger),
        "canonical_tree_sha256": tree["tree_sha256"],
        "semantic_packet_sha256": digest(packet),
        "nix_output_sha256": digest(nix_path),
        "live_transport_receipt_sha256": digest(root / "out/transports/live/transport-receipt.json"),
    },
    "git_fixture_revision": revision,
    "nix_store_path": str(nix_path),
}
(root / "out/proof-receipt.json").write_text(
    json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY

printf 'proof=pass\ntests=%s\nledger=%s\ntree=%s\nsemantic=%s\nnix=%s\n' \
  "$(sed -n 's/^Ran \([0-9][0-9]*\) tests.*/\1/p' "$ROOT/out/tests.log")" \
  "$(sha256sum "$ROOT/out/transports/live/ledger.jsonl" | awk '{print $1}')" \
  "$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["tree_sha256"])' "$ROOT/out/sources/local/tree.json")" \
  "$(sha256sum "$ROOT/out/evaluations/live-local/semantic-packet.json" | awk '{print $1}')" \
  "$NIX_LIVE"

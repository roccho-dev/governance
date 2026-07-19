#!/usr/bin/env bash
set -euo pipefail

python3 -m unittest discover -s tools/gov_release/tests -p 'test_*.py'
python3 tools/check-gov-release-integration.py selftest --json
python3 tools/check-gov-release-integration.py canary --json

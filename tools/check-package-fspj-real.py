from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / 'tools' / 'build-package-responsibility-closure.py'
ADRS = ROOT / 'docs' / 'fspj-125' / 'real' / 'adrs'
REPO = ROOT / 'docs' / 'fspj-125' / 'real' / 'repo'
RESP = ROOT / 'docs' / 'fspj-125' / 'real' / 'responses'


def load_compiler():
    spec = importlib.util.spec_from_file_location('compiler', COMPILER)
    if spec is None or spec.loader is None:
        raise SystemExit('compiler-load-failed')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    compiler = load_compiler()
    result = compiler.compile_all(ADRS, REPO, RESP)
    blocking = [row for row in result['work_orders'] if row.get('blocking_level') != 'warning']
    if blocking:
        raise SystemExit('fspj-real:blocking-drift')
    if any(row.get('authority') is True for row in result['responses']):
        raise SystemExit('fspj-real:authority-collision')
    print('fspj-real:pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

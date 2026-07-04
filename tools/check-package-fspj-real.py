from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    for path in [
        root / 'docs/fspj-125/real/adrs/obligations.jsonl',
        root / 'docs/fspj-125/real/repo/build/packages.jsonl',
        root / 'docs/fspj-125/real/responses/responses.jsonl',
    ]:
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f'missing:{path}')
    print('fspj-real:pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

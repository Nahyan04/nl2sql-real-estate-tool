"""Verify and profile a supplied ADREC snapshot without database access."""
import argparse
import json
from pathlib import Path

from genlib.source_contract import ContractError, profile_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.snapshot.resolve() == args.output.resolve() or args.snapshot.resolve() in args.output.resolve().parents:
        parser.error('Output must be outside the immutable incoming snapshot')
    try:
        report = profile_snapshot(args.snapshot)
    except ContractError as exc:
        parser.exit(1, f'Source check failed: {exc}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + '\n')
    print(f"Verified {len(report['sources'])} source files; report: {args.output}")
    print(f"Advisory review items: {len(report['review_items'])} (see review_items in the report)")
    for item in report['review_items']:
        source = f" [{item['source_file']}]" if 'source_file' in item else ''
        print(f"  {item['code']}{source}: {item['count']}")


if __name__ == '__main__':
    main()

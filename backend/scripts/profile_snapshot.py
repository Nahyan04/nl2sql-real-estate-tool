"""Verify and profile a supplied ADREC snapshot without database access."""
import argparse
import json
from pathlib import Path

from genlib.source_contract import profile_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.snapshot.resolve() == args.output.resolve() or args.snapshot.resolve() in args.output.resolve().parents:
        parser.error('Output must be outside the immutable incoming snapshot')
    report = profile_snapshot(args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + '\n')
    print(f"Verified {len(report['sources'])} sources; report: {args.output}")


if __name__ == '__main__':
    main()

"""Import verified native exports into an explicitly named staging database."""
import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from genlib.snapshot_import import import_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--staging-url-env', required=True, help='Environment variable containing staging credentials; never pass credentials as arguments')
    parser.add_argument('--expected-database', required=True)
    args = parser.parse_args()
    url = os.environ.get(args.staging_url_env)
    if not url:
        parser.error('Staging URL environment variable is not set')
    engine = create_engine(url)
    try:
        print(json.dumps(import_snapshot(engine, args.snapshot, args.expected_database)))
    except Exception as exc:
        # Driver messages can contain connection details; diagnostics stay bounded.
        parser.exit(1, f'Staging import failed ({type(exc).__name__}); transaction rolled back.\n')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

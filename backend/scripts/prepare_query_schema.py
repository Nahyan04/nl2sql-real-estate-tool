"""Prepare query views on staging; never changes application configuration."""
import argparse
import os
from sqlalchemy import create_engine
from genlib.query_schema import prepare_query_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging-url-env', required=True)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--snapshot-id', required=True)
    parser.add_argument('--grant-readonly', action='store_true', help='Restrict an existing dedicated nl2sql_readonly role to product views')
    args = parser.parse_args()
    url = os.environ.get(args.staging_url_env)
    if not url:
        parser.error('Staging URL environment variable is not set')
    engine = create_engine(url)
    try:
        prepare_query_schema(engine, args.expected_database, args.snapshot_id, restrict_readonly=args.grant_readonly)
        print('Source-backed query schema prepared; application configuration unchanged')
    except Exception as exc:
        parser.exit(1, f'Query schema preparation failed ({type(exc).__name__}); rolled back.\n')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

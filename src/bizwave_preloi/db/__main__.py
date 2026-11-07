"""python -m bizwave_preloi.db upgrade|downgrade|current [--url URL] [REVISION | --revision REVISION]

    python -m bizwave_preloi.db downgrade --url sqlite:///C:/path/bizwave.db base     # remove everything

Without --url the database in the data folder is used (settings().database_url).
"""
from __future__ import annotations

import argparse
import sys

from .migrate import current_revision, downgrade, upgrade


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bizwave_preloi.db",
                                     description="Create, update or inspect the BizWave database schema.")
    parser.add_argument("action", choices=["upgrade", "downgrade", "current"])
    parser.add_argument("--url", default=None, help="database URL (default: the data folder's database)")
    parser.add_argument("target", nargs="?", default=None,
                        help='target revision (upgrade default "head", downgrade default "-1", "base" = empty)')
    parser.add_argument("--revision", default=None, help="the same as the positional target")
    args = parser.parse_args(argv)
    if args.target and args.revision and args.target != args.revision:
        parser.error(f"two different revisions given: {args.target!r} and --revision {args.revision!r}")
    revision = args.target or args.revision
    if args.action == "upgrade":
        upgrade(args.url, revision or "head")
    elif args.action == "downgrade":
        downgrade(args.url, revision or "-1")
    print(current_revision(args.url) or "(empty database)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

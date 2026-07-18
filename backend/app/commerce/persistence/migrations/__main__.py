"""CLI for the independent Commerce Alembic branch."""

from __future__ import annotations

import argparse

from app.commerce.persistence.migrations.runner import (
    downgrade_commerce_schema,
    upgrade_commerce_schema,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("upgrade", "downgrade"))
    parser.add_argument("--url", required=True, help="SQLAlchemy async database URL")
    parser.add_argument("--revision")
    args = parser.parse_args()

    if args.operation == "upgrade":
        upgrade_commerce_schema(args.url, args.revision or "head")
    else:
        downgrade_commerce_schema(args.url, args.revision or "base")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

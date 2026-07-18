#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.validators.core import validate_fixture_collection  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate OpenSKU artifact fixtures.")
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--expect-fail", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    fixtures = args.fixtures
    if not fixtures.is_absolute():
        fixtures = REPO_ROOT / fixtures
    result = validate_fixture_collection(fixtures)
    print(f"fixtures={fixtures}")
    print(f"bundle_count={result.bundle_count}")
    print(f"passed_count={result.passed_count}")
    print(f"failed_count={result.failed_count}")
    for bundle_result in result.results:
        status = "PASS" if bundle_result.ok else "FAIL"
        print(f"{status} {bundle_result.bundle_path.name} artifacts={bundle_result.artifact_count}")
        for error in bundle_result.errors:
            print(f"  - {error}")

    if args.expect_fail:
        if result.bundle_count >= 10 and result.failed_count >= 10:
            print("EXPECTED_FAILURES_CAUGHT")
            return 0
        print("EXPECTED_FAILURES_NOT_CAUGHT")
        return 1

    if result.bundle_count >= 10 and result.failed_count == 0:
        print("VALIDATION PASSED")
        return 0
    print("VALIDATION FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


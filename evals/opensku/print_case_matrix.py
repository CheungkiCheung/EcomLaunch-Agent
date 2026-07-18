#!/usr/bin/env python3
"""Print a compact OpenSKU-Bench case matrix."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.validate_cases import load_cases  # noqa: E402


STAGE_ORDER = [
    "idea_only",
    "supplier_sample",
    "pre_launch_test",
    "soft_launch",
    "scale_iterate",
]


def main() -> int:
    cases = [case for _, case in load_cases()]
    cases.sort(key=lambda item: (STAGE_ORDER.index(item["stage"]), item["case_id"]))
    print("| Stage | Case | Decision | Sources | Tags |")
    print("|---|---|---|---|---|")
    for case in cases:
        print(
            "| {stage} | {case_id} | {decision} | {sources} | {tags} |".format(
                stage=case["stage"],
                case_id=case["case_id"],
                decision=case["expected_decision"],
                sources=", ".join(case["source_dataset"]),
                tags=", ".join(case["evaluation_tags"]),
            )
        )
    print()
    print(f"total_cases={len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


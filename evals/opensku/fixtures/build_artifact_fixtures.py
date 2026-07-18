#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_ROOT = REPO_ROOT / "evals/opensku/fixtures"
GOLDEN_ROOT = FIXTURES_ROOT / "golden"
BROKEN_ROOT = FIXTURES_ROOT / "broken"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def evidence_ledger(index: int, *, private_metric_broken: bool = False, no_uploaded: bool = False) -> list[dict[str, Any]]:
    items = [
        {
            "id": "EVID-001",
            "evidence_type": "observed_public",
            "source_type": "public_benchmark_fixture",
            "confidence": "high",
            "metric": "review_score",
            "value": 4 + (index % 2),
            "summary": "Public review signal supports VOC analysis.",
            "used_in": ["positioning-brief.md", "listing-pack.md"],
        },
        {
            "id": "EVID-002",
            "evidence_type": "unavailable",
            "source_type": "public_benchmark_fixture",
            "confidence": "high",
            "metric": "GMV",
            "value": None,
            "summary": "GMV is unavailable because no merchant backend data was uploaded.",
            "used_in": ["launch-calendar.csv"],
        },
    ]
    if private_metric_broken:
        items[1]["evidence_type"] = "observed_public"
        items[1]["value"] = "100000"
        items[1]["summary"] = "Broken fixture incorrectly treats public rows as GMV."
    if not no_uploaded:
        items.append(
            {
                "id": "EVID-003",
                "evidence_type": "uploaded_real",
                "source_type": "public_fixture_as_uploaded_simulation",
                "confidence": "medium",
                "metric": "payment_value",
                "value": 29.9 + index,
                "summary": "Uploaded-data simulation row for payment value.",
                "used_in": ["launch-state.json", "promotion-replan.md"],
            }
        )
    return items


def write_bundle(
    bundle_dir: Path,
    index: int,
    *,
    broken_kind: int | None = None,
) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    no_uploaded = broken_kind == 6
    ledger = evidence_ledger(index, private_metric_broken=broken_kind == 3, no_uploaded=no_uploaded)
    if broken_kind == 1:
        write_text(bundle_dir / "evidence-ledger.json", "{not valid json")
    elif broken_kind == 2:
        broken_ledger = evidence_ledger(index)
        del broken_ledger[0]["id"]
        write_json(bundle_dir / "evidence-ledger.json", broken_ledger)
    else:
        write_json(bundle_dir / "evidence-ledger.json", ledger)

    write_text(
        bundle_dir / "launch-war-room.html",
        "<html><body><h1>OpenSKU fixture</h1><p>Evidence EVID-001</p></body></html>\n",
    )
    write_csv(
        bundle_dir / "competitor-table.csv",
        ["competitor", "observed_claim", "evidence_id", "confidence", "limitation"],
        [
            {
                "competitor": f"Fixture competitor {index}",
                "observed_claim": "Review language suggests scent/feel objections.",
                "evidence_id": "EVID-001",
                "confidence": "medium",
                "limitation": "Public fixture, not live competitor telemetry.",
            }
        ],
    )
    write_text(
        bundle_dir / "positioning-brief.md",
        (
            "# Positioning Brief\n\n"
            "Decision: Hold until the next evidence loop is collected.\n\n"
            "Evidence: EVID-001 supports VOC framing.\n\n"
            "Evidence limitations: Public fixture rows are not live merchant telemetry.\n"
        ),
    )

    listing_text = (
        "# Listing Pack\n\n"
        "Claim readiness: ready for VOC-backed copy using EVID-001.\n\n"
        "Exact specs: keep [SUPPORTED_SPEC] placeholders until uploaded sample fields prove exact values.\n"
    )
    if broken_kind == 7:
        listing_text += "\nThis product is FDA approved and 100% safe for everyone.\n"
    write_text(bundle_dir / "listing-pack.md", listing_text)

    content_text = (
        "# Content Pack\n\n"
        "Claim readiness: needs evidence for exact specs; use EVID-001 only for VOC hooks.\n\n"
        "Hook: Solve the most visible review objection before scaling.\n"
    )
    if broken_kind == 8:
        content_text = "# Content Pack\n\nHook: Scale now without a claim readiness label.\n"
    write_text(bundle_dir / "content-pack.md", content_text)

    calendar_fields = [
        "day",
        "objective",
        "experiment",
        "asset",
        "channel",
        "validation_signal_to_collect",
        "decision_rule",
        "owner",
        "expected_output",
    ]
    calendar_row = {
        "day": "1",
        "objective": "Validate VOC-backed positioning",
        "experiment": "Compare claim-safe listing angle",
        "asset": "listing-pack.md",
        "channel": "marketplace listing",
        "validation_signal_to_collect": "Review objection tags from EVID-001",
        "decision_rule": "Continue only if evidence cites supported fields and no private metrics are invented.",
        "owner": "OpenSKU",
        "expected_output": "Evidence-backed next-loop decision",
    }
    if broken_kind == 5:
        calendar_row["decision_rule"] = ""
    if broken_kind == 6:
        calendar_row["validation_signal_to_collect"] = "CTR, CVR, GMV, and ROI from the merchant backend"
    if broken_kind == 4:
        reduced_fields = [field for field in calendar_fields if field != "decision_rule"]
        write_csv(
            bundle_dir / "launch-calendar.csv",
            reduced_fields,
            [{key: value for key, value in calendar_row.items() if key in reduced_fields}],
        )
    else:
        write_csv(bundle_dir / "launch-calendar.csv", calendar_fields, [calendar_row])

    write_json(
        bundle_dir / "launch-state.json",
        {
            "stage": "soft_launch",
            "decision": "Hold",
            "evidence_ids": ["EVID-001", "EVID-003"] if not no_uploaded else ["EVID-001"],
            "limitation": "Fixture only.",
        },
    )

    promotion_text = (
        "# Promotion Replan\n\n"
        "## Observed signal\n"
        "EVID-001 shows a review-language objection.\n\n"
        "## Interpretation\n"
        "The next loop should reduce claim risk and sharpen positioning.\n\n"
        "## Plan change\n"
        "Move the claim-safe angle earlier in the listing.\n\n"
        "## Next test\n"
        "Run a copy test that cites only supported evidence.\n\n"
        "## Stop/continue rule\n"
        "Stop if new evidence remains unavailable; continue if objections decline.\n"
    )
    if broken_kind == 9:
        promotion_text = promotion_text.replace("## Stop/continue rule\nStop if new evidence remains unavailable; continue if objections decline.\n", "")
    write_text(bundle_dir / "promotion-replan.md", promotion_text)

    knowledge = [
        {
            "type": "pitfall",
            "maturity": "draft",
            "source_case_id": f"opensku-softlaunch-{index:03d}",
            "summary": "Do not convert public review evidence into private growth metrics.",
        }
    ]
    if broken_kind == 10:
        knowledge = [
            {
                "type": "unsupported",
                "maturity": "magic",
                "summary": "Broken knowledge delta lacks a valid source id.",
            }
        ]
    write_json(bundle_dir / "knowledge-deltas.json", knowledge)


def reset_generated_dirs() -> None:
    for path in [GOLDEN_ROOT, BROKEN_ROOT]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    reset_generated_dirs()
    for index in range(1, 11):
        write_bundle(GOLDEN_ROOT / f"golden-{index:03d}", index)
        write_bundle(BROKEN_ROOT / f"broken-{index:03d}", index, broken_kind=index)
    print("golden_bundles=10")
    print("broken_bundles=10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


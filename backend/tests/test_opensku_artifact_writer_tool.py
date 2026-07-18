from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from deerflow.tools.builtins.opensku_artifact_writer import write_opensku_artifact_bundle_tool
from deerflow.tools.tools import BUILTIN_TOOLS


REPO_ROOT = Path(__file__).resolve().parents[2]


def _runtime_for_thread_data(*, outputs_path: Path, uploads_path: Path) -> SimpleNamespace:
    workspace = outputs_path.parent / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    uploads_path.mkdir(parents=True, exist_ok=True)
    outputs_path.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        state={
            "thread_data": {
                "workspace_path": str(workspace),
                "uploads_path": str(uploads_path),
                "outputs_path": str(outputs_path),
            }
        },
        context={"thread_id": "thread-opensku-writer"},
        config={"configurable": {"thread_id": "thread-opensku-writer"}},
    )


def test_write_opensku_artifact_bundle_generates_validator_clean_bundle(tmp_path):
    outputs = tmp_path / "user-data" / "outputs"
    uploads = tmp_path / "user-data" / "uploads"
    runtime = _runtime_for_thread_data(outputs_path=outputs, uploads_path=uploads)
    (uploads / "demo-brief.portable-coffee-tumbler.json").write_text(
        (REPO_ROOT / "docs/ecom-launch/demo-brief.portable-coffee-tumbler.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (uploads / "amazon_reviews.jsonl").write_text(
        (REPO_ROOT / "data/opensku/samples/amazon_reviews.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = write_opensku_artifact_bundle_tool.func(
        runtime=runtime,
        case_id="opensku-writer-test-001",
        stage="pre_launch_test",
        decision="Hold",
        product_name="Portable leak-proof coffee tumbler",
        target_platforms="Taobao, Xiaohongshu, Douyin",
        target_customers="office commuters and light outdoor users",
        audience_wedge="office workers who care about leakage, cleaning, odor, and portability",
        core_promise="carry coffee without creating a messy commute",
        key_findings="Fixture evidence supports VOC mining, but it does not prove private ecommerce performance.",
        pain_points="leakage anxiety; cleaning effort; odor retention; portability tradeoffs",
        competitor_notes="Most visible alternatives compete on insulation, lid design, and price-band clarity.",
        listing_angle="Lead with leak-safe commute and easy-clean routine; avoid unsupported exact specs.",
        content_angle="Short videos should show commute scenarios and objection handling, not invented testimonials.",
        next_test="Collect 20 target-user reactions to two claim-safe hooks before scaling spend.",
        promotion_adjustment="Hold paid scale; run creator/sample feedback first.",
        data_limitations="No merchant backend metrics were uploaded; GMV, CTR, CVR, ROI, ad spend, refund rate, and repeat purchase rate are unavailable.",
    )

    assert "status=PASS" in result
    assert "artifact_count=10" in result
    assert "evidence_count=5" in result
    assert "launch-war-room.html" in result

    from evals.opensku.validators.core import REQUIRED_ARTIFACTS, validate_artifact_bundle

    assert {path.name for path in outputs.iterdir() if path.is_file()} == set(REQUIRED_ARTIFACTS)
    assert (outputs / "launch-war-room.html").stat().st_size < 25_000
    bundle_result = validate_artifact_bundle(outputs)
    assert bundle_result.ok, bundle_result.errors

    launch_state = json.loads((outputs / "launch-state.json").read_text(encoding="utf-8"))
    assert launch_state["stage"] == "pre_launch_test"
    assert launch_state["decision"] == "Hold"
    assert "EVID-001" in launch_state["evidence_ids"]


def test_write_opensku_artifact_bundle_is_exposed_as_builtin_tool():
    assert "write_opensku_artifact_bundle" in {tool.name for tool in BUILTIN_TOOLS}

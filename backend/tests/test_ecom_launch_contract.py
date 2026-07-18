from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ARTIFACTS = {
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
}
OPTIONAL_LOOP_ARTIFACTS = {
    "launch-state.json",
    "promotion-replan.md",
    "knowledge-deltas.json",
}
ECOM_ROLES = {
    "market-voc-researcher",
    "offer-architect",
    "growth-analyst",
    "asset-studio",
    "evidence-checker",
}
CLAIM_STATUSES = {
    "ready_public_insight",
    "needs_product_spec",
    "needs_test_report",
    "needs_policy_confirmation",
    "draft_only",
    "do_not_use_until_verified",
}
DECISION_CALIBRATION_RULES = {
    "Do not choose Hold solely because private metrics, ad attribution, margin, refund, or repeat-purchase data are unavailable",
    "Choose Pivot when available evidence supports a specific change to query, claim, format, offer, channel, or promotion plan",
    "Choose Go for a bounded pre_launch_test when public relevance or category-fit evidence supports the next test and no blocking risk is present",
    "For supplier_sample, unsupported claims usually mean Pivot the claim set or listing plan, not Hold, when uploaded sample or metadata is enough to continue under safer claims",
    "For soft_launch uploaded-data cases, missing attribution is not by itself Hold when order, review, payment, or product rows support a plan change",
}


def test_ecom_launch_skill_defaults_to_adaptive_launch_loop_snapshot():
    skill = (REPO_ROOT / "skills" / "custom" / "ecom-launch" / "SKILL.md").read_text(
        encoding="utf-8",
    )

    assert "agent workflow behind OpenSKU" in skill
    assert "validate-launch -> Adaptive Launch Loop snapshot" in skill
    assert "`validate-launch` means a full adaptive launch-loop snapshot by default" in skill
    assert "Launch Decision Pack plus next-loop recommendation" in skill
    assert "Go, Pivot, Hold, Kill, or Scale" in skill
    assert "launch-stage diagnosis" in skill
    assert "Only reduce scope when the user explicitly asks" in skill
    assert "three-file smoke test" in skill
    assert REQUIRED_ARTIFACTS.issubset(set(_artifact_mentions(skill)))
    assert OPTIONAL_LOOP_ARTIFACTS.issubset(set(_artifact_mentions(skill)))
    assert ECOM_ROLES.issubset(set(_role_mentions(skill)))
    assert CLAIM_STATUSES.issubset(set(_claim_status_mentions(skill)))
    assert "Run OpenSKU artifact validators before `present_files` when available" in skill
    assert "For benchmark-fixture validation" in skill
    assert "Do not call `web_search`, `web_fetch`, or `image_search` in benchmark-fixture mode" in skill
    assert "write_opensku_artifact_bundle" in skill
    assert "validate_opensku_artifacts" in skill
    assert "do not emit a giant `launch-war-room.html` through `write_file`" in skill
    assert "If `write_opensku_artifact_bundle` returns `status=PASS`, call `present_files` immediately" in skill
    assert "Do not claim row counts or internal artifact counts in the final response" in skill
    assert "Final artifact list must be filenames only" in skill
    assert "Do not add per-file descriptions, evidence counts, row counts, or entry counts" in skill
    assert "competitor,observed_claim,evidence_id,confidence,limitation" in skill
    assert "`competitor-table.csv` `evidence_id` values are exact `EVID-...` IDs" in skill
    assert "exact case-sensitive literal label `Evidence limitations:`" in skill
    assert "exact case-sensitive literal label `Claim readiness:`" in skill
    assert "exact section text `stop/continue rule`" in skill
    assert "After `present_files` succeeds, do not call another tool" in skill
    assert "After `validate_opensku_artifacts` returns PASS, call `present_files` immediately" in skill
    assert "If any specialist returns partial findings, times out, or fails" in skill
    assert "pre_launch_test search-fit mismatch defaults to Pivot" in skill
    assert "Kill only when the SKU or offer itself is not worth continuing" in skill
    assert DECISION_CALIBRATION_RULES.issubset(set(_decision_calibration_mentions(skill)))
    assert (
        "When uploaded feedback, uploaded real data, or benchmark context is present, create and present "
        "`launch-state.json`, `promotion-replan.md`, and `knowledge-deltas.json`"
        in skill
    )


def test_ecom_launch_soul_defaults_to_adaptive_launch_loop_snapshot():
    soul = (REPO_ROOT / "agents" / "ecom-launch" / "SOUL.md").read_text(
        encoding="utf-8",
    )

    assert "agent contract behind OpenSKU" in soul
    assert "validate-launch   -> Adaptive Launch Loop snapshot" in soul
    assert "By default, `validate-launch` means a complete Launch Decision Pack" in soul
    assert "launch-stage diagnosis" in soul
    assert "Go/Pivot/Hold/Kill/Scale" in soul
    assert "next-loop experiment or promotion replan" in soul
    assert "Only run a smoke test" in soul
    assert "use all five ecommerce roles" in soul
    assert REQUIRED_ARTIFACTS.issubset(set(_artifact_mentions(soul)))
    assert OPTIONAL_LOOP_ARTIFACTS.issubset(set(_artifact_mentions(soul)))
    assert ECOM_ROLES.issubset(set(_role_mentions(soul)))
    assert "Run OpenSKU artifact validators before `present_files` when available" in soul
    assert "In benchmark-fixture validation, do not call `web_search`, `web_fetch`, or `image_search`" in soul
    assert "write_opensku_artifact_bundle" in soul
    assert "do not emit a giant `launch-war-room.html` through `write_file`" in soul
    assert "Do not claim row counts or internal artifact counts in the final response" in soul
    assert "Final artifact list must be filenames only" in soul
    assert "Do not add per-file descriptions, evidence counts, row counts, or entry counts" in soul
    assert "Prefer the `validate_opensku_artifacts` tool when it is exposed" in soul
    assert "`competitor-table.csv` `evidence_id` must be one exact `EVID-...` id" in soul
    assert "exact case-sensitive literal label `Evidence limitations:`" in soul
    assert "exact case-sensitive literal label `Claim readiness:`" in soul
    assert "After `present_files` succeeds, do not call another tool" in soul
    assert "After `validate_opensku_artifacts` returns PASS, call `present_files` immediately" in soul
    assert "If a specialist returns partial findings, times out, or fails" in soul
    assert "pre_launch_test search-fit mismatch defaults to Pivot" in soul
    assert "Kill only when the SKU or offer itself is not worth continuing" in soul
    assert DECISION_CALIBRATION_RULES.issubset(set(_decision_calibration_mentions(soul)))
    assert (
        "Final response must state launch stage, decision, next-loop test, promotion adjustment, "
        "data limitations, and artifact list"
        in soul
    )


def test_ecom_launch_manual_prompt_matches_hardened_contract():
    manual = (REPO_ROOT / "docs" / "ecom-launch" / "manual-run-prompt.md").read_text(
        encoding="utf-8",
    )

    assert ECOM_ROLES.issubset(set(_role_mentions(manual)))
    assert REQUIRED_ARTIFACTS.issubset(set(_artifact_mentions(manual)))
    assert OPTIONAL_LOOP_ARTIFACTS.issubset(set(_artifact_mentions(manual)))
    assert "Go, Pivot, Hold, Kill, or Scale" in manual
    assert "Run OpenSKU artifact validators before `present_files` when available" in manual
    assert "write_opensku_artifact_bundle" in manual
    assert "do not emit a giant `launch-war-room.html` through `write_file`" in manual
    assert "If `write_opensku_artifact_bundle` returns `status=PASS`, call `present_files` immediately" in manual
    assert "Do not claim row counts or internal artifact counts in the final response" in manual
    assert "Final artifact list must be filenames only" in manual
    assert "Do not add per-file descriptions, evidence counts, row counts, or entry counts" in manual
    assert "Prefer the `validate_opensku_artifacts` tool when it is exposed" in manual
    assert "competitor,observed_claim,evidence_id,confidence,limitation" in manual
    assert "`competitor-table.csv` `evidence_id` must be one exact `EVID-...` id" in manual
    assert "exact case-sensitive literal label `Evidence limitations:`" in manual
    assert "exact case-sensitive literal label `Claim readiness:`" in manual
    assert "After `present_files` succeeds, do not call another tool" in manual
    assert "After `validate_opensku_artifacts` returns PASS, call `present_files` immediately" in manual
    assert "pre_launch_test search-fit mismatch defaults to Pivot" in manual
    assert "Kill only when the SKU or offer itself is not worth continuing" in manual
    assert DECISION_CALIBRATION_RULES.issubset(set(_decision_calibration_mentions(manual)))
    assert (
        "Final response must state launch stage, decision, next-loop test, promotion adjustment, "
        "data limitations, and artifact list"
        in manual
    )


def _artifact_mentions(text: str) -> list[str]:
    return [
        artifact
        for artifact in REQUIRED_ARTIFACTS | OPTIONAL_LOOP_ARTIFACTS
        if artifact in text
    ]


def _role_mentions(text: str) -> list[str]:
    return [role for role in ECOM_ROLES if role in text]


def _claim_status_mentions(text: str) -> list[str]:
    return [status for status in CLAIM_STATUSES if status in text]


def _decision_calibration_mentions(text: str) -> list[str]:
    return [rule for rule in DECISION_CALIBRATION_RULES if rule in text]

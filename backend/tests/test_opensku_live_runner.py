from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from evals.opensku.run_live_agent_validation import (  # noqa: E402
    build_artifact_manifest,
    build_live_prompt,
    final_response_consistency_errors,
    merge_parsed_streams,
    missing_final_response_requirements,
    parse_run_messages,
    parse_state,
)
from evals.opensku.knowledge_context import load_knowledge_patterns, select_knowledge_patterns  # noqa: E402


def test_parse_run_messages_recovers_subagents_after_state_summarization():
    run_messages = {
        "data": [
            {
                "content": {
                    "type": "ai",
                    "content": "launch specialists",
                    "response_metadata": {
                        "model_provider": "deepseek",
                        "model_name": "deepseek-v4-flash",
                        "token_usage": {"total_tokens": 123},
                    },
                    "tool_calls": [
                        {
                            "name": "task",
                            "args": {"subagent_type": "market-voc-researcher"},
                        },
                        {
                            "name": "task",
                            "args": {"subagent_type": "asset-studio"},
                        },
                    ],
                }
            },
            {
                "content": {
                    "type": "ai",
                    "content": "",
                    "tool_calls": [{"name": "present_files", "args": {"filepaths": []}}],
                }
            },
        ],
        "has_more": False,
    }

    state_parsed = parse_state({"messages": []})
    message_parsed = parse_run_messages(run_messages)
    parsed = merge_parsed_streams(state_parsed, message_parsed)

    assert parsed.model_provider == "deepseek"
    assert parsed.model_name == "deepseek-v4-flash"
    assert parsed.token_usage == {"total_tokens": 123}
    assert parsed.present_files_called is True
    assert parsed.subagent_types == ["asset-studio", "market-voc-researcher"]
    assert [call["name"] for call in parsed.tool_calls] == ["task", "task", "present_files"]


def test_live_prompt_requires_runtime_artifact_writer():
    prompt = build_live_prompt("opensku-live-test")

    assert "call write_opensku_artifact_bundle if that tool is available" in prompt
    assert "Do not use write_file to hand-write the required artifact bundle" in prompt
    assert "If write_opensku_artifact_bundle returns status=PASS, call present_files immediately" in prompt


def test_live_prompt_requires_plain_filename_artifact_list_without_counts():
    prompt = build_live_prompt("opensku-live-test")

    assert "Final artifact list must be filenames only" in prompt
    assert "Do not add per-file descriptions, evidence counts, row counts, or entry counts" in prompt


def test_live_prompt_includes_prelaunch_pivot_kill_boundary():
    prompt = build_live_prompt("opensku-live-test", case={"stage": "pre_launch_test"})

    assert "pre_launch_test search-fit mismatch defaults to Pivot" in prompt
    assert "Kill only when the SKU or offer itself is not worth continuing" in prompt


def test_live_prompt_includes_go_pivot_hold_calibration():
    prompt = build_live_prompt("opensku-live-test", case={"stage": "soft_launch"})

    assert (
        "Do not choose Hold solely because private metrics, ad attribution, margin, refund, or repeat-purchase data are unavailable"
        in prompt
    )
    assert "Choose Pivot when available evidence supports a specific change to query, claim, format, offer, channel, or promotion plan" in prompt
    assert (
        "Choose Go for a bounded pre_launch_test when public relevance or category-fit evidence supports the next test and no blocking risk is present"
        in prompt
    )
    assert (
        "For supplier_sample, unsupported claims usually mean Pivot the claim set or listing plan, not Hold, when uploaded sample or metadata is enough to continue under safer claims"
        in prompt
    )
    assert (
        "For soft_launch uploaded-data cases, missing attribution is not by itself Hold when order, review, payment, or product rows support a plan change"
        in prompt
    )


def test_live_prompt_injects_reusable_knowledge_patterns():
    patterns = load_knowledge_patterns(REPO_ROOT / "docs/knowledge/opensku")
    selected = select_knowledge_patterns(patterns, case={"stage": "idea_only"}, limit=3)

    prompt = build_live_prompt("opensku-live-test", injected_knowledge_patterns=selected)

    assert "Relevant OpenSKU reusable knowledge" in prompt
    assert "Do not convert public fixtures" in prompt
    assert "artifact writer plus validator" in prompt
    assert "Do not copy a previous decision unless the current evidence supports it" in prompt


def test_artifact_manifest_records_injected_knowledge_patterns(tmp_path):
    patterns = load_knowledge_patterns(REPO_ROOT / "docs/knowledge/opensku")
    selected = select_knowledge_patterns(patterns, case={"stage": "idea_only"}, limit=3)
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    parsed = parse_state({"messages": []})

    manifest = build_artifact_manifest(
        case_id="opensku-live-test",
        run_id="run-1",
        thread_id="thread-1",
        user_id="user-1",
        outputs_dir=outputs,
        parsed=parsed,
        uploaded_files=[],
        injected_knowledge_patterns=selected,
        knowledge_dir=REPO_ROOT / "docs/knowledge/opensku",
    )

    assert manifest["knowledge_dir"].endswith("docs/knowledge/opensku")
    injected = manifest["injected_knowledge_patterns"]
    assert injected[0]["statement"].startswith("Do not convert public fixtures")
    assert injected[1]["statement"].startswith("Use a runtime artifact writer plus validator")
    assert all(pattern["id"].startswith("kp_") for pattern in injected)


def test_final_response_requirement_checker_accepts_complete_chinese_summary():
    response = """
    上新阶段 Stage: idea_only
    当前决策 Decision: Hold
    下一循环: 7天验证冲刺，测试两个标题钩子。
    推广调整: 暂停放量，先做样本反馈。
    数据限制: GMV/CTR/CVR/ROI 不可用。
    Artifact list:
    launch-war-room.html
    evidence-ledger.json
    competitor-table.csv
    positioning-brief.md
    listing-pack.md
    content-pack.md
    launch-calendar.csv
    launch-state.json
    promotion-replan.md
    knowledge-deltas.json
    """

    assert missing_final_response_requirements(response) == []


def test_final_response_requirement_checker_accepts_data_boundary_synonyms():
    response = """
    上新阶段 Stage: idea_only
    当前决策 Decision: Hold
    下一轮验证: 先做样本访谈。
    推广调整: 暂停放量。
    数据局限: 所有证据来自公开基准测试集文件，无任何商户私域指标可获取。
    launch-war-room.html evidence-ledger.json competitor-table.csv positioning-brief.md listing-pack.md
    content-pack.md launch-calendar.csv launch-state.json promotion-replan.md knowledge-deltas.json
    """

    assert missing_final_response_requirements(response) == []


def test_final_response_requirement_checker_accepts_metric_limitations_wording():
    response = """
    案例阶段: pre_launch_test
    当前推荐方向: Pivot
    下一轮实验: 完成品类转向，验证 3-5 个正确查询词。
    推广调整: 暂停 salon chair 配对投放，改为床类查询词人工验证。
    指标限制: 本次验证仅基于 WANDS 公共基准测试数据，不包含任何私有商户指标。
    无价格数据、销售额、CTR、CVR、ROI、退款率、广告支出或实时排名数据可供参考。
    launch-war-room.html evidence-ledger.json competitor-table.csv positioning-brief.md listing-pack.md
    content-pack.md launch-calendar.csv launch-state.json promotion-replan.md knowledge-deltas.json
    """

    assert missing_final_response_requirements(response) == []


def test_final_response_consistency_checker_catches_wrong_evidence_count(tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "evidence-ledger.json").write_text(
        '[{"id":"EVID-001"},{"id":"EVID-002"},{"id":"EVID-003"},{"id":"EVID-004"},{"id":"EVID-005"}]\n',
        encoding="utf-8",
    )
    response = "`evidence-ledger.json` — 证据日志（6条证据追溯，含类型/来源/置信度/局限性）"

    assert final_response_consistency_errors(response, outputs) == [
        "final response claims evidence-ledger.json has 6 entries, expected 5"
    ]

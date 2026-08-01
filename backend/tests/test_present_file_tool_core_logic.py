"""Core behavior tests for present_files path normalization."""

import importlib
import json
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

present_file_tool_module = importlib.import_module("deerflow.tools.builtins.present_file_tool")


def _make_runtime(outputs_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        state={
            "thread_data": {"outputs_path": outputs_path},
            "messages": [HumanMessage(content="没有样品、没有规格表，请输出完整 Launch Validation Pack。", name="user-input")],
        },
        context={"thread_id": "thread-1"},
        config={},
    )


def test_present_files_normalizes_host_outputs_path(tmp_path):
    outputs_dir = tmp_path / "threads" / "thread-1" / "user-data" / "outputs"
    outputs_dir.mkdir(parents=True)
    artifact_path = outputs_dir / "report.md"
    artifact_path.write_text("ok")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_make_runtime(str(outputs_dir)),
        filepaths=[str(artifact_path)],
        tool_call_id="tc-1",
    )

    assert result.update["artifacts"] == ["/mnt/user-data/outputs/report.md"]
    assert result.update["messages"][0].content == "Successfully presented files"


def test_present_files_keeps_virtual_outputs_path(tmp_path, monkeypatch):
    outputs_dir = tmp_path / "threads" / "thread-1" / "user-data" / "outputs"
    outputs_dir.mkdir(parents=True)
    artifact_path = outputs_dir / "summary.json"
    artifact_path.write_text("{}")

    monkeypatch.setattr(
        present_file_tool_module,
        "get_paths",
        lambda: SimpleNamespace(resolve_virtual_path=lambda thread_id, path, *, user_id=None: artifact_path),
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_make_runtime(str(outputs_dir)),
        filepaths=["/mnt/user-data/outputs/summary.json"],
        tool_call_id="tc-2",
    )

    assert result.update["artifacts"] == ["/mnt/user-data/outputs/summary.json"]


def test_present_files_uses_config_thread_id_when_context_missing(tmp_path, monkeypatch):
    outputs_dir = tmp_path / "threads" / "thread-from-config" / "user-data" / "outputs"
    outputs_dir.mkdir(parents=True)
    artifact_path = outputs_dir / "summary.json"
    artifact_path.write_text("{}")

    monkeypatch.setattr(
        present_file_tool_module,
        "get_paths",
        lambda: SimpleNamespace(resolve_virtual_path=lambda thread_id, path: artifact_path),
    )

    runtime = SimpleNamespace(
        state={"thread_data": {"outputs_path": str(outputs_dir)}},
        context={},
        config={"configurable": {"thread_id": "thread-from-config"}},
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=runtime,
        filepaths=["/mnt/user-data/outputs/summary.json"],
        tool_call_id="tc-config",
    )

    assert result.update["artifacts"] == ["/mnt/user-data/outputs/summary.json"]
    assert result.update["messages"][0].content == "Successfully presented files"


def test_present_files_rejects_paths_outside_outputs(tmp_path):
    outputs_dir = tmp_path / "threads" / "thread-1" / "user-data" / "outputs"
    workspace_dir = tmp_path / "threads" / "thread-1" / "user-data" / "workspace"
    outputs_dir.mkdir(parents=True)
    workspace_dir.mkdir(parents=True)
    leaked_path = workspace_dir / "notes.txt"
    leaked_path.write_text("leak")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_make_runtime(str(outputs_dir)),
        filepaths=[str(leaked_path)],
        tool_call_id="tc-3",
    )

    assert "artifacts" not in result.update
    assert result.update["messages"][0].content == f"Error: Only files in /mnt/user-data/outputs can be presented: {leaked_path}"


PACK_FILES = [
    "launch-war-room.html",
    "evidence-ledger.json",
    "competitor-table.csv",
    "positioning-brief.md",
    "listing-pack.md",
    "content-pack.md",
    "launch-calendar.csv",
]


def _write_safe_pack(outputs_dir):
    (outputs_dir / "launch-war-room.html").write_text(
        '<!doctype html><html lang="zh-CN"><body><main><h1>验证作战室</h1><p>当前无样品、无规格，所有产品事实均待验证。本页面仅汇总公开信号、假设和七天验证动作。</p></main></body></html>',
        encoding="utf-8",
    )
    (outputs_dir / "evidence-ledger.json").write_text(
        json.dumps(
            {
                "meta": {"status": "无样品、无规格"},
                "entries": [
                    {
                        "id": "E1",
                        "claim": "公开类目页面存在",
                        "label": "observed_public",
                        "source_urls": ["https://example.com/source"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (outputs_dir / "competitor-table.csv").write_text(
        "name,evidence_label,source_url\n竞品A,observed_public,https://example.com/a\n",
        encoding="utf-8",
    )
    (outputs_dir / "positioning-brief.md").write_text(
        "# 定位验证简报\n\n内部验证假设：目标人群、通勤场景和价格接受度均待验证。先收集问题与预算信号，再决定是否进入样品阶段；不得把假设描述成现有产品能力或用户结论。七天内只记录可追溯的反馈数量、来源和停止条件。",
        encoding="utf-8",
    )
    (outputs_dir / "listing-pack.md").write_text(
        "# 概念调研页\n\n## 概念测试问题\n\n你最在意桌面充电的哪个问题？哪些信息缺失时你不会继续了解？当前无样品、无规格，本页面不售卖、不收款，也不承诺产品能力或交付时间。所有回答只用于判断是否值得进入下一阶段，不构成购买邀请。",
        encoding="utf-8",
    )
    (outputs_dir / "content-pack.md").write_text(
        "# 问题型内容\n\n## 调研问题\n\n你用桌面无线充时最困扰什么？你会先确认场景、预算还是现有替代方案？当前无样品、无规格，内容只用于收集问题，不描述现有产品能力，也不接受付款或预订。反馈会按来源和日期记录，无法确认的信息保持未知。",
        encoding="utf-8",
    )
    (outputs_dir / "launch-calendar.csv").write_text("day,action\n1,收集问题\n", encoding="utf-8")


def _pack_runtime(outputs_dir, *, audited=True):
    runtime = _make_runtime(str(outputs_dir))
    runtime.context["__deerflow_agent_run_budget"] = {
        "config": {
            "required_output_files": PACK_FILES,
            "required_completed_subagents": [
                "market-voc-researcher",
                "offer-architect",
                "asset-studio",
                "evidence-checker",
            ],
            "require_evidence_checker": True,
            "validate_pack_before_present": True,
        },
        "evidence_checker_completed": audited,
        "subagent_types_completed": {
            "market-voc-researcher",
            "offer-architect",
            "asset-studio",
            "evidence-checker",
        },
    }
    return runtime


def _active_ecom_pack_runtime(outputs_dir):
    runtime = _make_runtime(str(outputs_dir))
    runtime.context["__deerflow_agent_run_budget"] = {
        "config": {
            "required_output_files": PACK_FILES,
            "required_completed_subagents": [
                "market-voc-researcher",
                "offer-architect",
                "asset-studio",
            ],
            "require_evidence_checker": False,
            "validate_pack_before_present": True,
        },
        "subagent_types_completed": {
            "market-voc-researcher",
            "offer-architect",
            "asset-studio",
        },
    }
    return runtime


def test_complete_launch_pack_requires_evidence_checker(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir, audited=False),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-no-audit",
    )

    assert "artifacts" not in result.update
    assert "did not return a valid pass/revise/blocked verdict" in result.update["messages"][0].content


def test_active_ecom_pack_delivers_without_evidence_checker(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)

    result = present_file_tool_module.present_file_tool.func(
        runtime=_active_ecom_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-no-checker-required",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]
    assert result.update["messages"][0].content == "Successfully presented files"


def test_active_ecom_pack_normalizes_unsafe_no_sample_copy_without_checker(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "content-pack.md").write_text("我实测这款产品完全不漏。", encoding="utf-8")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_active_ecom_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-no-checker-unsafe",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]
    assert result.update["messages"][0].content == "Successfully presented files"
    normalized = (outputs_dir / "content-pack.md").read_text(encoding="utf-8")
    assert "我实测" not in normalized
    assert "概念调研版" in normalized


def test_active_ecom_pack_detects_no_sample_context_from_written_copy(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "content-pack.md").write_text(
        "# 概念内容\n\n阶段：无样品、无规格。本人妥妥杯子控，实测这只随行杯不漏；这只是内部草稿，仍需继续验证。\n",
        encoding="utf-8",
    )
    runtime = _active_ecom_pack_runtime(outputs_dir)
    runtime.state["messages"] = [HumanMessage(content="没有店铺后台数据，请输出完整 Pack。", name="user-input")]

    result = present_file_tool_module.present_file_tool.func(
        runtime=runtime,
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-no-sample-from-artifact",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]
    normalized = (outputs_dir / "content-pack.md").read_text(encoding="utf-8")
    assert "本人妥妥杯子控" not in normalized
    assert "概念调研版" in normalized


def test_active_ecom_pack_blocks_internal_compaction_marker(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "launch-war-room.html").write_text(
        "[compacted 5174 characters already written successfully to /mnt/user-data/outputs/launch-war-room.html; do not reread unless a deterministic preflight error names this file]",
        encoding="utf-8",
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_active_ecom_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-compaction-marker",
    )

    assert "artifacts" not in result.update
    assert "contains an internal history-compaction marker" in result.update["messages"][0].content


def test_complete_launch_pack_requires_every_configured_specialist(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    runtime = _pack_runtime(outputs_dir)
    runtime.context["__deerflow_agent_run_budget"]["subagent_types_completed"].remove("asset-studio")

    result = present_file_tool_module.present_file_tool.func(
        runtime=runtime,
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-no-assets",
    )

    assert "artifacts" not in result.update
    assert "configured specialist(s) have not completed" in result.update["messages"][0].content
    assert "asset-studio" in result.update["messages"][0].content


def test_complete_launch_pack_preflight_blocks_unsafe_claims_and_bad_urls(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "competitor-table.csv").write_text(
        "name,evidence_label,source_url\n竞品A,observed_public,example.com/a\n",
        encoding="utf-8",
    )
    (outputs_dir / "content-pack.md").write_text("最近我试用过这款产品，主打 Qi2 15W 快充和磁吸自动对位。", encoding="utf-8")
    (outputs_dir / "positioning-brief.md").write_text(
        "# 内容调性\n\n内容调性：用了就回不去。该句仅作为待审风险提示，不是用户体验证据。需要保留来源、风险边界和后续验证动作，不能把它写成真实用户结论。后续还要记录反馈数量、样本来源、时间范围和停止条件，避免用一句口号替代证据。\n",
        encoding="utf-8",
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-unsafe",
    )

    message = result.update["messages"][0].content
    assert "artifacts" not in result.update
    assert "row 2 is observed_public without a direct evidence source_url" in message
    assert "first-person usage/testimonial pattern" in message
    assert "positioning-brief.md" not in message


def test_complete_launch_pack_preflight_allows_unverified_competitor_rows_without_fake_urls(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "competitor-table.csv").write_text(
        "name,evidence_label,source_url\n竞品A,estimated,\n竞品B,unavailable,\n",
        encoding="utf-8",
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-estimated-competitors",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]


def test_complete_launch_pack_preflight_reports_all_missing_competitor_columns(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "competitor-table.csv").write_text(
        "name,price\n竞品A,99\n",
        encoding="utf-8",
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-missing-columns",
    )

    message = result.update["messages"][0].content
    assert "missing the source_url column" in message
    assert "missing the evidence_label column" in message


def test_complete_launch_pack_preflight_reads_evidence_label_field(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "evidence-ledger.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "E1",
                        "claim": "公开信号",
                        "evidence_label": "observed_public",
                        "source_urls": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-evidence-label",
    )

    assert "observed_public without a direct evidence source_urls value" in result.update["messages"][0].content


def test_complete_launch_pack_preflight_blocks_unattributed_usage_history(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "content-pack.md").write_text("三四十的硅胶碗，用了两个月就洗不干净了。", encoding="utf-8")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-usage-history",
    )

    assert "first-person usage/testimonial pattern" in result.update["messages"][0].content


def test_complete_launch_pack_preflight_allows_explicit_non_testimonial_language(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "content-pack.md").write_text("# Day 2 内容\n\n竞品观察对比帖（非实测，不包含使用体验），只记录待验证问题与来源，不描述本产品能力。后续只根据公开页面与真实反馈补充信息，未经确认的内容保持未知。\n", encoding="utf-8")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-non-testimonial",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]


def test_complete_launch_pack_preflight_blocks_unconfirmed_generic_product_specs(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)
    (outputs_dir / "content-pack.md").write_text("主打食品级材质、稳固防滑、可机洗，清洁更省心。", encoding="utf-8")

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-generic-specs",
    )

    message = result.update["messages"][0].content
    assert "artifacts" not in result.update
    assert "states an unconfirmed product feature" in message


def test_complete_launch_pack_preflight_allows_safe_audited_pack(tmp_path):
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    _write_safe_pack(outputs_dir)

    result = present_file_tool_module.present_file_tool.func(
        runtime=_pack_runtime(outputs_dir),
        filepaths=[str(outputs_dir / name) for name in PACK_FILES],
        tool_call_id="tc-pack-safe",
    )

    assert result.update["artifacts"] == [f"/mnt/user-data/outputs/{name}" for name in PACK_FILES]
    assert result.update["messages"][0].content == "Successfully presented files"

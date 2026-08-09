import importlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

from deerflow.sandbox import tools as sandbox_tools
from deerflow.sandbox.tools import _complete_pack_path_error, render_launch_pack_tool, write_launch_pack_tool
from deerflow.tools.builtins.launch_pack_guard import validate_launch_pack


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        context={
            "__deerflow_agent_run_budget": {
                "config": {
                    "auto_present_complete_pack": True,
                    "required_output_files": ["launch-war-room.html", "evidence-ledger.json"],
                }
            }
        },
        state={"messages": [HumanMessage(content="输出 Launch Validation Pack")]},
    )


def test_complete_pack_rejects_skill_and_scratch_writes() -> None:
    runtime = _runtime()
    assert "skills are already preloaded" in (_complete_pack_path_error(runtime, "/mnt/skills/custom/ecom-launch/SKILL.md") or "")
    assert "only under /mnt/user-data/outputs" in (_complete_pack_path_error(runtime, "/mnt/user-data/workspace/placeholder.md") or "")
    assert _complete_pack_path_error(runtime, "/mnt/user-data/outputs/evidence-ledger.json") is None


def test_write_launch_pack_writes_exact_seven_files_and_marks_ready(monkeypatch) -> None:
    required = [
        "launch-war-room.html",
        "evidence-ledger.json",
        "competitor-table.csv",
        "positioning-brief.md",
        "listing-pack.md",
        "content-pack.md",
        "launch-calendar.csv",
    ]
    runtime = SimpleNamespace(
        context={
            "__deerflow_agent_run_budget": {
                "config": {
                    "auto_present_complete_pack": True,
                    "required_output_files": required,
                }
            }
        },
        state={"messages": [HumanMessage(content="输出 Launch Validation Pack")]},
    )

    class FakeSandbox:
        def __init__(self) -> None:
            self.writes: dict[str, str] = {}

        def write_file(self, path: str, content: str, append: bool = False) -> None:
            assert append is False
            self.writes[path] = content

    fake = FakeSandbox()
    monkeypatch.setattr(sandbox_tools, "ensure_sandbox_initialized", lambda _runtime: fake)
    monkeypatch.setattr(sandbox_tools, "ensure_thread_directories_exist", lambda _runtime: None)
    monkeypatch.setattr(sandbox_tools, "is_local_sandbox", lambda _runtime: False)
    monkeypatch.setattr(sandbox_tools, "get_file_operation_lock", lambda _sandbox, _path: nullcontext())

    result = write_launch_pack_tool.func(
        runtime,
        launch_war_room_html="<html>war room</html>",
        evidence_ledger_json='{"entries": []}',
        competitor_table_csv="competitor,evidence_label,source_url\nA,estimated,\n",
        positioning_brief_md="# Positioning",
        listing_pack_md="# Listing",
        content_pack_md="# Content",
        launch_calendar_csv="day,action\n1,research\n",
    )

    assert "All seven required files are ready" in result
    assert set(fake.writes) == {f"/mnt/user-data/outputs/{name}" for name in required}
    state = runtime.context["__deerflow_agent_run_budget"]
    assert state["required_output_files_ready"] is True
    assert state["required_output_files_missing"] == []
    assert state["required_output_files_written"] == set(required)


def test_render_launch_pack_accepts_one_compact_spec_and_writes_preflight_clean_files(monkeypatch, tmp_path) -> None:
    required = [
        "launch-war-room.html",
        "evidence-ledger.json",
        "competitor-table.csv",
        "positioning-brief.md",
        "listing-pack.md",
        "content-pack.md",
        "launch-calendar.csv",
    ]
    runtime = SimpleNamespace(
        context={
            "__deerflow_agent_run_budget": {
                "config": {
                    "auto_present_complete_pack": True,
                    "required_output_files": required,
                }
            }
        },
        state={
            "messages": [
                HumanMessage(
                    content="我想做一个 99-199 元的通勤咖啡杯，但没有任何店铺后台数据。请输出 Launch Validation Pack。"
                )
            ]
        },
        tool_call_id="call-render-pack",
    )

    class DiskSandbox:
        def write_file(self, path: str, content: str, append: bool = False) -> None:
            assert append is False
            (tmp_path / Path(path).name).write_text(content, encoding="utf-8")

    monkeypatch.setattr(sandbox_tools, "ensure_sandbox_initialized", lambda _runtime: DiskSandbox())
    monkeypatch.setattr(sandbox_tools, "ensure_thread_directories_exist", lambda _runtime: None)
    monkeypatch.setattr(sandbox_tools, "is_local_sandbox", lambda _runtime: False)
    monkeypatch.setattr(sandbox_tools, "get_file_operation_lock", lambda _sandbox, _path: nullcontext())
    present_module = importlib.import_module("deerflow.tools.builtins.present_file_tool")

    def fake_present(_runtime, filepaths, tool_call_id):
        assert tool_call_id == "call-render-pack"
        assert {Path(path).name for path in filepaths} == set(required)
        return Command(
            update={
                "artifacts": filepaths,
                "messages": [ToolMessage("Successfully presented files", tool_call_id=tool_call_id, status="success")],
            }
        )

    monkeypatch.setattr(present_module.present_file_tool, "func", fake_present)

    result = render_launch_pack_tool.func(
        runtime,
        spec={
            "category": "通勤咖啡杯",
            "target_price": "99-199 元",
            "decision": "test_now",
            "decision_rationale": "先验证问题、预算和购买时机。",
            "audience": "工作日通勤人群",
            "evidence": [
                {
                    "claim": "公开类目页可访问",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://example.com/category"],
                }
            ],
        },
    )

    assert isinstance(result, Command)
    assert result.update["messages"][0].content == "Successfully presented files"
    assert validate_launch_pack(tmp_path, required, user_request=runtime.state["messages"][0].content) == []
    assert runtime.context["__deerflow_agent_run_budget"]["required_output_files_ready"] is True

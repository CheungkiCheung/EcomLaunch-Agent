"""Core behavior tests for task tool orchestration."""

import asyncio
import importlib
from enum import Enum
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from deerflow.subagents.config import SubagentConfig

# Use module import so tests can patch the exact symbols referenced inside task_tool().
task_tool_module = importlib.import_module("deerflow.tools.builtins.task_tool")
launch_pack_guard_module = importlib.import_module("deerflow.tools.builtins.launch_pack_guard")


class FakeSubagentStatus(Enum):
    # Match production enum values so branch comparisons behave identically.
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


def _make_runtime(*, app_config=None) -> SimpleNamespace:
    # Minimal ToolRuntime-like object; task_tool only reads these three attributes.
    context = {"thread_id": "thread-1"}
    if app_config is not None:
        context["app_config"] = app_config
    return SimpleNamespace(
        state={
            "sandbox": {"sandbox_id": "local"},
            "thread_data": {
                "workspace_path": "/tmp/workspace",
                "uploads_path": "/tmp/uploads",
                "outputs_path": "/tmp/outputs",
            },
        },
        context=context,
        config={"metadata": {"model_name": "ark-model", "trace_id": "trace-1"}},
    )


def _install_run_budget(
    runtime: SimpleNamespace,
    *,
    max_subagent_calls: int = 4,
    deduplicate_subagents: bool = True,
    allowed_subagent_types: list[str] | None = None,
    subagent_dependencies: dict[str, list[str]] | None = None,
    complete_workflow_patterns: list[str] | None = None,
    required_completed_subagents: list[str] | None = None,
    required_output_files: list[str] | None = None,
    finalize_after_subagent: str | None = None,
    validate_pack_before_evidence: bool = False,
    remaining_seconds: float = 120,
) -> None:
    now = task_tool_module.time.monotonic()
    runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY] = {
        "config": {
            "max_subagent_calls": max_subagent_calls,
            "deduplicate_subagents": deduplicate_subagents,
            "allowed_subagent_types": allowed_subagent_types,
            "subagent_dependencies": subagent_dependencies,
            "complete_workflow_patterns": complete_workflow_patterns,
            "required_completed_subagents": required_completed_subagents,
            "required_output_files": required_output_files,
            "finalize_after_subagent": finalize_after_subagent,
            "validate_pack_before_evidence": validate_pack_before_evidence,
        },
        "started_at_monotonic": now,
        "deadline_monotonic": now + remaining_seconds,
        "subagent_calls_started": 0,
        "subagent_types_started": set(),
        "subagent_types_completed": set(),
    }


def _make_subagent_config(name: str = "general-purpose") -> SubagentConfig:
    return SubagentConfig(
        name=name,
        description="General helper",
        system_prompt="Base system prompt",
        max_turns=50,
        timeout_seconds=10,
    )


def _make_result(
    status: FakeSubagentStatus,
    *,
    ai_messages: list[dict] | None = None,
    result: str | None = None,
    error: str | None = None,
    token_usage_records: list[dict] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        ai_messages=ai_messages or [],
        result=result,
        error=error,
        token_usage_records=token_usage_records or [],
        usage_reported=False,
    )


def _run_task_tool(**kwargs) -> str:
    """Execute the task tool across LangChain sync/async wrapper variants."""
    coroutine = getattr(task_tool_module.task_tool, "coroutine", None)
    if coroutine is not None:
        return asyncio.run(coroutine(**kwargs))
    return task_tool_module.task_tool.func(**kwargs)


async def _no_sleep(_: float) -> None:
    return None


class _DummyScheduledTask:
    def add_done_callback(self, _callback):
        return None


def test_task_tool_returns_error_for_unknown_subagent(monkeypatch):
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: None)
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", lambda: ["general-purpose"])

    result = _run_task_tool(
        runtime=None,
        description="执行任务",
        prompt="do work",
        subagent_type="general-purpose",
        tool_call_id="tc-1",
    )

    assert result == "Error: Unknown subagent type 'general-purpose'. Available: general-purpose"


def test_task_tool_rejects_bash_subagent_when_host_bash_disabled(monkeypatch):
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: _make_subagent_config())
    monkeypatch.setattr(task_tool_module, "is_host_bash_allowed", lambda: False)

    result = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="run commands",
        subagent_type="bash",
        tool_call_id="tc-bash",
    )

    assert result.startswith("Error: Bash subagent is disabled")


def test_run_budget_rejects_a_duplicate_specialist_without_starting_it(monkeypatch):
    runtime = _make_runtime()
    _install_run_budget(runtime)
    runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]["subagent_calls_started"] = 1
    runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]["subagent_types_started"] = {"market-voc-researcher"}
    monkeypatch.setattr(
        task_tool_module,
        "get_subagent_config",
        lambda _: _make_subagent_config(name="market-voc-researcher"),
    )
    monkeypatch.setattr(
        task_tool_module,
        "get_available_subagent_names",
        lambda: ["market-voc-researcher"],
    )

    result = _run_task_tool(
        runtime=runtime,
        description="重复研究",
        prompt="search again",
        subagent_type="market-voc-researcher",
        tool_call_id="tc-duplicate",
    )

    assert "already ran" in result
    assert runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]["subagent_calls_started"] == 1


def test_run_budget_rejects_disallowed_subagent_without_starting_it(monkeypatch):
    runtime = _make_runtime()
    _install_run_budget(runtime, allowed_subagent_types=["market-voc-researcher", "offer-architect"])
    monkeypatch.setattr(
        task_tool_module,
        "get_subagent_config",
        lambda _: _make_subagent_config(name="general-purpose"),
    )
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", lambda: ["general-purpose"])
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", lambda **_: pytest.fail("disallowed subagent must not start"))

    result = _run_task_tool(
        runtime=runtime,
        description="通用研究",
        prompt="redo the research",
        subagent_type="general-purpose",
        tool_call_id="tc-disallowed",
    )

    assert "not allowed for this agent" in result
    assert "market-voc-researcher, offer-architect" in result
    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0
    assert budget_state["subagent_types_started"] == set()


def test_completed_evidence_checker_marks_terminal_delivery_state():
    runtime = _make_runtime()
    _install_run_budget(runtime)

    task_tool_module._mark_completed_subagent(runtime, "evidence-checker", "verdict: revise")

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["evidence_checker_completed"] is True
    assert budget_state["evidence_checker_verdict"] == "revise"
    assert budget_state["evidence_checker_result"] == "verdict: revise"


def test_budget_stopped_evidence_checker_is_not_a_valid_audit():
    runtime = _make_runtime()
    _install_run_budget(runtime, finalize_after_subagent="evidence-checker")

    task_tool_module._mark_completed_subagent(
        runtime,
        "evidence-checker",
        "Specialist execution budget reached.\n停止原因：Token 上限 50000。",
    )

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert "evidence-checker" not in budget_state["subagent_types_completed"]
    assert budget_state["terminal_subagent_finished"] is True
    assert budget_state["evidence_checker_completed"] is False
    assert budget_state["evidence_checker_verdict"] is None


def test_budget_stopped_non_terminal_specialist_is_not_marked_completed():
    runtime = _make_runtime()
    _install_run_budget(runtime)

    task_tool_module._mark_completed_subagent(
        runtime,
        "market-voc-researcher",
        "Specialist execution budget reached.\n停止原因：主智能体模型调用上限 3 次。",
    )

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert "market-voc-researcher" not in budget_state["subagent_types_completed"]


def test_budget_stopped_required_specialist_terminates_complete_workflow():
    runtime = _make_runtime()
    runtime.state["messages"] = [
        HumanMessage(content="请输出完整 Launch Validation Pack", name="user-input"),
        HumanMessage(content="compact", name="compacted_file_history", additional_kwargs={"hide_from_ui": True}),
    ]
    _install_run_budget(
        runtime,
        complete_workflow_patterns=["Launch Validation Pack"],
        required_completed_subagents=["market-voc-researcher", "evidence-checker"],
    )

    task_tool_module._mark_completed_subagent(
        runtime,
        "market-voc-researcher",
        "Specialist execution budget reached.\n停止原因：主智能体模型调用上限 4 次。",
    )

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_types_completed"] == set()
    assert budget_state["workflow_failed_subagent"] == "market-voc-researcher"
    assert budget_state["terminal_subagent_finished"] is True


def test_evidence_checker_accepts_markdown_audit_result_heading():
    runtime = _make_runtime()
    _install_run_budget(runtime)

    task_tool_module._mark_completed_subagent(runtime, "evidence-checker", "## 审计结果：revise\n- 修正 E002")

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["evidence_checker_completed"] is True
    assert budget_state["evidence_checker_verdict"] == "revise"


def test_terminal_specialist_preflight_blocks_without_reserving_a_slot(tmp_path, monkeypatch):
    runtime = _make_runtime()
    runtime.state["thread_data"]["outputs_path"] = str(tmp_path)
    runtime.state["messages"] = [HumanMessage(content="没有样品，请输出完整 Launch Validation Pack", name="user-input")]
    _install_run_budget(
        runtime,
        required_output_files=["listing-pack.md"],
        finalize_after_subagent="evidence-checker",
        validate_pack_before_evidence=True,
    )

    def fake_validate(*_args, **kwargs):
        assert kwargs["user_request"] == "没有样品，请输出完整 Launch Validation Pack"
        return ["listing-pack.md:2 unsafe"]

    monkeypatch.setattr(task_tool_module, "validate_launch_pack", fake_validate)

    error = task_tool_module._terminal_specialist_preflight(runtime, "evidence-checker")

    assert error is not None
    assert "did not reserve a specialist slot" in error
    assert "listing-pack.md:2 unsafe" in error
    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0
    assert budget_state["subagent_types_started"] == set()
    assert budget_state["subagent_types_completed"] == set()


def test_second_terminal_preflight_failure_stops_further_audit_attempts(tmp_path, monkeypatch):
    runtime = _make_runtime()
    runtime.state["thread_data"]["outputs_path"] = str(tmp_path)
    runtime.state["messages"] = [HumanMessage(content="请输出完整 Launch Validation Pack", name="user-input")]
    _install_run_budget(
        runtime,
        required_output_files=["listing-pack.md"],
        finalize_after_subagent="evidence-checker",
        validate_pack_before_evidence=True,
    )
    monkeypatch.setattr(task_tool_module, "validate_launch_pack", lambda *_args, **_kwargs: ["listing-pack.md:2 unsafe"])

    first = task_tool_module._terminal_specialist_preflight(runtime, "evidence-checker")
    second = task_tool_module._terminal_specialist_preflight(runtime, "evidence-checker")
    assert first is not None and second is not None
    assert task_tool_module._record_terminal_preflight_failure(runtime, "evidence-checker", first) is False
    assert task_tool_module._record_terminal_preflight_failure(runtime, "evidence-checker", second) is True

    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["terminal_preflight_failures"] == 2
    assert budget_state["terminal_subagent_finished"] is True
    assert budget_state["evidence_checker_completed"] is False


def test_no_sample_pack_is_deterministically_normalized_before_audit(tmp_path):
    required = [
        "launch-war-room.html",
        "evidence-ledger.json",
        "competitor-table.csv",
        "positioning-brief.md",
        "listing-pack.md",
        "content-pack.md",
        "launch-calendar.csv",
    ]
    (tmp_path / "launch-war-room.html").write_text(
        "<html><body><main>Pack validation dashboard with public signals and seven-day actions.</main></body></html>\n",
        encoding="utf-8",
    )
    (tmp_path / "positioning-brief.md").write_text(
        "# Positioning brief\n\nInternal hypothesis: audience, use scenario, and price acceptance remain unverified; collect traceable problem and budget signals before sampling.\n",
        encoding="utf-8",
    )
    (tmp_path / "launch-calendar.csv").write_text("day,action\n1,collect questions\n", encoding="utf-8")
    (tmp_path / "evidence-ledger.json").write_text(
        '{"entries":[{"id":"E1","label":"observed_public","source_urls":[]}]}' + "\n",
        encoding="utf-8",
    )
    (tmp_path / "competitor-table.csv").write_text(
        "name,evidence_label,source_url\nA,observed_public,\n",
        encoding="utf-8",
    )
    (tmp_path / "listing-pack.md").write_text("亲测防泼水材质，专为20寸登机箱设计。\n", encoding="utf-8")
    (tmp_path / "content-pack.md").write_text("最近我试用了这款产品。\n", encoding="utf-8")
    user_request = "我想做一个 89-169 元的旅行收纳包套装，没有样品和规格表。"

    changed = launch_pack_guard_module.prepare_launch_pack_for_audit(
        tmp_path,
        required,
        user_request=user_request,
    )
    issues = launch_pack_guard_module.validate_launch_pack(
        tmp_path,
        required,
        user_request=user_request,
    )

    assert set(changed) == {"listing-pack.md", "content-pack.md", "evidence-ledger.json", "competitor-table.csv"}
    assert issues == []
    assert "不接受订单或付款" in (tmp_path / "listing-pack.md").read_text(encoding="utf-8")
    assert "不接受付款或预订" in (tmp_path / "content-pack.md").read_text(encoding="utf-8")


def test_run_budget_blocks_a_sibling_specialist_until_its_dependency_completes():
    runtime = _make_runtime()
    _install_run_budget(runtime, subagent_dependencies={"offer-architect": ["market-voc-researcher"]})
    runtime.state["messages"] = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {"subagent_type": "market-voc-researcher"},
                    "id": "tc-market",
                    "type": "tool_call",
                },
                {
                    "name": "task",
                    "args": {"subagent_type": "offer-architect"},
                    "id": "tc-offer",
                    "type": "tool_call",
                },
            ],
        )
    ]

    _, error = task_tool_module._apply_run_budget_to_subagent(runtime, _make_subagent_config("offer-architect"), "offer-architect")

    assert "must wait for prerequisite(s) market-voc-researcher" in error
    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0
    assert budget_state["subagent_types_started"] == set()


def test_complete_workflow_enforces_dependencies_even_when_the_prerequisite_was_not_scheduled():
    runtime = _make_runtime()
    runtime.state["messages"] = [HumanMessage(content="请输出完整 Launch Validation Pack")]
    _install_run_budget(
        runtime,
        subagent_dependencies={"evidence-checker": ["asset-studio"]},
        complete_workflow_patterns=["Launch Validation Pack"],
    )

    _, error = task_tool_module._apply_run_budget_to_subagent(
        runtime,
        _make_subagent_config("evidence-checker"),
        "evidence-checker",
    )

    assert "must wait for prerequisite(s) asset-studio" in error
    budget_state = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0


def test_run_budget_allows_a_dependent_specialist_standalone_or_after_completion():
    standalone_runtime = _make_runtime()
    dependencies = {"offer-architect": ["market-voc-researcher"]}
    _install_run_budget(standalone_runtime, subagent_dependencies=dependencies)
    standalone_runtime.state["messages"] = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {"subagent_type": "offer-architect"},
                    "id": "tc-offer",
                    "type": "tool_call",
                }
            ],
        )
    ]

    _, standalone_error = task_tool_module._apply_run_budget_to_subagent(
        standalone_runtime,
        _make_subagent_config("offer-architect"),
        "offer-architect",
    )

    assert standalone_error is None

    completed_runtime = _make_runtime()
    _install_run_budget(completed_runtime, subagent_dependencies=dependencies)
    completed_state = completed_runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]
    completed_state["subagent_types_started"] = {"market-voc-researcher"}
    task_tool_module._mark_completed_subagent(completed_runtime, "market-voc-researcher", "done")

    _, completed_error = task_tool_module._apply_run_budget_to_subagent(
        completed_runtime,
        _make_subagent_config("offer-architect"),
        "offer-architect",
    )

    assert completed_error is None


def test_run_budget_rejects_subagents_after_the_whole_run_limit(monkeypatch):
    runtime = _make_runtime()
    _install_run_budget(runtime, max_subagent_calls=1, deduplicate_subagents=False)
    runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]["subagent_calls_started"] = 1
    monkeypatch.setattr(
        task_tool_module,
        "get_subagent_config",
        lambda _: _make_subagent_config(name="offer-architect"),
    )
    monkeypatch.setattr(
        task_tool_module,
        "get_available_subagent_names",
        lambda: ["offer-architect"],
    )

    result = _run_task_tool(
        runtime=runtime,
        description="额外策略",
        prompt="design another offer",
        subagent_type="offer-architect",
        tool_call_id="tc-over-budget",
    )

    assert "run budget allows at most 1 subagent call" in result


def test_run_budget_clamps_specialist_timeout_to_remaining_wall_time(monkeypatch):
    runtime = _make_runtime()
    _install_run_budget(runtime, remaining_seconds=3.2)
    config = _make_subagent_config(name="offer-architect")
    captured = {}
    events = []

    class DummyExecutor:
        def __init__(self, **kwargs):
            captured["config"] = kwargs["config"]

        def execute_async(self, prompt, task_id=None):
            return task_id

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", lambda: ["offer-architect"])
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **_: [])

    result = _run_task_tool(
        runtime=runtime,
        description="策略设计",
        prompt="design offer",
        subagent_type="offer-architect",
        tool_call_id="tc-clamped",
    )

    assert result == "Task Succeeded. Result: done"
    assert 1 <= captured["config"].timeout_seconds <= 3


def test_task_tool_threads_runtime_app_config_to_subagent_dependencies(monkeypatch):
    app_config = object()
    config = _make_subagent_config(name="bash")
    runtime = _make_runtime(app_config=app_config)
    events = []
    captured = {}

    class DummyExecutor:
        def __init__(self, **kwargs):
            captured["executor_kwargs"] = kwargs

        def execute_async(self, prompt, task_id=None):
            captured["prompt"] = prompt
            return task_id or "generated-task-id"

    def fake_get_available_subagent_names(*, app_config):
        captured["names_app_config"] = app_config
        return ["bash"]

    def fake_get_subagent_config(name, *, app_config):
        captured["config_lookup"] = (name, app_config)
        return config

    def fake_is_host_bash_allowed(config):
        captured["bash_gate_app_config"] = config
        return True

    def fake_get_available_tools(**kwargs):
        captured["tools_kwargs"] = kwargs
        return ["tool-a"]

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", fake_get_available_subagent_names)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", fake_get_subagent_config)
    monkeypatch.setattr(task_tool_module, "is_host_bash_allowed", fake_is_host_bash_allowed)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", fake_get_available_tools)

    output = _run_task_tool(
        runtime=runtime,
        description="运行命令",
        prompt="inspect files",
        subagent_type="bash",
        tool_call_id="tc-explicit-config",
    )

    assert output == "Task Succeeded. Result: done"
    assert captured["names_app_config"] is app_config
    assert captured["config_lookup"] == ("bash", app_config)
    assert captured["bash_gate_app_config"] is app_config
    assert captured["tools_kwargs"]["app_config"] is app_config
    assert captured["executor_kwargs"]["app_config"] is app_config
    assert captured["executor_kwargs"]["tools"] == ["tool-a"]


def test_task_tool_emits_running_and_completed_events(monkeypatch):
    config = _make_subagent_config()
    runtime = _make_runtime()
    events = []
    captured = {}
    get_available_tools = MagicMock(return_value=["tool-a", "tool-b"])

    class DummyExecutor:
        def __init__(self, **kwargs):
            captured["executor_kwargs"] = kwargs

        def execute_async(self, prompt, task_id=None):
            captured["prompt"] = prompt
            captured["task_id"] = task_id
            return task_id or "generated-task-id"

    # Simulate two polling rounds: first running (with one message), then completed.
    responses = iter(
        [
            _make_result(FakeSubagentStatus.RUNNING, ai_messages=[{"id": "m1", "content": "phase-1"}]),
            _make_result(
                FakeSubagentStatus.COMPLETED,
                ai_messages=[{"id": "m1", "content": "phase-1"}, {"id": "m2", "content": "phase-2"}],
                result="all done",
            ),
        ]
    )

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: next(responses))
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    # task_tool lazily imports from deerflow.tools at call time, so patch that module-level function.
    monkeypatch.setattr("deerflow.tools.get_available_tools", get_available_tools)

    output = _run_task_tool(
        runtime=runtime,
        description="运行子任务",
        prompt="collect diagnostics",
        subagent_type="general-purpose",
        tool_call_id="tc-123",
    )

    assert output == "Task Succeeded. Result: all done"
    assert captured["prompt"] == "collect diagnostics"
    assert captured["task_id"] == "tc-123"
    assert captured["executor_kwargs"]["thread_id"] == "thread-1"
    assert captured["executor_kwargs"]["parent_model"] == "ark-model"
    assert captured["executor_kwargs"]["config"].max_turns == config.max_turns
    # Skills are no longer appended to system_prompt; they are loaded per-session
    # by SubagentExecutor and injected as conversation items (Codex pattern).
    assert captured["executor_kwargs"]["config"].system_prompt == "Base system prompt"

    get_available_tools.assert_called_once_with(model_name="ark-model", groups=None, subagent_enabled=False)

    event_types = [e["type"] for e in events]
    assert event_types == ["task_started", "task_running", "task_running", "task_completed"]
    assert events[-1]["result"] == "all done"


def test_task_tool_propagates_tool_groups_to_subagent(monkeypatch):
    """Verify tool_groups from parent metadata are passed to get_available_tools(groups=...)."""
    config = _make_subagent_config()
    parent_tool_groups = ["file:read", "file:write", "bash"]
    runtime = SimpleNamespace(
        state={
            "sandbox": {"sandbox_id": "local"},
            "thread_data": {"workspace_path": "/tmp/workspace"},
        },
        context={"thread_id": "thread-1"},
        config={"metadata": {"model_name": "ark-model", "trace_id": "trace-1", "tool_groups": parent_tool_groups}},
    )
    events = []
    get_available_tools = MagicMock(return_value=["tool-a"])

    class DummyExecutor:
        def __init__(self, **kwargs):
            pass

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", get_available_tools)

    output = _run_task_tool(
        runtime=runtime,
        description="执行任务",
        prompt="file work only",
        subagent_type="general-purpose",
        tool_call_id="tc-groups",
    )

    assert output == "Task Succeeded. Result: done"
    # The key assertion: groups should be propagated from parent metadata
    get_available_tools.assert_called_once_with(model_name="ark-model", groups=parent_tool_groups, subagent_enabled=False)


def test_task_tool_uses_subagent_model_override_for_tool_loading(monkeypatch):
    """Subagent model overrides should drive model-gated tool loading."""
    config = SubagentConfig(
        name="general-purpose",
        description="General helper",
        system_prompt="Base system prompt",
        model="vision-subagent-model",
        max_turns=50,
        timeout_seconds=10,
    )
    runtime = _make_runtime()
    runtime.config["metadata"]["model_name"] = "parent-text-model"
    events = []
    get_available_tools = MagicMock(return_value=[])

    class DummyExecutor:
        def __init__(self, **kwargs):
            pass

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", get_available_tools)

    output = _run_task_tool(
        runtime=runtime,
        description="inspect image",
        prompt="inspect the uploaded image",
        subagent_type="general-purpose",
        tool_call_id="tc-issue-2543",
    )

    assert output == "Task Succeeded. Result: done"
    get_available_tools.assert_called_once_with(
        model_name="vision-subagent-model",
        groups=None,
        subagent_enabled=False,
    )


def test_task_tool_inherits_parent_skill_allowlist_for_default_subagent(monkeypatch):
    config = _make_subagent_config()
    runtime = _make_runtime()
    runtime.config["metadata"]["available_skills"] = ["safe-skill"]
    events = []
    captured = {}

    class DummyExecutor:
        def __init__(self, **kwargs):
            captured["config"] = kwargs["config"]

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    output = _run_task_tool(
        runtime=runtime,
        description="执行任务",
        prompt="use skills",
        subagent_type="general-purpose",
        tool_call_id="tc-skills",
    )

    assert output == "Task Succeeded. Result: done"
    assert captured["config"].skills == ["safe-skill"]


def test_task_tool_keeps_explicit_subagent_skills_instead_of_intersecting_with_router_skills(monkeypatch):
    config = _make_subagent_config()
    config = SubagentConfig(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        max_turns=config.max_turns,
        timeout_seconds=config.timeout_seconds,
        skills=["safe-skill", "other-skill"],
    )
    runtime = _make_runtime()
    runtime.config["metadata"]["available_skills"] = ["safe-skill"]
    events = []
    captured = {}

    class DummyExecutor:
        def __init__(self, **kwargs):
            captured["config"] = kwargs["config"]

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    output = _run_task_tool(
        runtime=runtime,
        description="执行任务",
        prompt="use skills",
        subagent_type="general-purpose",
        tool_call_id="tc-skills-intersection",
    )

    assert output == "Task Succeeded. Result: done"
    assert captured["config"].skills == ["safe-skill", "other-skill"]


def test_task_tool_no_tool_groups_passes_none(monkeypatch):
    """Verify that when metadata has no tool_groups, groups=None is passed (backward compat)."""
    config = _make_subagent_config()
    # Default _make_runtime() has no tool_groups in metadata
    runtime = _make_runtime()
    events = []
    get_available_tools = MagicMock(return_value=[])

    class DummyExecutor:
        def __init__(self, **kwargs):
            pass

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="ok"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", get_available_tools)

    output = _run_task_tool(
        runtime=runtime,
        description="执行任务",
        prompt="normal work",
        subagent_type="general-purpose",
        tool_call_id="tc-no-groups",
    )

    assert output == "Task Succeeded. Result: ok"
    # No tool_groups in metadata → groups=None (default behavior preserved)
    get_available_tools.assert_called_once_with(model_name="ark-model", groups=None, subagent_enabled=False)


def test_task_tool_runtime_none_passes_groups_none(monkeypatch):
    """Verify that when runtime is None, groups=None is passed (e.g., unknown subagent path exits early, but tools still load correctly)."""
    config = _make_subagent_config()
    events = []
    get_available_tools = MagicMock(return_value=[])

    class DummyExecutor:
        def __init__(self, **kwargs):
            pass

        def execute_async(self, prompt, task_id=None):
            return task_id or "generated-task-id"

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "SubagentExecutor", DummyExecutor)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="ok"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", get_available_tools)
    fallback_app_config = SimpleNamespace(models=[SimpleNamespace(name="default-model")])
    monkeypatch.setattr(task_tool_module, "get_app_config", lambda: fallback_app_config)

    output = _run_task_tool(
        runtime=None,
        description="执行任务",
        prompt="no runtime",
        subagent_type="general-purpose",
        tool_call_id="tc-no-runtime",
    )

    assert output == "Task Succeeded. Result: ok"
    # runtime is None -> metadata is empty dict -> groups=None, model falls back to app default.
    get_available_tools.assert_called_once_with(
        model_name="default-model",
        groups=None,
        subagent_enabled=False,
        app_config=fallback_app_config,
    )

    config = _make_subagent_config()
    events = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.FAILED, error="subagent crashed"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="do fail",
        subagent_type="general-purpose",
        tool_call_id="tc-fail",
    )

    assert output == "Task failed. Error: subagent crashed"
    assert events[-1]["type"] == "task_failed"
    assert events[-1]["error"] == "subagent crashed"


def test_task_tool_returns_timed_out_message(monkeypatch):
    config = _make_subagent_config()
    events = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.TIMED_OUT, error="timeout"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="do timeout",
        subagent_type="general-purpose",
        tool_call_id="tc-timeout",
    )

    assert output == "Task timed out. Error: timeout"
    assert events[-1]["type"] == "task_timed_out"
    assert events[-1]["error"] == "timeout"


def test_complete_pack_timeout_is_degraded_and_keeps_dependency_chain_alive(monkeypatch):
    runtime = _make_runtime()
    runtime.state["messages"] = [HumanMessage(content="输出 Launch Validation Pack")]
    _install_run_budget(
        runtime,
        complete_workflow_patterns=["Launch Validation Pack"],
        required_completed_subagents=["market-voc-researcher"],
        subagent_dependencies={"offer-architect": ["market-voc-researcher"]},
    )
    config = _make_subagent_config(name="market-voc-researcher")
    events = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.TIMED_OUT, error="public search timeout"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])

    output = _run_task_tool(
        runtime=runtime,
        description="公开信号研究",
        prompt="research public signals",
        subagent_type="market-voc-researcher",
        tool_call_id="tc-degraded-pack",
    )

    assert output.startswith("Task degraded: market-voc-researcher")
    degraded = runtime.context[task_tool_module.RUN_BUDGET_CONTEXT_KEY]["subagent_types_degraded"]
    assert degraded["market-voc-researcher"] == "public search timeout"


def test_task_tool_polling_safety_timeout(monkeypatch):
    config = _make_subagent_config()
    # Keep max_poll_count small for test speed: (1 + 60) // 5 = 12
    config.timeout_seconds = 1
    events = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="never finish",
        subagent_type="general-purpose",
        tool_call_id="tc-safety-timeout",
    )

    assert output.startswith("Task polling timed out after 0 minutes")
    assert events[0]["type"] == "task_started"
    assert events[-1]["type"] == "task_timed_out"


def test_cleanup_called_on_completed(monkeypatch):
    """Verify cleanup_background_task is called when task completes."""
    config = _make_subagent_config()
    events = []
    cleanup_calls = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.COMPLETED, result="done"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="complete task",
        subagent_type="general-purpose",
        tool_call_id="tc-cleanup-completed",
    )

    assert output == "Task Succeeded. Result: done"
    assert cleanup_calls == ["tc-cleanup-completed"]


def test_cleanup_called_on_failed(monkeypatch):
    """Verify cleanup_background_task is called when task fails."""
    config = _make_subagent_config()
    events = []
    cleanup_calls = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.FAILED, error="error"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="fail task",
        subagent_type="general-purpose",
        tool_call_id="tc-cleanup-failed",
    )

    assert output == "Task failed. Error: error"
    assert cleanup_calls == ["tc-cleanup-failed"]


def test_cleanup_called_on_timed_out(monkeypatch):
    """Verify cleanup_background_task is called when task times out."""
    config = _make_subagent_config()
    events = []
    cleanup_calls = []

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.TIMED_OUT, error="timeout"),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="timeout task",
        subagent_type="general-purpose",
        tool_call_id="tc-cleanup-timedout",
    )

    assert output == "Task timed out. Error: timeout"
    assert cleanup_calls == ["tc-cleanup-timedout"]


def test_cleanup_not_called_on_polling_safety_timeout(monkeypatch):
    """Verify cleanup_background_task is NOT called directly on polling safety timeout.

    The task is still RUNNING so it cannot be safely removed yet. Instead,
    cooperative cancellation is requested and a deferred cleanup is scheduled.
    """
    config = _make_subagent_config()
    # Keep max_poll_count small for test speed: (1 + 60) // 5 = 12
    config.timeout_seconds = 1
    events = []
    cleanup_calls = []
    cancel_requests = []
    scheduled_cleanups = []

    class DummyCleanupTask:
        def add_done_callback(self, _callback):
            return None

    def fake_create_task(coro):
        scheduled_cleanups.append(coro)
        coro.close()
        return DummyCleanupTask()

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(task_tool_module.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )
    monkeypatch.setattr(
        task_tool_module,
        "request_cancel_background_task",
        lambda task_id: cancel_requests.append(task_id),
    )

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="never finish",
        subagent_type="general-purpose",
        tool_call_id="tc-no-cleanup-safety-timeout",
    )

    assert output.startswith("Task polling timed out after 0 minutes")
    # cleanup_background_task must NOT be called directly (task is still RUNNING)
    assert cleanup_calls == []
    # cooperative cancellation must be requested
    assert cancel_requests == ["tc-no-cleanup-safety-timeout"]
    # a deferred cleanup coroutine must be scheduled
    assert len(scheduled_cleanups) == 1


def test_cleanup_scheduled_on_cancellation(monkeypatch):
    """Verify cancellation handler synchronously cleans up after shielded wait."""
    config = _make_subagent_config()
    events = []
    cleanup_calls = []
    poll_count = 0

    def get_result(_: str):
        nonlocal poll_count
        poll_count += 1
        # Main loop polls RUNNING twice, then shielded wait gets COMPLETED
        if poll_count <= 2:
            return _make_result(FakeSubagentStatus.RUNNING, ai_messages=[])
        return _make_result(FakeSubagentStatus.COMPLETED, result="done")

    sleep_count = 0

    async def cancel_on_second_sleep(_: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(task_tool_module, "get_background_task_result", get_result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", cancel_on_second_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    with pytest.raises(asyncio.CancelledError):
        _run_task_tool(
            runtime=_make_runtime(),
            description="执行任务",
            prompt="cancel task",
            subagent_type="general-purpose",
            tool_call_id="tc-cancelled-cleanup",
        )

    # Cleanup happens synchronously within the cancellation handler
    assert cleanup_calls == ["tc-cancelled-cleanup"]


def test_cancelled_cleanup_stops_after_timeout(monkeypatch):
    """Verify cancellation handler survives a shielded-wait timeout gracefully.

    When the subagent never reaches a terminal state, the shielded wait times
    out (or is interrupted), the handler reports whatever usage it can, calls
    cleanup (which is a no-op for non-terminal tasks), and re-raises.
    """
    config = _make_subagent_config()
    events = []
    report_calls = []
    cleanup_calls = []
    scheduled_cleanups = []

    # Always return RUNNING — subagent never finishes
    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
    )

    async def cancel_on_first_sleep(_: float) -> None:
        raise asyncio.CancelledError

    def fake_report_subagent_usage(runtime, result):
        report_calls.append((runtime, result))

    class DummyCleanupTask:
        def __init__(self, coro):
            self.coro = coro

        def add_done_callback(self, callback):
            self.callback = callback

    def fake_create_task(coro):
        scheduled_cleanups.append(coro)
        coro.close()
        return DummyCleanupTask(coro)

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", cancel_on_first_sleep)
    monkeypatch.setattr(task_tool_module.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", fake_report_subagent_usage)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    with pytest.raises(asyncio.CancelledError):
        _run_task_tool(
            runtime=_make_runtime(),
            description="执行任务",
            prompt="cancel task",
            subagent_type="general-purpose",
            tool_call_id="tc-cancelled-timeout",
        )

    # Non-terminal tasks cannot be cleaned immediately; a deferred cleanup
    # keeps polling after the parent cancellation path exits.
    assert cleanup_calls == []
    assert len(scheduled_cleanups) == 1
    # _report_subagent_usage is called (but skips because result has no records)
    assert len(report_calls) == 1


def test_cancellation_wait_uses_subagent_polling_budget(monkeypatch):
    """Cancelled parent waits on the existing subagent polling budget, not a fixed timeout."""
    config = _make_subagent_config()
    events = []
    report_calls = []
    cleanup_calls = []
    sleep_count = 0
    result_polls = 0
    terminal_result = _make_result(FakeSubagentStatus.COMPLETED, result="done")

    def get_result(_: str):
        nonlocal result_polls
        result_polls += 1
        if result_polls < 5:
            return _make_result(FakeSubagentStatus.RUNNING, ai_messages=[])
        return terminal_result

    async def cancel_then_continue(_: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 1:
            raise asyncio.CancelledError

    def fake_report_subagent_usage(runtime, result):
        report_calls.append((runtime, result))

    async def fail_on_fixed_timeout(awaitable, *, timeout=None):
        raise AssertionError(f"cancellation wait should not use fixed timeout={timeout}")

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_background_task_result", get_result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", cancel_then_continue)
    monkeypatch.setattr(task_tool_module.asyncio, "wait_for", fail_on_fixed_timeout)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", fake_report_subagent_usage)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    with pytest.raises(asyncio.CancelledError):
        _run_task_tool(
            runtime=_make_runtime(),
            description="执行任务",
            prompt="cancel task",
            subagent_type="general-purpose",
            tool_call_id="tc-cancel-budget",
        )

    assert report_calls == [(_make_runtime(), terminal_result)]
    assert cleanup_calls == ["tc-cancel-budget"]


def test_cancellation_calls_request_cancel(monkeypatch):
    """Verify CancelledError path calls request_cancel_background_task(task_id)."""
    config = _make_subagent_config()
    events = []
    cancel_requests = []

    async def cancel_on_first_sleep(_: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(
        task_tool_module,
        "get_background_task_result",
        lambda _: _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
    )
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", cancel_on_first_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "request_cancel_background_task",
        lambda task_id: cancel_requests.append(task_id),
    )
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: None,
    )

    with pytest.raises(asyncio.CancelledError):
        _run_task_tool(
            runtime=_make_runtime(),
            description="执行任务",
            prompt="cancel me",
            subagent_type="general-purpose",
            tool_call_id="tc-cancel-request",
        )

    assert cancel_requests == ["tc-cancel-request"]


def test_task_tool_returns_cancelled_message(monkeypatch):
    """Verify polling a CANCELLED result emits task_cancelled event and returns message."""
    config = _make_subagent_config()
    events = []
    cleanup_calls = []

    # First poll: RUNNING, second poll: CANCELLED
    responses = iter(
        [
            _make_result(FakeSubagentStatus.RUNNING, ai_messages=[]),
            _make_result(FakeSubagentStatus.CANCELLED, error="Cancelled by user"),
        ]
    )

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)

    monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: next(responses))
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    output = _run_task_tool(
        runtime=_make_runtime(),
        description="执行任务",
        prompt="some task",
        subagent_type="general-purpose",
        tool_call_id="tc-poll-cancelled",
    )

    assert output == "Task cancelled by user."
    assert any(e.get("type") == "task_cancelled" for e in events)
    assert cleanup_calls == ["tc-poll-cancelled"]


def test_cancellation_reports_subagent_usage(monkeypatch):
    """Verify cancellation handler waits (shielded) for subagent terminal state,
    then reports the final token usage before re-raising CancelledError.

    The report must happen synchronously within the cancellation handler so
    the parent worker's finally block sees the updated journal totals.
    """
    config = _make_subagent_config()
    events = []
    report_calls = []
    cleanup_calls = []

    # Terminal result with token usage collected after cancellation processing
    cancel_result = _make_result(FakeSubagentStatus.CANCELLED, error="Cancelled by user")
    cancel_result.token_usage_records = [{"source_run_id": "sub-run-1", "caller": "subagent:gp", "input_tokens": 50, "output_tokens": 25, "total_tokens": 75}]
    cancel_result.usage_reported = False

    poll_count = 0

    def get_result(_: str):
        nonlocal poll_count
        poll_count += 1
        # Main loop polls 3 times (RUNNING each time to keep looping)
        if poll_count <= 3:
            running = _make_result(FakeSubagentStatus.RUNNING, ai_messages=[])
            running.token_usage_records = []
            running.usage_reported = False
            return running
        # Shielded wait poll gets the terminal result
        return cancel_result

    sleep_count = 0

    async def cancel_on_third_sleep(_: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 3:
            raise asyncio.CancelledError

    def fake_report_subagent_usage(runtime, result):
        report_calls.append((runtime, result))

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_background_task_result", get_result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", cancel_on_third_sleep)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", fake_report_subagent_usage)
    monkeypatch.setattr("deerflow.tools.get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(task_tool_module, "request_cancel_background_task", lambda _: None)
    monkeypatch.setattr(
        task_tool_module,
        "cleanup_background_task",
        lambda task_id: cleanup_calls.append(task_id),
    )

    with pytest.raises(asyncio.CancelledError):
        _run_task_tool(
            runtime=_make_runtime(),
            description="执行任务",
            prompt="cancel me",
            subagent_type="general-purpose",
            tool_call_id="tc-cancel-report",
        )

    # _report_subagent_usage is called synchronously within the cancellation
    # handler (after the shielded wait), before CancelledError is re-raised.
    assert len(report_calls) == 1
    assert report_calls[0][1] is cancel_result
    assert cleanup_calls == ["tc-cancel-report"]


@pytest.mark.parametrize(
    "status, expected_type",
    [
        (FakeSubagentStatus.COMPLETED, "task_completed"),
        (FakeSubagentStatus.FAILED, "task_failed"),
        (FakeSubagentStatus.CANCELLED, "task_cancelled"),
        (FakeSubagentStatus.TIMED_OUT, "task_timed_out"),
    ],
)
def test_terminal_events_include_usage(monkeypatch, status, expected_type):
    """Terminal task events include a usage summary from token_usage_records."""
    config = _make_subagent_config()
    runtime = _make_runtime()
    events = []

    records = [
        {"source_run_id": "r1", "caller": "subagent:general-purpose", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        {"source_run_id": "r2", "caller": "subagent:general-purpose", "input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
    ]
    result = _make_result(status, result="ok" if status == FakeSubagentStatus.COMPLETED else None, error="err" if status != FakeSubagentStatus.COMPLETED else None, token_usage_records=records)

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", lambda *_: None)
    monkeypatch.setattr(task_tool_module, "cleanup_background_task", lambda _: None)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    _run_task_tool(
        runtime=runtime,
        description="test",
        prompt="do work",
        subagent_type="general-purpose",
        tool_call_id="tc-usage",
    )

    terminal_events = [e for e in events if e["type"] == expected_type]
    assert len(terminal_events) == 1
    assert terminal_events[0]["usage"] == {
        "input_tokens": 300,
        "output_tokens": 130,
        "total_tokens": 430,
    }


def test_terminal_event_usage_none_when_no_records(monkeypatch):
    """Terminal event has usage=None when token_usage_records is empty."""
    config = _make_subagent_config()
    runtime = _make_runtime()
    events = []

    result = _make_result(FakeSubagentStatus.COMPLETED, result="done", token_usage_records=[])

    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _: config)
    monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(task_tool_module.asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", lambda *_: None)
    monkeypatch.setattr(task_tool_module, "cleanup_background_task", lambda _: None)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    _run_task_tool(
        runtime=runtime,
        description="test",
        prompt="do work",
        subagent_type="general-purpose",
        tool_call_id="tc-no-records",
    )

    completed = [e for e in events if e["type"] == "task_completed"]
    assert len(completed) == 1
    assert completed[0]["usage"] is None


def test_subagent_usage_cache_is_skipped_when_config_file_is_missing(monkeypatch):
    monkeypatch.setattr(
        task_tool_module,
        "get_app_config",
        MagicMock(side_effect=FileNotFoundError("missing config")),
    )

    assert task_tool_module._token_usage_cache_enabled(None) is False


def test_subagent_usage_cache_is_skipped_when_provider_env_is_unresolved(monkeypatch):
    monkeypatch.setattr(
        task_tool_module,
        "get_app_config",
        MagicMock(side_effect=ValueError("Environment variable DEEPSEEK_API_KEY not found for config value $DEEPSEEK_API_KEY")),
    )

    assert task_tool_module._token_usage_cache_enabled(None) is False


def test_subagent_usage_cache_preserves_unrelated_config_errors(monkeypatch):
    monkeypatch.setattr(
        task_tool_module,
        "get_app_config",
        MagicMock(side_effect=ValueError("token_usage.enabled must be a boolean")),
    )

    with pytest.raises(ValueError, match="token_usage.enabled must be a boolean"):
        task_tool_module._token_usage_cache_enabled(None)


def test_subagent_usage_cache_is_skipped_when_token_usage_is_disabled(monkeypatch):
    config = _make_subagent_config()
    app_config = SimpleNamespace(token_usage=SimpleNamespace(enabled=False))
    runtime = _make_runtime(app_config=app_config)
    records = [{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}]
    result = _make_result(FakeSubagentStatus.COMPLETED, result="done", token_usage_records=records)

    task_tool_module._subagent_usage_cache.clear()
    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", lambda *, app_config: ["general-purpose"])
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _, *, app_config: config)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_background_task_result", lambda _: result)
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: lambda _: None)
    monkeypatch.setattr(task_tool_module, "_report_subagent_usage", lambda *_: None)
    monkeypatch.setattr(task_tool_module, "cleanup_background_task", lambda _: None)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    _run_task_tool(
        runtime=runtime,
        description="test",
        prompt="do work",
        subagent_type="general-purpose",
        tool_call_id="tc-disabled-cache",
    )

    assert task_tool_module.pop_cached_subagent_usage("tc-disabled-cache") is None


def test_subagent_usage_cache_is_cleared_when_polling_raises(monkeypatch):
    config = _make_subagent_config()
    app_config = SimpleNamespace(token_usage=SimpleNamespace(enabled=True))
    runtime = _make_runtime(app_config=app_config)

    task_tool_module._subagent_usage_cache["tc-error"] = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
    monkeypatch.setattr(task_tool_module, "SubagentStatus", FakeSubagentStatus)
    monkeypatch.setattr(task_tool_module, "get_available_subagent_names", lambda *, app_config: ["general-purpose"])
    monkeypatch.setattr(task_tool_module, "get_subagent_config", lambda _, *, app_config: config)
    monkeypatch.setattr(
        task_tool_module,
        "SubagentExecutor",
        type("DummyExecutor", (), {"__init__": lambda self, **kwargs: None, "execute_async": lambda self, prompt, task_id=None: task_id}),
    )
    monkeypatch.setattr(task_tool_module, "get_background_task_result", MagicMock(side_effect=RuntimeError("poll failed")))
    monkeypatch.setattr(task_tool_module, "get_stream_writer", lambda: lambda _: None)
    monkeypatch.setattr("deerflow.tools.get_available_tools", MagicMock(return_value=[]))

    with pytest.raises(RuntimeError, match="poll failed"):
        _run_task_tool(
            runtime=runtime,
            description="test",
            prompt="do work",
            subagent_type="general-purpose",
            tool_call_id="tc-error",
        )

    assert task_tool_module.pop_cached_subagent_usage("tc-error") is None

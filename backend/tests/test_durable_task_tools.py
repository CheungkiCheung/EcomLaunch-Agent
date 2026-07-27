"""Parent-facing tools for the durable Subagent task lifecycle."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import StrEnum
from types import SimpleNamespace
from typing import get_type_hints

import pytest
from pydantic import TypeAdapter, ValidationError

from deerflow.subagents.tasks import (
    DurableSubagentTaskRuntime,
    MemorySubagentTaskStore,
    SubagentTaskManager,
    SubagentTaskStatus,
)
from deerflow.tools.builtins import durable_task_tools as tool_module


class _Status(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self is not type(self).RUNNING


@dataclass
class _Result:
    task_id: str
    trace_id: str
    status: _Status
    result: str | None = None
    error: str | None = None
    token_usage_records: list[dict] | None = None

    def __post_init__(self) -> None:
        self.token_usage_records = self.token_usage_records or []


@dataclass
class _Config:
    name: str = "analyst"
    skills: list[str] | None = None
    max_turns: int = 8
    timeout_seconds: int = 30
    max_tool_rounds: int | None = 4
    max_tool_calls: int | None = 8
    disallowed_tools: list[str] | None = None


class _Executor:
    def __init__(self, results: dict[str, _Result]) -> None:
        self.results = results
        self.config = _Config()
        self.tools = []
        self.trace_id = "trace-1"
        self.calls: list[tuple[str, str | None]] = []

    def execute_async(self, prompt: str, task_id: str | None = None) -> str:
        assert task_id is not None
        self.calls.append((prompt, task_id))
        self.results[task_id] = _Result(
            task_id=task_id,
            trace_id=self.trace_id,
            status=_Status.RUNNING,
        )
        return task_id


class _Runtime:
    def __init__(
        self,
        task_runtime: DurableSubagentTaskRuntime,
        *,
        run_id: str = "run-1",
        require_explicit_subagent_scope: bool = False,
    ) -> None:
        self.context = {
            "thread_id": "thread-1",
            "run_id": run_id,
            "user_id": "user-1",
            "__subagent_task_runtime": task_runtime,
            "__subagent_task_manager": task_runtime.manager,
        }
        self.config = {"metadata": {"model_name": "deepseek-reasoner"}}
        if require_explicit_subagent_scope:
            self.config["configurable"] = {
                "require_explicit_subagent_scope": True,
            }
        self.state = {"sandbox": None, "thread_data": None}


async def _invoke(tool, **kwargs):
    coroutine = getattr(tool, "coroutine", None)
    assert coroutine is not None
    return await coroutine(**kwargs)


def test_explicit_scope_spawn_schema_requires_minimal_capability_and_budget():
    strict_tool = tool_module.with_explicit_subagent_scope_schema(
        tool_module.spawn_task_tool,
    )

    schema = strict_tool.tool_call_schema.model_json_schema()
    required = set(schema["required"])
    assert {
        "description",
        "prompt",
        "subagent_type",
        "skills",
        "tools",
        "max_tool_rounds",
        "max_tool_calls",
    } <= required
    assert schema["properties"]["skills"]["minItems"] == 1
    assert schema["properties"]["tools"]["minItems"] == 1

    with pytest.raises(ValidationError):
        strict_tool.args_schema.model_validate(
            {
                "description": "核验履约变化",
                "prompt": "独立重算核心指标",
                "subagent_type": "verifier",
            }
        )


def test_default_spawn_schema_keeps_profile_defaults_optional():
    schema = tool_module.spawn_task_tool.tool_call_schema.model_json_schema()

    assert "skills" not in schema["required"]
    assert "tools" not in schema["required"]
    assert "max_tool_rounds" not in schema["required"]
    assert "max_tool_calls" not in schema["required"]


@pytest.fixture
def components(monkeypatch):
    results: dict[str, _Result] = {}
    cancelled: list[str] = []
    manager = SubagentTaskManager(MemorySubagentTaskStore())
    task_runtime = DurableSubagentTaskRuntime(
        manager,
        worker_id="test-worker",
        poll_interval_seconds=0.001,
        result_getter=results.get,
        cancel_requester=cancelled.append,
        cleanup=lambda _task_id: None,
    )
    executors: list[_Executor] = []

    def build_executor(
        _runtime,
        _subagent_type,
        requested_skills=None,
        requested_tools=None,
        requested_max_tool_rounds=None,
        requested_max_tool_calls=None,
    ):
        executor = _Executor(results)
        if requested_skills is not None:
            executor.config = replace(
                executor.config,
                skills=list(requested_skills),
            )
        if requested_max_tool_rounds is not None:
            executor.config = replace(
                executor.config,
                max_tool_rounds=requested_max_tool_rounds,
            )
        if requested_max_tool_calls is not None:
            executor.config = replace(
                executor.config,
                max_tool_calls=requested_max_tool_calls,
            )
        executors.append(executor)
        return tool_module.SubagentExecutorBundle(
            executor=executor,
            config=executor.config,
            available_tools=tuple(requested_tools or ()),
        )

    monkeypatch.setattr(tool_module, "_build_subagent_executor", build_executor)
    return task_runtime, manager, results, cancelled, executors


@pytest.mark.anyio
async def test_spawn_task_returns_immediately_with_durable_task_id(components):
    task_runtime, manager, _results, _cancelled, executors = components

    raw = await _invoke(
        tool_module.spawn_task_tool,
        runtime=_Runtime(task_runtime),
        description="分析履约异常",
        prompt="定位延迟履约率上升的原因",
        subagent_type="analyst",
        skills=["fulfillment-investigation"],
        tool_call_id="call-spawn-1",
    )

    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["task"]["task_id"] == "call-spawn-1"
    assert payload["task"]["status"] == "running"
    assert payload["task"]["source_refs"] == []
    assert executors[0].calls == [("定位延迟履约率上升的原因", "call-spawn-1")]
    persisted = await manager.get("call-spawn-1")
    assert persisted.status is SubagentTaskStatus.running
    assert persisted.context_packet.available_skills == ("fulfillment-investigation",)

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_spawn_task_persists_minimal_tools_and_round_budget(components):
    task_runtime, manager, _results, _cancelled, _executors = components

    await _invoke(
        tool_module.spawn_task_tool,
        runtime=_Runtime(task_runtime),
        description="核验履约变化",
        prompt="只做一次窗口比较和一次证据抽查",
        subagent_type="analyst",
        tools=["commerce_compare_windows", "commerce_evidence_query"],
        max_tool_rounds=2,
        max_tool_calls=3,
        tool_call_id="budgeted-task",
    )

    persisted = await manager.get("budgeted-task")
    assert persisted.context_packet.available_tools == (
        "commerce_compare_windows",
        "commerce_evidence_query",
    )
    assert persisted.context_packet.budget["max_tool_rounds"] == 2
    assert persisted.context_packet.budget["max_tool_calls"] == 3

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_spawn_task_requires_explicit_non_empty_scope_when_policy_enabled(
    components,
):
    task_runtime, _manager, _results, _cancelled, _executors = components
    runtime = _Runtime(
        task_runtime,
        require_explicit_subagent_scope=True,
    )

    with pytest.raises(ValueError, match="explicit non-empty skills, tools"):
        await _invoke(
            tool_module.spawn_task_tool,
            runtime=runtime,
            description="核验履约变化",
            prompt="独立重算核心指标",
            subagent_type="verifier",
            source_refs=["task:missing"],
            tool_call_id="call-scopeless-task",
        )

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_spawn_task_accepts_complete_explicit_scope_when_policy_enabled(
    components,
):
    task_runtime, manager, _results, _cancelled, _executors = components
    runtime = _Runtime(
        task_runtime,
        require_explicit_subagent_scope=True,
    )

    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="计算履约变化",
        prompt="独立计算核心指标",
        subagent_type="analyst",
        skills=["fulfillment-investigation"],
        tools=["commerce_compare_windows", "commerce_evidence_query"],
        max_tool_rounds=2,
        max_tool_calls=2,
        tool_call_id="call-scoped-task",
    )

    persisted = await manager.get("call-scoped-task")
    assert persisted.context_packet.available_skills == (
        "fulfillment-investigation",
    )
    assert persisted.context_packet.available_tools == (
        "commerce_compare_windows",
        "commerce_evidence_query",
    )
    assert persisted.context_packet.budget["max_tool_rounds"] == 2
    assert persisted.context_packet.budget["max_tool_calls"] == 2

    await task_runtime.shutdown(reason="test cleanup")


def test_build_subagent_executor_propagates_runtime_user_id(monkeypatch):
    """The Durable builder must pass the Parent's explicit user scope."""
    import deerflow.tools as tools_package

    captured = {}

    class _CapturedExecutor:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    config = SimpleNamespace(
        name="analyst",
        model="fixed-model",
        skills=[],
        tools=None,
        disallowed_tools=None,
    )
    runtime = SimpleNamespace(
        context={"thread_id": "thread-1", "user_id": "user-42"},
        config={"metadata": {"model_name": "parent-model"}},
        state={"sandbox": None, "thread_data": None},
    )
    monkeypatch.setattr(tool_module, "get_subagent_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(tool_module, "get_available_subagent_names", lambda *args, **kwargs: ["analyst"])
    monkeypatch.setattr(tool_module, "resolve_subagent_model_name", lambda *args, **kwargs: "fixed-model")
    monkeypatch.setattr(tools_package, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(tool_module, "filter_tools_by_runtime_constraints", lambda tools, context: tools)
    monkeypatch.setattr(tool_module, "SubagentExecutor", _CapturedExecutor)

    tool_module._build_subagent_executor(runtime, "analyst")

    assert captured["user_id"] == "user-42"


def test_build_subagent_executor_enforces_minimal_tools_and_lower_budget(monkeypatch):
    """Parent may narrow a Profile's tool and round envelope, never expand it."""
    import deerflow.tools as tools_package
    from deerflow.subagents.config import SubagentConfig

    captured = {}

    class _CapturedExecutor:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    config = SubagentConfig(
        name="analyst",
        description="分析",
        model="fixed-model",
        skills=[],
        max_tool_rounds=4,
        max_tool_calls=6,
    )
    runtime = SimpleNamespace(
        context={"thread_id": "thread-1", "user_id": "user-42"},
        config={"metadata": {"model_name": "parent-model"}},
        state={"sandbox": None, "thread_data": None},
    )
    available = [
        SimpleNamespace(name="commerce_capabilities"),
        SimpleNamespace(name="commerce_compare_windows"),
        SimpleNamespace(name="commerce_evidence_query"),
    ]
    monkeypatch.setattr(tool_module, "get_subagent_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(tool_module, "get_available_subagent_names", lambda *args, **kwargs: ["analyst"])
    monkeypatch.setattr(tool_module, "resolve_subagent_model_name", lambda *args, **kwargs: "fixed-model")
    monkeypatch.setattr(tools_package, "get_available_tools", lambda **kwargs: available)
    monkeypatch.setattr(tool_module, "filter_tools_by_runtime_constraints", lambda tools, context: tools)
    monkeypatch.setattr(tool_module, "SubagentExecutor", _CapturedExecutor)

    bundle = tool_module._build_subagent_executor(
        runtime,
        "analyst",
        requested_tools=["commerce_compare_windows", "commerce_evidence_query"],
        requested_max_tool_rounds=2,
        requested_max_tool_calls=3,
    )

    assert bundle.available_tools == (
        "commerce_compare_windows",
        "commerce_evidence_query",
    )
    assert captured["config"].max_tool_rounds == 2
    assert captured["config"].max_tool_calls == 3


def test_build_subagent_executor_rejects_budget_expansion(monkeypatch):
    from deerflow.subagents.config import SubagentConfig

    config = SubagentConfig(
        name="analyst",
        description="分析",
        model="fixed-model",
        max_tool_rounds=2,
    )
    runtime = SimpleNamespace(
        context={"thread_id": "thread-1", "user_id": "user-42"},
        config={"metadata": {"model_name": "parent-model"}},
        state={"sandbox": None, "thread_data": None},
    )
    monkeypatch.setattr(tool_module, "get_subagent_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(tool_module, "get_available_subagent_names", lambda *args, **kwargs: ["analyst"])

    with pytest.raises(ValueError, match="exceeds the Subagent Profile budget"):
        tool_module._build_subagent_executor(
            runtime,
            "analyst",
            requested_max_tool_rounds=3,
        )


@pytest.mark.anyio
async def test_wait_task_returns_structured_terminal_result(components):
    task_runtime, _manager, results, _cancelled, _executors = components
    runtime = _Runtime(task_runtime)
    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="call-spawn-1",
    )
    results["call-spawn-1"].status = _Status.COMPLETED
    results["call-spawn-1"].result = "承运运输阶段贡献最大"

    raw = await _invoke(
        tool_module.wait_task_tool,
        runtime=runtime,
        task_ids=["call-spawn-1"],
        mode="all",
        timeout_seconds=1,
    )

    payload = json.loads(raw)
    assert payload["ready"] is True
    assert payload["tasks"][0]["status"] == "completed"
    assert payload["tasks"][0]["result"]["output"] == "承运运输阶段贡献最大"
    assert "unknown_task_ids" not in payload
    assert "known_tasks" not in payload

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_wait_task_reports_persisted_subagent_usage_to_parent_journal(
    components,
):
    task_runtime, _manager, results, _cancelled, _executors = components

    class _Recorder:
        def __init__(self):
            self.records = []

        def record_external_llm_usage_records(self, records):
            self.records.extend(records)

    recorder = _Recorder()
    runtime = _Runtime(task_runtime)
    runtime.config["callbacks"] = [recorder]
    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="usage-task",
    )
    results["usage-task"].status = _Status.COMPLETED
    results["usage-task"].result = "承运运输阶段变化更明显"
    results["usage-task"].token_usage_records = [
        {
            "source_run_id": "provider-run-1",
            "caller": "subagent:analyst",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        }
    ]

    await _invoke(
        tool_module.wait_task_tool,
        runtime=runtime,
        task_ids=["usage-task"],
        mode="all",
        timeout_seconds=1,
    )

    assert recorder.records == results["usage-task"].token_usage_records

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "task_ids", "expected_ready"),
    [
        ("one", ["task-typo"], False),
        ("any", ["task-typo", "task-known"], True),
        ("all", ["task-typo", "task-known"], False),
    ],
)
async def test_wait_task_returns_authorized_known_tasks_when_an_id_is_unknown(
    components,
    mode,
    task_ids,
    expected_ready,
):
    task_runtime, manager, _results, _cancelled, _executors = components
    runtime = _Runtime(task_runtime)
    await manager.create(
        task_id="task-known",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="已知任务",
        context_packet=tool_module.ContextPacket(goal="返回已知任务快照"),
    )
    await manager.transition("task-known", SubagentTaskStatus.running)
    await manager.transition(
        "task-known",
        SubagentTaskStatus.completed,
        result={"output": "已完成"},
    )

    raw = await _invoke(
        tool_module.wait_task_tool,
        runtime=runtime,
        task_ids=task_ids,
        mode=mode,
        timeout_seconds=0,
    )

    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["ready"] is expected_ready
    assert payload["unknown_task_ids"] == ["task-typo"]
    assert payload["known_task_ids"] == ["task-known"]
    assert payload["known_tasks"][0]["task_id"] == "task-known"
    assert payload["known_tasks"][0]["status"] == "completed"
    assert all(task["task_id"] != "task-typo" for task in payload["tasks"])

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_wait_task_recovery_never_discloses_tasks_from_another_run(components):
    task_runtime, manager, _results, _cancelled, _executors = components
    await manager.create(
        task_id="other-run-task",
        thread_id="thread-1",
        run_id="run-2",
        user_id="user-1",
        subagent_type="analyst",
        description="其他 Run",
        context_packet=tool_module.ContextPacket(goal="不得泄露"),
    )

    raw = await _invoke(
        tool_module.wait_task_tool,
        runtime=_Runtime(task_runtime),
        task_ids=["task-typo"],
        mode="one",
        timeout_seconds=0,
    )
    payload = json.loads(raw)

    assert payload["known_task_ids"] == []
    assert payload["known_tasks"] == []
    with pytest.raises(PermissionError, match="current run"):
        await _invoke(
            tool_module.wait_task_tool,
            runtime=_Runtime(task_runtime),
            task_ids=["other-run-task"],
            mode="one",
            timeout_seconds=0,
        )

    await task_runtime.shutdown(reason="test cleanup")


def test_wait_task_schema_rejects_timeout_outside_runtime_bounds():
    coroutine = tool_module.wait_task_tool.coroutine
    assert coroutine is not None
    timeout_annotation = get_type_hints(
        coroutine,
        include_extras=True,
    )["timeout_seconds"]
    adapter = TypeAdapter(timeout_annotation)

    with pytest.raises(ValueError):
        adapter.validate_python(61)
    assert adapter.validate_python(60) == 60


def test_spawn_task_schema_exposes_total_tool_call_budget_bounds():
    schema = tool_module.spawn_task_tool.tool_call_schema.model_json_schema()
    integer_branch = schema["properties"]["max_tool_calls"]["anyOf"][0]

    assert integer_branch["minimum"] == 1
    assert integer_branch["maximum"] == 256


@pytest.mark.anyio
async def test_follow_up_creates_cross_run_child_with_explicit_parent_snapshot(components):
    task_runtime, manager, results, _cancelled, executors = components
    first_runtime = _Runtime(task_runtime, run_id="run-1")
    await _invoke(
        tool_module.spawn_task_tool,
        runtime=first_runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="parent-task",
    )
    results["parent-task"].status = _Status.COMPLETED
    results["parent-task"].result = "承运运输阶段贡献最大"
    await task_runtime.wait(["parent-task"], mode=tool_module.TaskWaitMode.all, timeout_seconds=1)

    raw = await _invoke(
        tool_module.follow_up_task_tool,
        runtime=_Runtime(task_runtime, run_id="run-2"),
        parent_task_id="parent-task",
        description="核查区域差异",
        prompt="进一步检查华东区域是否集中恶化",
        subagent_type=None,
        tool_call_id="child-task",
    )

    payload = json.loads(raw)
    child = await manager.get("child-task")
    assert payload["task"]["parent_task_id"] == "parent-task"
    assert child.run_id == "run-2"
    assert child.context_packet.source_refs == ("task:parent-task",)
    assert child.context_packet.metadata["source_snapshots"]["task:parent-task"]["result"]["output"] == "承运运输阶段贡献最大"
    assert "进一步检查华东区域是否集中恶化" in executors[-1].calls[0][0]
    assert "承运运输阶段贡献最大" in executors[-1].calls[0][0]

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_verifier_spawn_requires_and_snapshots_explicit_task_sources(components):
    task_runtime, manager, results, _cancelled, _executors = components
    runtime = _Runtime(task_runtime)

    with pytest.raises(ValueError, match="verifier.*task:<task_id>"):
        await _invoke(
            tool_module.spawn_task_tool,
            runtime=runtime,
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=None,
            tool_call_id="verifier-without-source",
        )

    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="source-task",
    )
    results["source-task"].status = _Status.COMPLETED
    results["source-task"].result = "承运运输阶段变化更明显"
    await task_runtime.wait(
        ["source-task"],
        mode=tool_module.TaskWaitMode.all,
        timeout_seconds=1,
    )

    raw = await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="独立核验",
        prompt="使用 fresh context 重新计算并核验",
        subagent_type="verifier",
        source_refs=["task:source-task"],
        tool_call_id="verifier-task",
    )

    payload = json.loads(raw)
    verifier = await manager.get("verifier-task")
    snapshot = verifier.context_packet.metadata["source_snapshots"]["task:source-task"]
    assert payload["task"]["status"] == "running"
    assert verifier.context_packet.source_refs == ("task:source-task",)
    assert snapshot["status"] == "completed"
    assert snapshot["result"]["output"] == "承运运输阶段变化更明显"

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_verifier_spawn_normalizes_exact_terminal_task_id_source(components):
    task_runtime, manager, results, _cancelled, _executors = components
    runtime = _Runtime(task_runtime)
    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="source-task",
    )
    results["source-task"].status = _Status.COMPLETED
    results["source-task"].result = "承运运输阶段变化更明显"
    await task_runtime.wait(
        ["source-task"],
        mode=tool_module.TaskWaitMode.all,
        timeout_seconds=1,
    )

    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="独立核验",
        prompt="使用 fresh context 重新计算并核验",
        subagent_type="verifier",
        source_refs=["source-task"],
        tool_call_id="verifier-task",
    )

    verifier = await manager.get("verifier-task")
    assert verifier.context_packet.source_refs == ("task:source-task",)
    assert verifier.context_packet.metadata["source_snapshots"]["task:source-task"]["result"]["output"] == "承运运输阶段变化更明显"

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
@pytest.mark.parametrize("source_task_kind", ["missing", "running", "other-run"])
async def test_verifier_bare_task_id_normalization_fails_closed(
    components,
    source_task_kind,
):
    task_runtime, manager, _results, _cancelled, _executors = components
    task_id = f"{source_task_kind}-task"
    if source_task_kind != "missing":
        await manager.create(
            task_id=task_id,
            thread_id="thread-1",
            run_id="run-2" if source_task_kind == "other-run" else "run-1",
            user_id="user-1",
            subagent_type="analyst",
            description="候选来源任务",
            context_packet=tool_module.ContextPacket(goal="候选来源"),
        )
        await manager.transition(task_id, SubagentTaskStatus.running)

    with pytest.raises(ValueError, match="verifier.*task:<task_id>|still running"):
        await _invoke(
            tool_module.spawn_task_tool,
            runtime=_Runtime(task_runtime),
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=[task_id],
            tool_call_id=f"verifier-{source_task_kind}",
        )

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_verifier_explicit_task_source_rejects_another_run(components):
    task_runtime, manager, _results, _cancelled, _executors = components
    await manager.create(
        task_id="other-run-source",
        thread_id="thread-1",
        run_id="run-2",
        user_id="user-1",
        subagent_type="analyst",
        description="其他 Run 来源",
        context_packet=tool_module.ContextPacket(goal="不得用于当前 Run 核验"),
    )
    await manager.transition("other-run-source", SubagentTaskStatus.running)
    await manager.transition(
        "other-run-source",
        SubagentTaskStatus.completed,
        result={"output": "其他 Run 结果"},
    )

    with pytest.raises(PermissionError, match="current run"):
        await _invoke(
            tool_module.spawn_task_tool,
            runtime=_Runtime(task_runtime),
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=["task:other-run-source"],
            tool_call_id="verifier-other-run-explicit",
        )

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_verifier_rejects_failed_source_task(components):
    task_runtime, manager, _results, _cancelled, _executors = components
    await manager.create(
        task_id="failed-source",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="失败的来源任务",
        context_packet=tool_module.ContextPacket(goal="无法形成可核验结果"),
    )
    await manager.transition("failed-source", SubagentTaskStatus.running)
    await manager.transition(
        "failed-source",
        SubagentTaskStatus.failed,
        error={"message": "分析失败"},
    )

    with pytest.raises(ValueError, match="must be completed"):
        await _invoke(
            tool_module.spawn_task_tool,
            runtime=_Runtime(task_runtime),
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=["task:failed-source"],
            tool_call_id="verifier-failed-source",
        )

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_cancel_and_resume_tools_control_the_same_durable_task(components):
    task_runtime, manager, _results, cancelled, _executors = components
    runtime = _Runtime(task_runtime)
    await _invoke(
        tool_module.spawn_task_tool,
        runtime=runtime,
        description="分析履约异常",
        prompt="定位原因",
        subagent_type="analyst",
        tool_call_id="task-1",
    )
    cancelled_raw = await _invoke(
        tool_module.cancel_task_tool,
        runtime=runtime,
        task_id="task-1",
        reason="不再需要",
    )
    assert json.loads(cancelled_raw)["task"]["status"] == "cancelled"
    assert cancelled == ["task-1"]

    await manager.create(
        task_id="task-2",
        thread_id="thread-1",
        run_id="run-1",
        user_id="user-1",
        subagent_type="analyst",
        description="继续分析",
        context_packet=(await manager.get("task-1")).context_packet.model_copy(
            update={"goal": "继续分析"},
        ),
        max_attempts=2,
    )
    await manager.transition("task-2", SubagentTaskStatus.running)
    await manager.transition(
        "task-2",
        SubagentTaskStatus.blocked,
        wait_reason="worker lost",
    )
    resumed_raw = await _invoke(
        tool_module.resume_task_tool,
        runtime=runtime,
        task_id="task-2",
    )

    assert json.loads(resumed_raw)["task"]["status"] == "running"
    assert (await manager.get("task-2")).attempt == 2

    await task_runtime.shutdown(reason="test cleanup")


@pytest.mark.anyio
async def test_task_tools_reject_cross_thread_access(components):
    task_runtime, manager, _results, _cancelled, _executors = components
    await manager.create(
        task_id="foreign-task",
        thread_id="thread-2",
        run_id="run-2",
        user_id="user-1",
        subagent_type="analyst",
        description="foreign",
        context_packet=tool_module.ContextPacket(goal="foreign"),
    )

    with pytest.raises(PermissionError, match="does not belong"):
        await _invoke(
            tool_module.wait_task_tool,
            runtime=_Runtime(task_runtime),
            task_ids=["foreign-task"],
            mode="one",
            timeout_seconds=0,
        )

    await task_runtime.shutdown(reason="test cleanup")

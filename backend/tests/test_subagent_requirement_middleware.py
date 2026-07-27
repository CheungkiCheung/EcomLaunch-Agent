import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.subagent_requirement_middleware import (
    SubagentRequirementMiddleware,
    _subagent_tasks,
)


def _runtime(run_id: str = "run-1"):
    runtime = MagicMock()
    runtime.context = {"thread_id": "thread-1", "run_id": run_id}
    return runtime


def _tool_call(name: str, call_id: str, **args):
    return {"name": name, "id": call_id, "args": args}


def _tool_exchange(name: str, call_id: str, **args):
    return [
        AIMessage(content="", tool_calls=[_tool_call(name, call_id, **args)]),
        ToolMessage(content='{"ok": true}', tool_call_id=call_id),
    ]


def _task_snapshot(
    task_id: str,
    subagent_type: str,
    status: str,
    *,
    source_refs: list[str] | None = None,
):
    return {
        "task_id": task_id,
        "subagent_type": subagent_type,
        "status": status,
        "source_refs": source_refs or [],
    }


def _wait_exchange(call_id: str, *tasks: dict):
    return [
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "wait_task",
                    call_id,
                    task_ids=[task["task_id"] for task in tasks],
                    mode="all",
                )
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": True,
                    "ready": True,
                    "timed_out": False,
                    "tasks": list(tasks),
                }
            ),
            tool_call_id=call_id,
        ),
    ]


def test_externalized_wait_task_control_metadata_updates_terminal_snapshot():
    messages = [
        HumanMessage(content="调查异常"),
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    "spawn-analyst",
                    description="分析履约",
                    prompt="计算指标",
                    subagent_type="analyst",
                    skills=["fulfillment-investigation"],
                    tools=["commerce_compare_windows"],
                    max_tool_rounds=2,
                    max_tool_calls=2,
                )
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": True,
                    "task": _task_snapshot("task-analyst", "analyst", "running"),
                }
            ),
            tool_call_id="spawn-analyst",
        ),
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "wait_task",
                    "wait-analyst",
                    task_ids=["task-analyst"],
                    mode="all",
                )
            ],
        ),
        ToolMessage(
            content="externalized preview",
            tool_call_id="wait-analyst",
            additional_kwargs={
                "durable_task_control": {
                    "ok": True,
                    "ready": True,
                    "tasks": [
                        _task_snapshot(
                            "task-analyst",
                            "analyst",
                            "completed",
                        )
                    ],
                }
            },
        ),
    ]

    tasks = _subagent_tasks(messages)

    assert tasks[0]["task_id"] == "task-analyst"
    assert tasks[0]["status"] == "completed"


def test_simple_final_answer_does_not_force_a_subagent():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )

    result = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="这列是什么意思？"),
                AIMessage(content="这是订单批准时间。"),
            ]
        },
        _runtime(),
    )

    assert result is None


def test_complex_tool_chain_jumps_back_before_unverified_final_answer():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        AIMessage(content="最终结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result == {"jump_to": "model"}


def test_requirement_reminder_is_transient_and_explains_fresh_verifier_lineage():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    runtime = _runtime()
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        AIMessage(content="最终结论"),
    ]
    assert middleware.after_model({"messages": messages}, runtime) == {"jump_to": "model"}

    captured = {}

    def handler(request):
        captured["messages"] = request.messages
        return MagicMock()

    request = MagicMock()
    request.messages = messages
    request.runtime = runtime
    request.override.side_effect = lambda **changes: MagicMock(
        messages=changes["messages"],
        runtime=runtime,
    )

    middleware.wrap_model_call(request, handler)

    reminder = captured["messages"][-1]
    assert isinstance(reminder, HumanMessage)
    assert reminder.name == "subagent_requirement_reminder"
    assert reminder.additional_kwargs["hide_from_ui"] is True
    assert "spawn_task" in reminder.content
    assert "wait_task" in reminder.content
    assert "verifier" in reminder.content
    assert "task:<task_id>" in reminder.content


def test_force_dispatch_recovery_exposes_only_spawn_task_with_exact_tool_choice():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("analyst", "verifier"),
        recovery_mode="force_dispatch",
    )
    runtime = _runtime()
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_ingest_uploads", "ingest"),
        *_tool_exchange("commerce_list_entities", "entities"),
        AIMessage(content="准备回答"),
    ]
    assert middleware.after_model({"messages": messages}, runtime) == {"jump_to": "model"}

    request = MagicMock()
    request.messages = messages
    request.runtime = runtime
    request.tools = [
        SimpleNamespace(name="commerce_list_entities"),
        SimpleNamespace(name="spawn_task"),
        SimpleNamespace(name="wait_task"),
    ]
    request.model = SimpleNamespace(extra_body={"thinking": {"type": "enabled"}, "preserve": True})
    request.model_settings = {"timeout": 30}
    request.override.return_value = "forced-request"
    handler = MagicMock(return_value="response")

    assert middleware.wrap_model_call(request, handler) == "response"
    override = request.override.call_args.kwargs
    assert [tool.name for tool in override["tools"]] == ["spawn_task"]
    assert override["tool_choice"] == {
        "type": "function",
        "function": {"name": "spawn_task"},
    }
    assert override["model_settings"] == {
        "timeout": 30,
        "extra_body": {
            "thinking": {"type": "disabled"},
            "preserve": True,
        },
    }
    reminder = override["messages"][-1]
    assert reminder.name == "subagent_requirement_force_dispatch"
    assert reminder.additional_kwargs["missing_subagent_types"] == [
        "analyst",
        "verifier",
    ]
    assert reminder.additional_kwargs["expected_control_tool"] == "spawn_task"
    handler.assert_called_once_with("forced-request")


def test_force_dispatch_recovery_switches_to_wait_for_active_task():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("analyst", "verifier"),
        recovery_mode="force_dispatch",
    )
    runtime = _runtime()
    base = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_ingest_uploads", "ingest"),
        *_tool_exchange("commerce_list_entities", "entities"),
        AIMessage(content="准备回答"),
    ]
    middleware.after_model({"messages": base}, runtime)
    running_task = _task_snapshot("task-analyst", "analyst", "running")
    messages = [
        *base,
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    "spawn-analyst",
                    description="核心分析",
                    prompt="计算指标",
                    subagent_type="analyst",
                )
            ],
        ),
        ToolMessage(
            content=json.dumps({"ok": True, "task": running_task}),
            tool_call_id="spawn-analyst",
        ),
    ]
    request = MagicMock(
        messages=messages,
        runtime=runtime,
        tools=[
            SimpleNamespace(name="spawn_task"),
            SimpleNamespace(name="wait_task"),
        ],
        model=SimpleNamespace(extra_body={"thinking": {"type": "enabled"}}),
        model_settings={},
    )
    request.override.return_value = "wait-only"
    handler = MagicMock(return_value="response")

    middleware.wrap_model_call(request, handler)

    override = request.override.call_args.kwargs
    assert [tool.name for tool in override["tools"]] == ["wait_task"]
    assert override["tool_choice"]["function"]["name"] == "wait_task"


def test_force_dispatch_retries_wrong_control_action_then_fails_bounded():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("analyst", "verifier"),
        recovery_mode="force_dispatch",
        max_recovery_attempts=1,
    )
    runtime = _runtime()
    base = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_ingest_uploads", "ingest"),
        *_tool_exchange("commerce_list_entities", "entities"),
        AIMessage(content="准备回答"),
    ]
    middleware.after_model({"messages": base}, runtime)
    wrong = AIMessage(
        content="",
        tool_calls=[_tool_call("commerce_list_entities", "wrong-direct")],
    )

    retry = middleware.after_model(
        {"messages": [*base, wrong]},
        runtime,
    )

    assert retry is not None
    assert retry["jump_to"] == "model"
    assert retry["messages"][0].tool_calls == []
    assert retry["messages"][0].additional_kwargs["subagent_gate_status"] == "force_dispatch_retry"

    blocked = middleware.after_model(
        {"messages": [*base, wrong, AIMessage(content="仍然不派工")]},
        runtime,
    )
    assert blocked is not None
    assert "未通过独立子智能体核验" in blocked["messages"][0].content


def test_analyst_only_does_not_satisfy_required_verifier():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        *_tool_exchange(
            "spawn_task",
            "task-analyst",
            description="独立分析",
            prompt="重算指标",
            subagent_type="analyst",
        ),
        AIMessage(content="最终结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result == {"jump_to": "model"}


def test_dispatched_but_unfinished_verifier_does_not_allow_final_answer():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        *_tool_exchange(
            "spawn_task",
            "task-verifier",
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=["task:task-analyst"],
        ),
        AIMessage(content="经独立核验后的最终结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result == {"jump_to": "model"}


def test_completed_verifier_with_current_run_task_lineage_allows_final_answer():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    analyst = _task_snapshot("task-analyst", "analyst", "completed")
    verifier = _task_snapshot(
        "task-verifier",
        "verifier",
        "completed",
        source_refs=["task:task-analyst"],
    )
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        *_tool_exchange(
            "spawn_task",
            "task-analyst",
            description="独立分析",
            prompt="重算指标",
            subagent_type="analyst",
        ),
        *_wait_exchange("wait-analyst", analyst),
        *_tool_exchange(
            "spawn_task",
            "task-verifier",
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=["task:task-analyst"],
        ),
        *_wait_exchange("wait-verifier", verifier),
        AIMessage(content="经独立核验后的最终结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result is None


def test_failed_verifier_does_not_allow_final_answer():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    analyst = _task_snapshot("task-analyst", "analyst", "completed")
    verifier = _task_snapshot(
        "task-verifier",
        "verifier",
        "failed",
        source_refs=["task:task-analyst"],
    )
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        *_wait_exchange("wait-analyst", analyst),
        *_tool_exchange(
            "spawn_task",
            "task-verifier",
            description="独立核验",
            prompt="核验关键结论",
            subagent_type="verifier",
            source_refs=["task:task-analyst"],
        ),
        *_wait_exchange("wait-verifier", verifier),
        AIMessage(content="未经成功核验的最终结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result == {"jump_to": "model"}


def test_completed_verifier_without_task_lineage_does_not_allow_final_answer():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    verifier = _task_snapshot("task-verifier", "verifier", "completed")
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        *_wait_exchange("wait-verifier", verifier),
        AIMessage(content="缺少前置任务引用的核验结论"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime())

    assert result == {"jump_to": "model"}


def test_previous_turn_tool_chain_does_not_make_current_simple_turn_complex():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    messages = [
        HumanMessage(content="上一轮复杂诊断"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        AIMessage(content="上一轮回答"),
        HumanMessage(content="现在只解释一列是什么意思"),
        AIMessage(content="这是订单批准时间。"),
    ]

    result = middleware.after_model({"messages": messages}, _runtime("run-2"))

    assert result is None


def test_ignored_requirement_fails_closed_after_one_reminder():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
        max_reminders=1,
    )
    runtime = _runtime()
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        AIMessage(content="第一次未经核验的最终结论"),
    ]
    assert middleware.after_model({"messages": messages}, runtime) == {"jump_to": "model"}

    ignored = AIMessage(
        content="第二次仍未核验",
        response_metadata={"finish_reason": "stop"},
    )
    blocked = middleware.after_model(
        {"messages": [*messages, ignored]},
        runtime,
    )

    assert blocked is not None
    replacement = blocked["messages"][0]
    assert replacement.id == ignored.id
    assert replacement.tool_calls == []
    assert "未通过独立子智能体核验" in replacement.content
    assert replacement.additional_kwargs["subagent_gate_status"] == "blocked"


def test_run_state_is_cleared_after_agent_finishes():
    middleware = SubagentRequirementMiddleware(
        complexity_tool_call_threshold=2,
        required_subagent_types=("verifier",),
    )
    runtime = _runtime()
    messages = [
        HumanMessage(content="诊断延迟原因"),
        *_tool_exchange("commerce_metric_snapshot", "metric-1"),
        *_tool_exchange("commerce_compare_windows", "compare-1"),
        AIMessage(content="最终结论"),
    ]
    assert middleware.after_model({"messages": messages}, runtime) == {"jump_to": "model"}

    middleware.after_agent({"messages": messages}, runtime)

    assert middleware.reminder_count(runtime) == 0

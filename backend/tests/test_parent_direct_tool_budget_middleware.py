"""Parent direct-work Tool budget and delegation transition contracts."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.parent_direct_tool_budget_middleware import (
    ParentDirectToolBudgetMiddleware,
)


def _runtime():
    return SimpleNamespace(
        context={"thread_id": "thread-1", "run_id": "run-1"}
    )


def _tool_call(name: str, call_id: str, args: dict | None = None):
    return {"name": name, "id": call_id, "args": args or {}}


def test_parent_budget_keeps_only_durable_control_tools_until_verifier_completes():
    middleware = ParentDirectToolBudgetMiddleware(
        max_direct_tool_calls=2,
        required_subagent_types=("verifier",),
    )
    request = MagicMock()
    request.runtime = _runtime()
    request.messages = [
        HumanMessage(content="分析异常"),
        AIMessage(
            content="",
            tool_calls=[
                _tool_call("commerce_dataset_profile", "profile"),
                _tool_call("commerce_compare_windows", "compare"),
            ],
        ),
        ToolMessage(content='{"ok": true}', tool_call_id="profile"),
        ToolMessage(content='{"ok": true}', tool_call_id="compare"),
    ]
    request.tools = [
        SimpleNamespace(name="commerce_evidence_query"),
        SimpleNamespace(name="spawn_task"),
        SimpleNamespace(name="wait_task"),
        SimpleNamespace(name="write_todos"),
    ]
    request.model = SimpleNamespace(
        extra_body={"thinking": {"type": "enabled"}, "preserve": True}
    )
    request.model_settings = {"timeout": 30}
    request.override.return_value = "delegation-only"
    handler = MagicMock(return_value="response")

    result = middleware.wrap_model_call(request, handler)

    assert result == "response"
    override = request.override.call_args.kwargs
    assert [tool.name for tool in override["tools"]] == [
        "spawn_task",
        "wait_task",
        "write_todos",
    ]
    assert override["tool_choice"] == "required"
    assert override["model_settings"] == {
        "timeout": 30,
        "extra_body": {
            "thinking": {"type": "disabled"},
            "preserve": True,
        },
    }
    assert override["messages"][-1].name == "parent_direct_tool_budget"
    assert (
        override["messages"][-1].additional_kwargs["dispatch_model_mode"]
        == "tool_control_without_thinking"
    )
    assert "先完成最小分析任务" in override["messages"][-1].content
    handler.assert_called_once_with("delegation-only")


def test_parent_budget_removes_all_tools_after_lineaged_verifier_completes():
    middleware = ParentDirectToolBudgetMiddleware(
        max_direct_tool_calls=1,
        required_subagent_types=("verifier",),
    )
    verifier_call = _tool_call(
        "spawn_task",
        "spawn-verifier",
        {
            "subagent_type": "verifier",
            "source_refs": ["task:analysis-1"],
        },
    )
    request = MagicMock()
    request.runtime = _runtime()
    request.messages = [
        HumanMessage(content="分析异常"),
        AIMessage(
            content="",
            tool_calls=[_tool_call("commerce_compare_windows", "compare")],
        ),
        ToolMessage(content='{"ok": true}', tool_call_id="compare"),
        AIMessage(content="", tool_calls=[verifier_call]),
        ToolMessage(
            content=(
                '{"ok": true, "task": {'
                '"task_id": "verify-1", '
                '"subagent_type": "verifier", '
                '"status": "completed", '
                '"source_refs": ["task:analysis-1"]}}'
            ),
            tool_call_id="spawn-verifier",
        ),
    ]
    request.tools = [
        SimpleNamespace(name="commerce_evidence_query"),
        SimpleNamespace(name="spawn_task"),
        SimpleNamespace(name="wait_task"),
    ]
    request.override.return_value = "synthesis-only"
    handler = MagicMock(return_value="response")

    result = middleware.wrap_model_call(request, handler)

    assert result == "response"
    override = request.override.call_args.kwargs
    assert override["tools"] == []
    assert override["messages"][-1].name == "parent_direct_tool_budget_stop"
    assert "立即综合" in override["messages"][-1].content
    handler.assert_called_once_with("synthesis-only")


def test_parent_budget_truncates_parallel_direct_calls_but_preserves_dispatch():
    middleware = ParentDirectToolBudgetMiddleware(
        max_direct_tool_calls=2,
        required_subagent_types=("verifier",),
    )
    last = AIMessage(
        content="",
        tool_calls=[
            _tool_call("commerce_dataset_profile", "profile-2"),
            _tool_call("commerce_compare_windows", "compare-2"),
            _tool_call("spawn_task", "spawn-analysis", {"subagent_type": "analyst"}),
        ],
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("commerce_capabilities", "capabilities")
                ],
            ),
            ToolMessage(content='{"ok": true}', tool_call_id="capabilities"),
            last,
        ]
    }

    update = middleware.after_model(state, _runtime())

    assert update is not None
    kept = update["messages"][0].tool_calls
    assert [call["name"] for call in kept] == [
        "commerce_dataset_profile",
        "spawn_task",
    ]

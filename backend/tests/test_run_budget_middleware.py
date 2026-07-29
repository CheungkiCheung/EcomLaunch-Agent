from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.run_budget_middleware import RUN_BUDGET_CONTEXT_KEY, RunBudgetMiddleware
from deerflow.config.agent_run_budget_config import AgentRunBudgetConfig


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(context={"thread_id": "thread-1"})


def _tool_call(name: str, call_id: str) -> dict:
    return {"name": name, "id": call_id, "args": {}}


def test_before_agent_initializes_a_fresh_run_budget_context() -> None:
    runtime = _runtime()
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=8,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
        )
    )

    middleware.before_agent({"messages": [HumanMessage(content="start")]}, runtime)

    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0
    assert budget_state["subagent_types_started"] == set()
    assert budget_state["deadline_monotonic"] > budget_state["started_at_monotonic"]
    assert budget_state["config"]["max_subagent_calls"] == 4


def test_model_call_budget_only_counts_the_current_user_turn() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=2,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    current = AIMessage(
        content="",
        tool_calls=[_tool_call("web_search", "search-2")],
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "search-2",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": "{}"},
                }
            ]
        },
        response_metadata={"finish_reason": "tool_calls"},
    )
    state = {
        "messages": [
            HumanMessage(content="old question"),
            AIMessage(content="old answer"),
            HumanMessage(content="new question"),
            AIMessage(content="first current-turn call"),
            current,
        ]
    }

    update = middleware.after_model(state, runtime)

    assert update is not None
    stopped = update["messages"][0]
    assert stopped.tool_calls == []
    assert "执行预算" in stopped.content
    assert "tool_calls" not in stopped.additional_kwargs
    assert stopped.response_metadata["finish_reason"] == "stop"


def test_token_budget_includes_usage_merged_from_subagents() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=100,
            max_execution_seconds=240,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    dispatch = AIMessage(
        content="",
        tool_calls=[_tool_call("task", "task-1")],
        usage_metadata={"input_tokens": 80, "output_tokens": 30, "total_tokens": 110},
    )
    current = AIMessage(content="", tool_calls=[_tool_call("write_file", "write-1")])
    state = {
        "messages": [
            HumanMessage(content="build pack"),
            dispatch,
            ToolMessage(content="Task Succeeded", tool_call_id="task-1"),
            current,
        ]
    }

    update = middleware.after_model(state, runtime)

    assert update is not None
    assert update["messages"][0].tool_calls == []
    assert "Token" in update["messages"][0].content


def test_budget_does_not_replace_a_completed_final_answer() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=1,
            max_subagent_calls=1,
            max_total_tokens=1,
            max_execution_seconds=1,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    final = AIMessage(
        content="最终结论",
        usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
    )

    assert (
        middleware.after_model(
            {"messages": [HumanMessage(content="question"), final]},
            runtime,
        )
        is None
    )


def test_present_files_is_allowed_as_a_terminal_delivery_tool() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=1,
            max_subagent_calls=1,
            max_total_tokens=1,
            max_execution_seconds=240,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    message = AIMessage(
        content="",
        tool_calls=[
            _tool_call("write_file", "write-1"),
            _tool_call("present_files", "present-1"),
        ],
        usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="question"), message]},
        runtime,
    )

    assert update is not None
    assert [call["name"] for call in update["messages"][0].tool_calls] == ["present_files"]


def test_wrap_model_call_warns_the_model_to_finalize_before_the_hard_limit() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=2,
            max_subagent_calls=0,
            max_total_tokens=100_000,
            max_execution_seconds=60,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    request = MagicMock()
    request.runtime = runtime
    request.messages = [
        HumanMessage(content="research"),
        AIMessage(content="", tool_calls=[_tool_call("web_search", "search-1")]),
        ToolMessage(content="result", tool_call_id="search-1"),
    ]
    request.override = lambda **updates: SimpleNamespace(
        runtime=runtime,
        messages=updates.get("messages", request.messages),
    )
    captured = []

    def handler(updated_request):
        captured.append(updated_request)
        return MagicMock()

    middleware.wrap_model_call(request, handler)

    final_message = captured[0].messages[-1]
    assert isinstance(final_message, HumanMessage)
    assert final_message.name == "run_budget_finalization"
    assert final_message.additional_kwargs["hide_from_ui"] is True
    assert "Do not call more research or drafting tools" in final_message.content

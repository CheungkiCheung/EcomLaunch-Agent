import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.run_budget_middleware import RUN_BUDGET_CONTEXT_KEY, RunBudgetMiddleware, _current_turn_messages
from deerflow.config.agent_run_budget_config import AgentRunBudgetConfig


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(context={"thread_id": "thread-1"})


def _tool_call(name: str, call_id: str, args: dict | None = None) -> dict:
    return {"name": name, "id": call_id, "args": args or {}}


class _FakeRequest:
    def __init__(self, *, runtime: SimpleNamespace, messages: list, tools: list) -> None:
        self.runtime = runtime
        self.messages = messages
        self.tools = tools

    def override(self, **updates):
        return _FakeRequest(
            runtime=self.runtime,
            messages=updates.get("messages", self.messages),
            tools=updates.get("tools", self.tools),
        )


def test_before_agent_initializes_a_fresh_run_budget_context() -> None:
    runtime = _runtime()
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=8,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            allowed_subagent_types=["market-voc-researcher", "offer-architect"],
            subagent_dependencies={"offer-architect": ["market-voc-researcher"]},
            direct_answer_patterns=["最先.*验证"],
            direct_answer_exclude_patterns=["公开数据"],
            complete_workflow_patterns=["Launch Validation Pack"],
            required_completed_subagents=["market-voc-researcher", "offer-architect"],
            compact_write_file_history=True,
            finalize_after_subagent="evidence-checker",
            required_output_files=["evidence-ledger.json", "content-pack.md"],
            auto_present_complete_pack=True,
            require_evidence_checker=True,
            validate_pack_before_evidence=True,
            validate_pack_before_present=True,
        )
    )

    middleware.before_agent({"messages": [HumanMessage(content="start")]}, runtime)

    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    assert budget_state["subagent_calls_started"] == 0
    assert budget_state["subagent_types_started"] == set()
    assert budget_state["subagent_types_completed"] == set()
    assert budget_state["required_output_files_written"] == set()
    assert budget_state["deadline_monotonic"] > budget_state["started_at_monotonic"]
    assert budget_state["config"]["max_subagent_calls"] == 4
    assert budget_state["config"]["allowed_subagent_types"] == ["market-voc-researcher", "offer-architect"]
    assert budget_state["config"]["subagent_dependencies"] == {"offer-architect": ["market-voc-researcher"]}
    assert budget_state["config"]["direct_answer_patterns"] == ["最先.*验证"]
    assert budget_state["config"]["direct_answer_exclude_patterns"] == ["公开数据"]
    assert budget_state["config"]["complete_workflow_patterns"] == ["Launch Validation Pack"]
    assert budget_state["config"]["required_completed_subagents"] == ["market-voc-researcher", "offer-architect"]
    assert budget_state["config"]["compact_write_file_history"] is True
    assert budget_state["config"]["finalize_after_subagent"] == "evidence-checker"
    assert budget_state["config"]["required_output_files"] == ["evidence-ledger.json", "content-pack.md"]
    assert budget_state["config"]["auto_present_complete_pack"] is True
    assert budget_state["config"]["require_evidence_checker"] is True
    assert budget_state["config"]["validate_pack_before_evidence"] is True
    assert budget_state["config"]["validate_pack_before_present"] is True


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


def test_budget_removes_terminal_delivery_when_required_audit_is_incomplete() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=1,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "evidence-checker"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    message = AIMessage(
        content="Let me present the completed Pack.",
        tool_calls=[_tool_call("present_files", "present-1")],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="build pack"), message]},
        runtime,
    )

    assert update is not None
    stopped = update["messages"][0]
    assert stopped.tool_calls == []
    assert stopped.content == "配置的专家流程或证据审计未完成；文件未向用户展示，本次请求以部分完成状态结束。"


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


def test_specialist_finalization_removes_tools_and_requires_final_text() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=2,
            max_subagent_calls=0,
            max_total_tokens=100_000,
            max_execution_seconds=60,
            force_final_text_on_warning=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    request = FakeRequest(
        runtime=runtime,
        messages=[
            HumanMessage(content="research"),
            AIMessage(content="", tool_calls=[_tool_call("web_search", "search-1")]),
            ToolMessage(content="result", tool_call_id="search-1"),
        ],
        tools=[SimpleNamespace(name="web_search"), SimpleNamespace(name="web_fetch")],
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert captured[0].tools == []
    final_message = captured[0].messages[-1]
    assert final_message.name == "run_budget_finalization"
    assert "No tools are available" in final_message.content


def test_first_candidate_preflight_failure_allows_one_revision_then_only_audit() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["terminal_preflight_failures"] = 1

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    tools = [
        SimpleNamespace(name="read_file"),
        SimpleNamespace(name="write_file"),
        SimpleNamespace(name="str_replace"),
        SimpleNamespace(name="task"),
        SimpleNamespace(name="present_files"),
    ]
    request = FakeRequest(runtime=runtime, messages=[HumanMessage(content="build pack")], tools=tools)
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["write_file", "str_replace"]
    assert captured[0].messages[-1].name == "candidate_preflight_revision"

    middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="fix", tool_calls=[_tool_call("str_replace", "replace-1")]),
            ]
        },
        runtime,
    )
    captured.clear()
    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["task"]
    assert captured[0].messages[-1].name == "candidate_preflight_audit"


def test_wrap_model_call_forces_configured_short_question_to_one_no_tool_answer() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            direct_answer_patterns=["最先.*验证"],
            direct_answer_exclude_patterns=["公开数据"],
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    request = MagicMock()
    request.runtime = runtime
    request.messages = [HumanMessage(content="最先应该验证哪一个假设？")]
    request.tools = [SimpleNamespace(name="web_search"), SimpleNamespace(name="task")]
    request.override = lambda **updates: SimpleNamespace(
        runtime=runtime,
        messages=updates.get("messages", request.messages),
        tools=updates.get("tools", request.tools),
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert captured[0].tools == []
    final_message = captured[0].messages[-1]
    assert isinstance(final_message, HumanMessage)
    assert final_message.name == "direct_answer_execution"
    assert final_message.additional_kwargs["hide_from_ui"] is True
    assert "without tools" in final_message.content


def test_direct_answer_exclusion_keeps_tools_for_explicit_public_research() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            direct_answer_patterns=["最先.*验证"],
            direct_answer_exclude_patterns=["公开数据"],
        )
    )

    assert middleware._is_direct_answer_request([HumanMessage(content="用公开数据判断最先验证哪个假设")]) is False


def test_wrap_model_call_compacts_large_historical_write_file_payloads() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            compact_write_file_history=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    large_content = "x" * 2000
    raw_arguments = '{"file_path":"/mnt/user-data/outputs/report.md","content":"' + large_content + '"}'
    write_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"file_path": "/mnt/user-data/outputs/report.md", "content": large_content},
                "id": "write-1",
                "type": "tool_call",
            }
        ],
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "write-1",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": raw_arguments},
                }
            ]
        },
    )
    pending_content = "y" * 1800
    pending_write = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"path": "/mnt/user-data/outputs/pending.csv", "content": pending_content},
                "id": "write-pending",
                "type": "tool_call",
            }
        ],
    )
    request = MagicMock()
    request.runtime = runtime
    request.messages = [
        HumanMessage(content="build pack"),
        write_message,
        ToolMessage(content="File written", tool_call_id="write-1"),
        pending_write,
    ]
    request.tools = []
    request.override = lambda **updates: SimpleNamespace(
        runtime=runtime,
        messages=updates.get("messages", request.messages),
        tools=updates.get("tools", request.tools),
        override=request.override,
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    compacted_write = captured[0].messages[1]
    assert "content" not in compacted_write.tool_calls[0]["args"]
    assert compacted_write.tool_calls[0]["args"]["file_path"] == "/mnt/user-data/outputs/report.md"
    raw_compacted = compacted_write.additional_kwargs["tool_calls"][0]["function"]["arguments"]
    assert large_content not in raw_compacted
    assert "content" not in json.loads(raw_compacted)
    assert captured[0].messages[-1].name == "compacted_file_history"
    assert "Successful writes:" in captured[0].messages[-1].content
    assert '"path":"/mnt/user-data/outputs/report.md"' in captured[0].messages[-1].content
    assert '"bytes":2000' in captured[0].messages[-1].content
    assert '"status":"success"' in captured[0].messages[-1].content
    assert "[compacted" not in captured[0].messages[-1].content
    assert "Do not reread" in captured[0].messages[-1].content
    assert captured[0].messages[3].tool_calls[0]["args"]["content"] == pending_content


def test_complete_pack_ready_limits_next_model_call_to_presentation() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "asset-studio"}
    budget_state["required_output_files_ready"] = True
    request = _FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[
            SimpleNamespace(name="read_file"),
            SimpleNamespace(name="grep"),
            SimpleNamespace(name="write_file"),
            SimpleNamespace(name="present_files"),
        ],
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["present_files"]
    assert captured[0].messages[-1].name == "complete_pack_presentation"
    assert "Do not read or grep" in captured[0].messages[-1].content


def test_started_complete_pack_assembly_removes_manual_inspection_tools() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "asset-studio"}
    budget_state["required_output_files_written"] = {"a.md"}
    budget_state["required_output_files_missing"] = ["b.csv"]
    budget_state["required_output_files_ready"] = False
    request = _FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[
            SimpleNamespace(name="read_file"),
            SimpleNamespace(name="grep"),
            SimpleNamespace(name="write_file"),
            SimpleNamespace(name="str_replace"),
            SimpleNamespace(name="present_files"),
            SimpleNamespace(name="task"),
        ],
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["write_file", "str_replace"]
    assert captured[0].messages[-1].name == "complete_pack_assembly"
    assert "Do not read, grep" in captured[0].messages[-1].content


def test_started_complete_pack_assembly_reengages_after_toolless_intent() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "asset-studio"}
    budget_state["required_output_files_written"] = {"a.md"}

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="I will write the remaining file now."),
            ]
        },
        runtime,
    )

    assert update == {"jump_to": "model"}


def test_incomplete_pack_does_not_reengage_after_budget_is_exhausted() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=1,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "asset-studio"}
    budget_state["required_output_files_written"] = {"a.md"}

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="I will write the remaining file now."),
            ]
        },
        runtime,
    )

    assert update is not None
    assert "jump_to" not in update
    assert "Launch Pack 未完成" in update["messages"][0].content
    assert "主智能体模型调用上限 1 次" in update["messages"][0].content


def test_complete_pack_ready_replaces_manual_read_with_configured_presentation() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["required_output_files_ready"] = True
    manual_read = AIMessage(
        content="check again",
        tool_calls=[_tool_call("read_file", "read-1", {"path": "/mnt/user-data/outputs/a.md"})],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="build pack"), manual_read]},
        runtime,
    )

    assert update is not None
    calls = update["messages"][0].tool_calls
    assert [call["name"] for call in calls] == ["present_files"]
    assert calls[0]["args"]["filepaths"] == ["/mnt/user-data/outputs/a.md", "/mnt/user-data/outputs/b.csv"]


def test_failed_complete_pack_preflight_allows_only_revision_then_retries_presentation() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["required_output_files_ready"] = True
    user = HumanMessage(content="build pack")
    present = AIMessage(
        content="",
        tool_calls=[_tool_call("present_files", "present-1", {"filepaths": ["/mnt/user-data/outputs/a.md", "/mnt/user-data/outputs/b.csv"]})],
    )
    failure = ToolMessage(
        content="Error: Launch Pack preflight blocked delivery:\n- a.md:4 unsafe claim",
        tool_call_id="present-1",
        status="error",
    )
    tools = [
        SimpleNamespace(name="read_file"),
        SimpleNamespace(name="grep"),
        SimpleNamespace(name="write_file"),
        SimpleNamespace(name="str_replace"),
        SimpleNamespace(name="present_files"),
    ]
    request = _FakeRequest(runtime=runtime, messages=[user, present, failure], tools=tools)
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["write_file", "str_replace"]
    assert captured[0].messages[-1].name == "complete_pack_revision"

    revision = AIMessage(
        content="fix",
        tool_calls=[
            _tool_call(
                "str_replace",
                "replace-1",
                {"path": "/mnt/user-data/outputs/a.md", "old_str": "unsafe", "new_str": "neutral"},
            )
        ],
    )
    revision_result = ToolMessage(content="OK", tool_call_id="replace-1")
    retry_request = _FakeRequest(runtime=runtime, messages=[user, present, failure, revision, revision_result], tools=tools)
    captured.clear()

    middleware.wrap_model_call(retry_request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["present_files"]
    assert captured[0].messages[-1].name == "complete_pack_presentation"


def test_failed_complete_pack_preflight_reengages_after_toolless_revision_intent() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["required_output_files_ready"] = True
    user = HumanMessage(content="build pack")
    present = AIMessage(
        content="",
        tool_calls=[_tool_call("present_files", "present-1", {"filepaths": ["/mnt/user-data/outputs/a.md", "/mnt/user-data/outputs/b.csv"]})],
    )
    failure = ToolMessage(
        content="Error: Launch Pack preflight blocked delivery:\n- evidence-ledger.json is invalid JSON",
        tool_call_id="present-1",
        status="error",
    )
    stalled = AIMessage(content="I will rewrite the invalid JSON now.")

    update = middleware.after_model({"messages": [user, present, failure, stalled]}, runtime)

    assert update == {"jump_to": "model"}


def test_internal_hidden_human_messages_do_not_reset_current_turn_accounting() -> None:
    user = HumanMessage(content="build pack")
    first_call = AIMessage(content="draft")
    hidden = HumanMessage(content="compact", name="compacted_file_history", additional_kwargs={"hide_from_ui": True})

    assert _current_turn_messages([user, first_call, hidden]) == [first_call, hidden]


def test_terminal_specialist_completion_limits_remaining_tools_to_revision_and_delivery() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["subagent_types_completed"] = {"evidence-checker"}

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    request = FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[
            SimpleNamespace(name="read_file"),
            SimpleNamespace(name="write_file"),
            SimpleNamespace(name="str_replace"),
            SimpleNamespace(name="present_files"),
            SimpleNamespace(name="task"),
        ],
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["write_file", "str_replace", "present_files"]
    final_message = captured[0].messages[-1]
    assert final_message.name == "post_subagent_finalization"
    assert "Do not perform another manual check" in final_message.content


def test_incomplete_terminal_specialist_forces_declarative_partial_result_without_tools() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["terminal_subagent_finished"] = True
    budget_state["evidence_checker_completed"] = False

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    request = FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[SimpleNamespace(name="present_files"), SimpleNamespace(name="task")],
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    assert captured[0].tools == []
    assert captured[0].messages[-1].name == "post_subagent_failure"
    assert "partial or blocked" in captured[0].messages[-1].content

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="", tool_calls=[_tool_call("present_files", "present-1")]),
            ]
        },
        runtime,
    )
    assert update is not None
    assert update["messages"][0].tool_calls == []


def test_blocked_evidence_verdict_cannot_present_files() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["terminal_subagent_finished"] = True
    budget_state["subagent_types_completed"] = {"evidence-checker"}
    budget_state["evidence_checker_completed"] = True
    budget_state["evidence_checker_verdict"] = "blocked"

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="", tool_calls=[_tool_call("present_files", "present-1")]),
            ]
        },
        runtime,
    )

    assert update is not None
    assert update["messages"][0].tool_calls == []


def test_disallowed_tool_after_terminal_specialist_is_replaced_with_configured_delivery() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md", "b.csv"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"evidence-checker"}
    budget_state["evidence_checker_completed"] = True
    budget_state["evidence_checker_verdict"] = "pass"

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="Let me inspect again", tool_calls=[_tool_call("grep", "grep-1")]),
            ]
        },
        runtime,
    )

    assert update is not None
    calls = update["messages"][0].tool_calls
    assert [call["name"] for call in calls] == ["present_files"]
    assert calls[0]["args"]["filepaths"] == ["/mnt/user-data/outputs/a.md", "/mnt/user-data/outputs/b.csv"]


def test_post_specialist_revision_calls_drop_reads_and_defer_presentation() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md"],
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["subagent_types_completed"] = {"evidence-checker"}
    message = AIMessage(
        content="apply fix",
        tool_calls=[
            _tool_call("read_file", "read-1"),
            _tool_call("str_replace", "replace-1"),
            _tool_call("present_files", "present-1"),
        ],
    )

    update = middleware.after_model({"messages": [HumanMessage(content="build pack"), message]}, runtime)

    assert update is not None
    assert [call["name"] for call in update["messages"][0].tool_calls] == ["str_replace"]


def test_plain_text_after_valid_terminal_specialist_is_converted_to_delivery() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"evidence-checker"}
    budget_state["evidence_checker_completed"] = True
    budget_state["evidence_checker_verdict"] = "pass"

    update = middleware.after_model(
        {"messages": [HumanMessage(content="build pack"), AIMessage(content="audit passed")]},
        runtime,
    )

    assert update is not None
    assert [call["name"] for call in update["messages"][0].tool_calls] == ["present_files"]


def test_revise_verdict_requires_at_least_one_revision_before_auto_delivery() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            finalize_after_subagent="evidence-checker",
            required_output_files=["a.md"],
            require_evidence_checker=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"evidence-checker"}
    budget_state["evidence_checker_completed"] = True
    budget_state["evidence_checker_verdict"] = "revise"

    assert (
        middleware.after_model(
            {"messages": [HumanMessage(content="build pack"), AIMessage(content="revision needed")]},
            runtime,
        )
        is None
    )

    middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="fix", tool_calls=[_tool_call("str_replace", "replace-1")]),
            ]
        },
        runtime,
    )
    update = middleware.after_model(
        {"messages": [HumanMessage(content="build pack"), AIMessage(content="fixed")]},
        runtime,
    )

    assert update is not None
    assert [call["name"] for call in update["messages"][0].tool_calls] == ["present_files"]


def test_wrap_model_call_makes_a_successful_file_delivery_terminal() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    request = MagicMock()
    request.runtime = runtime
    request.messages = [
        HumanMessage(content="build pack"),
        AIMessage(content="", tool_calls=[_tool_call("present_files", "present-1")]),
        ToolMessage(content="Successfully presented files", tool_call_id="present-1"),
    ]
    request.override = lambda **updates: SimpleNamespace(
        runtime=runtime,
        messages=updates.get("messages", request.messages),
    )
    captured = []

    middleware.wrap_model_call(request, lambda updated_request: captured.append(updated_request) or MagicMock())

    final_message = captured[0].messages[-1]
    assert isinstance(final_message, HumanMessage)
    assert final_message.name == "terminal_delivery_finalization"
    assert final_message.additional_kwargs["hide_from_ui"] is True
    assert "Do not call any more tools" in final_message.content
    assert "end with a question" in final_message.content


def test_tool_calls_after_successful_file_delivery_are_removed() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=4,
            max_total_tokens=200_000,
            max_execution_seconds=240,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    extra_work = AIMessage(content="", tool_calls=[_tool_call("web_search", "search-2")])

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="build pack"),
                AIMessage(content="", tool_calls=[_tool_call("present_files", "present-1")]),
                ToolMessage(content="Successfully presented files", tool_call_id="present-1"),
                extra_work,
            ]
        },
        runtime,
    )

    assert update is not None
    stopped = update["messages"][0]
    assert stopped.tool_calls == []
    assert stopped.content == "文件已经交付，本次请求到此结束。"


def test_complete_workflow_toolless_after_failed_preflight_reengages_model() -> None:
    """A complete-workflow request must not end with a toolless response
    after present_files preflight failed — the model should be re-entered
    so it can revise the flagged files and retry delivery."""
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "offer-architect", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
            validate_pack_before_present=True,
            complete_workflow_patterns=["Launch Validation Pack", "验证包"],
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "offer-architect", "asset-studio"}
    budget_state["required_output_files_ready"] = True

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="输出 Launch Validation Pack"),
                AIMessage(content="", tool_calls=[_tool_call("write_file", "w1")]),
                ToolMessage(content="OK: wrote a.md", tool_call_id="w1"),
                AIMessage(content="全部写完", tool_calls=[_tool_call("present_files", "p1")]),
                ToolMessage(content="Error: Launch Pack preflight blocked delivery: a.md invalid evidence_label", tool_call_id="p1"),
                AIMessage(content="预检失败，我需要读取文件修正标签"),  # toolless
            ]
        },
        runtime,
    )

    assert update == {"jump_to": "model"}


def test_complete_workflow_toolless_after_successful_preflight_retry_can_finish() -> None:
    """A successful retry closes the verification loop even when an earlier
    preflight attempt failed in the same user turn."""
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=3,
            max_total_tokens=500_000,
            max_execution_seconds=270,
            required_completed_subagents=["market-voc-researcher", "offer-architect", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
            validate_pack_before_present=True,
            complete_workflow_patterns=["Launch Validation Pack", "验证包"],
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    budget_state = runtime.context[RUN_BUDGET_CONTEXT_KEY]
    budget_state["subagent_types_completed"] = {"market-voc-researcher", "offer-architect", "asset-studio"}
    budget_state["required_output_files_ready"] = True

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="输出 Launch Validation Pack"),
                AIMessage(content="", tool_calls=[_tool_call("present_files", "p1")]),
                ToolMessage(content="Error: Launch Pack preflight blocked delivery", tool_call_id="p1", status="error"),
                AIMessage(content="", tool_calls=[_tool_call("str_replace", "r1")]),
                ToolMessage(content="Successfully replaced text", tool_call_id="r1"),
                AIMessage(content="", tool_calls=[_tool_call("present_files", "p2")]),
                ToolMessage(content="Successfully presented files", tool_call_id="p2", status="success"),
                AIMessage(content="7/7 artifacts delivered."),
            ]
        },
        runtime,
    )

    assert update is None

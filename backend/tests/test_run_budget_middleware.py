import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
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


@pytest.mark.asyncio
async def test_async_model_call_is_cancelled_at_the_remaining_run_budget() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=2,
            max_subagent_calls=0,
            max_total_tokens=100_000,
            max_execution_seconds=60,
            max_model_call_seconds=45,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["deadline_monotonic"] = time.monotonic() + 0.02
    request = _FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[],
    )
    cancelled = asyncio.Event()

    async def handler(_updated_request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    result = await middleware.awrap_model_call(request, handler)

    assert isinstance(result, AIMessage)
    assert result.additional_kwargs["deerflow_error_fallback"] is True
    assert result.additional_kwargs["error_type"] == "RunBudgetModelTimeout"
    assert "运行预算" in result.content
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_async_model_call_does_not_relabel_provider_timeout() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=2,
            max_subagent_calls=0,
            max_total_tokens=100_000,
            max_execution_seconds=60,
            max_model_call_seconds=45,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    request = _FakeRequest(
        runtime=runtime,
        messages=[HumanMessage(content="build pack")],
        tools=[],
    )

    async def handler(_updated_request):
        raise TimeoutError("provider timeout")

    with pytest.raises(TimeoutError, match="provider timeout"):
        await middleware.awrap_model_call(request, handler)


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


def test_direct_answer_stops_before_auto_pack_state_machine() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=0,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            direct_answer_patterns=["最先.*验证"],
            complete_pack_initial_research_calls=2,
            required_output_files=["launch-war-room.html"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="最先应该验证哪一个假设？"),
                AIMessage(content="先验证需求假设。"),
            ]
        },
        runtime,
    )

    assert update is None


def test_direct_answer_strips_unexpected_model_tool_call() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=0,
            max_total_tokens=200_000,
            max_execution_seconds=240,
            direct_answer_patterns=["最先.*验证"],
            required_output_files=["launch-war-room.html"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)

    update = middleware.after_model(
        {
            "messages": [
                HumanMessage(content="最先应该验证哪一个假设？"),
                AIMessage(content="", tool_calls=[_tool_call("web_search", "search-1")]),
            ]
        },
        runtime,
    )

    assert update is not None
    stopped = update["messages"][0]
    assert stopped.tool_calls == []
    assert "已停止异常工具调用" in stopped.content


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


def test_complete_pack_draft_reengages_when_model_calls_disallowed_read() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=0,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    user = HumanMessage(content="请输出 Launch Validation Pack")
    wrong_tool = AIMessage(
        content="I will load the skill first.",
        tool_calls=[
            _tool_call(
                "read_file",
                "read-1",
                {"path": "/mnt/skills/custom/ecom-launch/SKILL.md"},
            )
        ],
    )

    update = middleware.after_model({"messages": [user, wrong_tool]}, runtime)

    assert update == {"jump_to": "model"}


def test_complete_pack_ultra_exposes_only_the_next_required_specialist() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=3,
            max_total_tokens=250_000,
            max_execution_seconds=180,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_completed_subagents=["market-voc-researcher", "offer-architect", "asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    user = HumanMessage(content="请输出 Launch Validation Pack")

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    request = FakeRequest(
        runtime=runtime,
        messages=[user],
        tools=[SimpleNamespace(name="read_file"), SimpleNamespace(name="task"), SimpleNamespace(name="write_file")],
    )
    captured = []
    middleware.wrap_model_call(request, lambda updated: captured.append(updated) or MagicMock())

    assert [tool.name for tool in captured[0].tools] == ["task"]
    assert captured[0].messages[-1].name == "complete_pack_specialist"
    assert "Next required specialist: market-voc-researcher" in captured[0].messages[-1].content
    assert "already loaded" in captured[0].messages[-1].content

    runtime.context[RUN_BUDGET_CONTEXT_KEY]["subagent_types_completed"] = {"market-voc-researcher"}
    captured.clear()
    middleware.wrap_model_call(request, lambda updated: captured.append(updated) or MagicMock())
    assert "Next required specialist: offer-architect" in captured[0].messages[-1].content


def test_complete_pack_ultra_rejects_skill_read_before_required_specialist() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=3,
            max_total_tokens=250_000,
            max_execution_seconds=180,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_completed_subagents=["market-voc-researcher"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    user = HumanMessage(content="请输出 Launch Validation Pack")
    wrong_tool = AIMessage(
        content="",
        tool_calls=[_tool_call("read_file", "read-skill", {"path": "/mnt/skills/custom/ecom-launch/SKILL.md"})],
    )

    assert middleware.after_model({"messages": [user, wrong_tool]}, runtime) == {"jump_to": "model"}


def test_render_launch_pack_success_is_terminal_delivery() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=0,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["required_output_files_ready"] = True
    user = HumanMessage(content="请输出 Launch Validation Pack")
    render = AIMessage(content="", tool_calls=[_tool_call("render_launch_pack", "render-1", {"spec": {"category": "cup"}})])
    delivered = ToolMessage(content="Successfully presented files", tool_call_id="render-1", status="success")
    completion = AIMessage(
        content="Launch Validation Pack 已通过预检，7 个交付文件已生成并展示。",
        additional_kwargs={"deerflow_deterministic_completion": True},
    )

    assert middleware._complete_pack_phase([user, render, delivered], runtime) is None
    assert middleware.before_model({"messages": [user, render, delivered]}, runtime) is None
    assert middleware.before_model({"messages": [user, render, delivered, completion]}, runtime) == {"jump_to": "end"}
    update = middleware.after_model(
        {"messages": [user, render, delivered, AIMessage(content="继续搜索", tool_calls=[_tool_call("web_search", "extra")])]},
        runtime,
    )
    assert update is not None
    assert update["messages"][0].tool_calls == []


def test_before_model_injects_renderer_from_terminal_specialist_spec() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=1,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_completed_subagents=["asset-studio"],
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
            auto_render_after_subagent="asset-studio",
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["subagent_types_completed"] = {"asset-studio"}
    user = HumanMessage(content="请输出 Launch Validation Pack")
    delegated = AIMessage(
        content="",
        tool_calls=[
            _tool_call(
                "task",
                "asset-1",
                {"subagent_type": "asset-studio", "description": "create assets", "prompt": "build"},
            )
        ],
    )
    result = ToolMessage(
        content=(
            "Task Succeeded. Result: concept kit\n"
            '<launch_pack_spec>{"category":"通勤咖啡杯","target_price":"99-199 元",'
            '"decision":"test_now","decision_rationale":"先做七天验证",'
            '"audience":"工作日通勤人群","validation_goal":"验证问题与价格接受度",'
            '"evidence":[{"claim":"通勤场景存在保温诉求","evidence_label":"observed_public",'
            '"source_urls":["https://example.com/review"]}],'
            '"competitors":[{"name":"竞品 A","price_signal":"129 元",'
            '"evidence":{"label":"observed_public","source_url":"https://example.com/a"}}]}'
            "</launch_pack_spec>"
        ),
        tool_call_id="asset-1",
        status="success",
    )

    update = middleware.before_model({"messages": [user, delegated, result]}, runtime)

    assert update is not None
    assert update["jump_to"] == "tools"
    injected = update["messages"][0]
    assert isinstance(injected, AIMessage)
    assert injected.additional_kwargs["deerflow_deterministic_render"] is True
    assert injected.tool_calls[0]["name"] == "render_launch_pack"
    assert injected.tool_calls[0]["args"]["spec"]["category"] == "通勤咖啡杯"
    assert injected.tool_calls[0]["args"]["spec"]["evidence"][0]["source_urls"] == ["https://example.com/review"]
    assert injected.tool_calls[0]["args"]["spec"]["competitors"][0]["evidence"]["source_url"] == "https://example.com/a"


def test_before_model_falls_back_to_model_for_invalid_terminal_specialist_spec() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=1,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            complete_workflow_patterns=["Launch Validation Pack"],
            required_completed_subagents=["asset-studio"],
            auto_present_complete_pack=True,
            auto_render_after_subagent="asset-studio",
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["subagent_types_completed"] = {"asset-studio"}
    user = HumanMessage(content="请输出 Launch Validation Pack")
    delegated = AIMessage(
        content="",
        tool_calls=[_tool_call("task", "asset-1", {"subagent_type": "asset-studio"})],
    )
    invalid = ToolMessage(
        content="Task Succeeded. Result: <launch_pack_spec>{not-json}</launch_pack_spec>",
        tool_call_id="asset-1",
        status="success",
    )

    assert middleware.before_model({"messages": [user, delegated, invalid]}, runtime) is None


def test_flash_complete_pack_runs_bounded_public_research_before_drafting() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=12,
            max_subagent_calls=0,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            complete_pack_initial_research_calls=2,
            complete_pack_initial_fetch_calls=2,
            required_output_files=["a.md", "b.csv"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    user = HumanMessage(content="请用公开信号输出 Launch Validation Pack")

    class FakeRequest(SimpleNamespace):
        def override(self, **updates):
            return FakeRequest(
                runtime=self.runtime,
                messages=updates.get("messages", self.messages),
                tools=updates.get("tools", self.tools),
            )

    request = FakeRequest(
        runtime=runtime,
        messages=[user],
        tools=[
            SimpleNamespace(name="web_search"),
            SimpleNamespace(name="web_fetch"),
            SimpleNamespace(name="render_launch_pack"),
            SimpleNamespace(name="write_launch_pack"),
            SimpleNamespace(name="write_file"),
        ],
    )
    captured = []
    middleware.wrap_model_call(request, lambda updated: captured.append(updated) or MagicMock())
    assert [tool.name for tool in captured[0].tools] == ["web_search", "web_fetch"]
    assert captured[0].messages[-1].name == "complete_pack_research"

    # DeepSeek can occasionally emit DSML-looking search markup as plain text
    # instead of provider tool_calls. The middleware must turn that stalled
    # response into real bounded web_search calls rather than loop on intent.
    stalled = AIMessage(content="<tool_calls>web_search ...</tool_calls>")
    update = middleware.after_model({"messages": [user, stalled]}, runtime)
    assert update is not None
    configured_calls = update["messages"][0].tool_calls
    assert len(configured_calls) == 2
    assert {call["name"] for call in configured_calls} == {"web_search"}
    assert all(call["args"]["max_results"] == 5 for call in configured_calls)

    # Once discovery has returned, Flash must fetch direct result pages instead
    # of drafting from search snippets.
    search_1 = AIMessage(content="", tool_calls=[_tool_call("web_search", "s1")])
    search_2 = AIMessage(content="", tool_calls=[_tool_call("web_search", "s2")])
    request.messages = [
        user,
        search_1,
        ToolMessage(
            content=json.dumps(
                {
                    "results": [
                        {
                            "title": "通勤咖啡杯公开页面",
                            "url": "https://example.com/cup-a",
                            "content": "通勤咖啡杯与保温杯场景",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            tool_call_id="s1",
            name="web_search",
        ),
        search_2,
        ToolMessage(
            content=json.dumps(
                {
                    "results": [
                        {
                            "title": "便携咖啡杯竞品页",
                            "url": "https://example.com/cup-b",
                            "content": "咖啡杯价格与通勤场景",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            tool_call_id="s2",
            name="web_search",
        ),
    ]
    captured.clear()
    middleware.wrap_model_call(request, lambda updated: captured.append(updated) or MagicMock())
    assert [tool.name for tool in captured[0].tools] == ["web_fetch"]
    assert captured[0].messages[-1].name == "complete_pack_research"
    assert "Remaining direct-page fetch attempts required: 2" in captured[0].messages[-1].content

    stalled_fetch = AIMessage(content="I should verify the source pages now.")
    update = middleware.after_model({"messages": [*request.messages, stalled_fetch]}, runtime)
    assert update is not None
    configured_fetches = update["messages"][0].tool_calls
    assert len(configured_fetches) == 2
    assert {call["name"] for call in configured_fetches} == {"web_fetch"}
    assert {call["args"]["url"] for call in configured_fetches} == {
        "https://example.com/cup-a",
        "https://example.com/cup-b",
    }

    fetch_1 = AIMessage(content="", tool_calls=[_tool_call("web_fetch", "f1", {"url": "https://example.com/cup-a"})])
    fetch_2 = AIMessage(content="", tool_calls=[_tool_call("web_fetch", "f2", {"url": "https://example.com/cup-b"})])
    request.messages.extend(
        [
            fetch_1,
            ToolMessage(content="# Product A", tool_call_id="f1", name="web_fetch"),
            fetch_2,
            ToolMessage(content="# Product B", tool_call_id="f2", name="web_fetch"),
        ]
    )
    captured.clear()
    middleware.wrap_model_call(request, lambda updated: captured.append(updated) or MagicMock())
    assert [tool.name for tool in captured[0].tools] == ["render_launch_pack", "write_launch_pack", "write_file"]
    assert captured[0].messages[-1].name == "complete_pack_draft"
    assert "Call render_launch_pack exactly once" in captured[0].messages[-1].content


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


def test_complete_pack_ready_replaces_model_filename_aliases_with_configured_names() -> None:
    middleware = RunBudgetMiddleware(
        AgentRunBudgetConfig(
            max_lead_model_calls=20,
            max_subagent_calls=0,
            max_total_tokens=250_000,
            max_execution_seconds=120,
            required_output_files=["launch-war-room.html", "evidence-ledger.json"],
            auto_present_complete_pack=True,
        )
    )
    runtime = _runtime()
    middleware.before_agent({}, runtime)
    runtime.context[RUN_BUDGET_CONTEXT_KEY]["required_output_files_ready"] = True
    aliased_present = AIMessage(
        content="",
        tool_calls=[
            _tool_call(
                "present_files",
                "present-alias",
                {
                    "filepaths": [
                        "/mnt/user-data/outputs/launch_war_room.html",
                        "/mnt/user-data/outputs/evidence_ledger.json",
                    ]
                },
            )
        ],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="build pack"), aliased_present]},
        runtime,
    )

    assert update is not None
    calls = update["messages"][0].tool_calls
    assert [call["name"] for call in calls] == ["present_files"]
    assert calls[0]["args"]["filepaths"] == [
        "/mnt/user-data/outputs/launch-war-room.html",
        "/mnt/user-data/outputs/evidence-ledger.json",
    ]


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
    assert "file card below" in final_message.content
    assert "Do not expose `/mnt/user-data/outputs`" in final_message.content
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

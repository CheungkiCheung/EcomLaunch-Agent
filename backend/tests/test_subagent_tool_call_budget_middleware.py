from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import HumanMessage, ToolMessage

from deerflow.agents.middlewares.subagent_tool_call_budget_middleware import (
    SubagentToolCallBudgetMiddleware,
)


def _request(completed: int) -> ModelRequest:
    messages = [HumanMessage(content="核验指标")]
    messages.extend(
        ToolMessage(
            content="result",
            tool_call_id=f"call-{index}",
            name="store_query_data",
        )
        for index in range(completed)
    )
    return ModelRequest(
        model=None,
        messages=messages,
        tools=[
            SimpleNamespace(name="store_inspect_data"),
            SimpleNamespace(name="store_query_data"),
        ],
        state={},
    )


def test_keeps_tools_before_budget_is_exhausted():
    middleware = SubagentToolCallBudgetMiddleware(max_tool_calls=4)
    captured = {}

    def handler(request):
        captured["request"] = request
        return "ok"

    assert middleware.wrap_model_call(_request(3), handler) == "ok"
    assert len(captured["request"].tools) == 2
    assert len(captured["request"].messages) == 4


def test_removes_tools_and_injects_finish_notice_at_budget():
    middleware = SubagentToolCallBudgetMiddleware(max_tool_calls=4)
    captured = {}

    def handler(request):
        captured["request"] = request
        return "ok"

    assert middleware.wrap_model_call(_request(4), handler) == "ok"
    assert captured["request"].tools == []
    assert "工具调用预算已经用完" in captured["request"].messages[-1].content


@pytest.mark.anyio
async def test_async_path_applies_same_budget():
    middleware = SubagentToolCallBudgetMiddleware(max_tool_calls=1)
    captured = {}

    async def handler(request):
        captured["request"] = request
        return "ok"

    assert await middleware.awrap_model_call(_request(1), handler) == "ok"
    assert captured["request"].tools == []

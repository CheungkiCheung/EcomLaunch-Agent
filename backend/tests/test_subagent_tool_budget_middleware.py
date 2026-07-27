"""Subagent tool-round budget enforcement without model doubles."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.subagent_tool_budget_middleware import (
    SubagentToolBudgetMiddleware,
)


def _tool_round(call_id: str) -> list:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "commerce_compare_windows",
                    "args": {},
                    "id": call_id,
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="result",
            tool_call_id=call_id,
            name="commerce_compare_windows",
        ),
    ]


def _parallel_tool_round(*call_ids: str) -> list:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": f"tool_{index}",
                    "args": {},
                    "id": call_id,
                    "type": "tool_call",
                }
                for index, call_id in enumerate(call_ids, start=1)
            ],
        ),
        *(
            ToolMessage(
                content="result",
                tool_call_id=call_id,
                name=f"tool_{index}",
            )
            for index, call_id in enumerate(call_ids, start=1)
        ),
    ]


def test_model_request_keeps_tools_before_round_budget_is_reached():
    middleware = SubagentToolBudgetMiddleware(max_tool_rounds=2)
    request = MagicMock()
    request.messages = [HumanMessage(content="调查"), *_tool_round("call-1")]
    request.tools = [MagicMock(name="tool")]
    handler = MagicMock(return_value="response")

    assert middleware.wrap_model_call(request, handler) == "response"

    request.override.assert_not_called()
    handler.assert_called_once_with(request)


def test_model_request_removes_tools_and_injects_stop_instruction_at_budget():
    middleware = SubagentToolBudgetMiddleware(max_tool_rounds=1)
    request = MagicMock()
    request.messages = [HumanMessage(content="调查"), *_tool_round("call-1")]
    request.tools = [MagicMock(name="tool")]
    request.override.return_value = "budgeted-request"
    handler = MagicMock(return_value="response")

    assert middleware.wrap_model_call(request, handler) == "response"

    request.override.assert_called_once()
    override = request.override.call_args.kwargs
    assert override["tools"] == []
    stop_message = override["messages"][-1]
    assert isinstance(stop_message, HumanMessage)
    assert stop_message.name == "subagent_budget_stop"
    assert stop_message.additional_kwargs["hide_from_ui"] is True
    assert "立即综合" in stop_message.content
    handler.assert_called_once_with("budgeted-request")


@pytest.mark.anyio
async def test_async_model_request_uses_the_same_budget_contract():
    middleware = SubagentToolBudgetMiddleware(max_tool_rounds=1)
    request = MagicMock()
    request.messages = [HumanMessage(content="调查"), *_tool_round("call-1")]
    request.tools = [MagicMock(name="tool")]
    request.override.return_value = "budgeted-request"
    handler = AsyncMock(return_value="response")

    assert await middleware.awrap_model_call(request, handler) == "response"

    handler.assert_awaited_once_with("budgeted-request")


def test_model_request_removes_tools_when_total_call_budget_is_reached():
    middleware = SubagentToolBudgetMiddleware(
        max_tool_rounds=4,
        max_tool_calls=2,
    )
    request = MagicMock()
    request.messages = [
        HumanMessage(content="调查"),
        *_parallel_tool_round("call-1", "call-2"),
    ]
    request.tools = [MagicMock(name="tool")]
    request.override.return_value = "budgeted-request"
    handler = MagicMock(return_value="response")

    assert middleware.wrap_model_call(request, handler) == "response"

    override = request.override.call_args.kwargs
    assert override["tools"] == []
    stop_message = override["messages"][-1]
    assert stop_message.additional_kwargs["budget_type"] == "tool_calls"
    assert stop_message.additional_kwargs["budget_limit"] == 2


@pytest.mark.anyio
async def test_after_model_truncates_parallel_calls_to_remaining_total_budget():
    middleware = SubagentToolBudgetMiddleware(
        max_tool_rounds=4,
        max_tool_calls=3,
    )
    messages = [
        HumanMessage(content="调查"),
        *_tool_round("call-1"),
        AIMessage(
            id="current-response",
            content="",
            tool_calls=[
                {
                    "name": "commerce_evidence_query",
                    "args": {"offset": index},
                    "id": f"call-{index}",
                    "type": "tool_call",
                }
                for index in (2, 3, 4)
            ],
        ),
    ]

    update = await middleware.aafter_model(
        {"messages": messages},
        MagicMock(),
    )

    assert update is not None
    kept = update["messages"][0]
    assert kept.id == "current-response"
    assert [call["id"] for call in kept.tool_calls] == ["call-2", "call-3"]


@pytest.mark.parametrize("value", [0, -1])
def test_budget_rejects_non_positive_rounds(value: int):
    with pytest.raises(ValueError, match="positive"):
        SubagentToolBudgetMiddleware(max_tool_rounds=value)


@pytest.mark.parametrize("value", [0, -1])
def test_budget_rejects_non_positive_total_calls(value: int):
    with pytest.raises(ValueError, match="positive"):
        SubagentToolBudgetMiddleware(max_tool_rounds=2, max_tool_calls=value)

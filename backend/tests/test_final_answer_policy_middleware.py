"""Fail-closed final-answer language policy without model doubles."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.final_answer_policy_middleware import (
    FinalAnswerPolicyMiddleware,
)


def _runtime(run_id: str = "run-1"):
    return SimpleNamespace(context={"thread_id": "thread-1", "run_id": run_id})


def test_compliant_final_answer_passes_without_repair():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因", "完全排除"),
        max_repairs=1,
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(content="运输阶段平均时长上升，但当前数据不能确认因果。"),
        ]
    }

    assert middleware.after_model(state, _runtime()) is None


def test_explicitly_negated_forbidden_phrases_pass_without_repair():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因", "导致", "完全排除"),
        max_repairs=1,
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(content=("当前数据不能证明运输时长上升导致晚到率变化，尚不能确认承运阶段是主因，也不能完全排除卖家端其他因素。")),
        ]
    }

    assert middleware.after_model(state, _runtime()) is None


def test_asserted_forbidden_phrase_after_contrast_is_still_repaired():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("导致",),
        max_repairs=1,
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(
                id="answer-contrast",
                content=("当前数据不能证明处理时长变化导致晚到率上升，但是运输时长恶化导致晚到率上升。"),
            ),
        ]
    }

    update = middleware.after_model(state, _runtime())

    assert update is not None
    assert update["jump_to"] == "model"
    assert update["messages"][0].additional_kwargs["final_answer_policy_status"] == "repair_required"


def test_first_forbidden_final_answer_is_hidden_and_repaired():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因", "完全排除"),
        max_repairs=1,
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(
                id="answer-1",
                content="运输恶化是延迟率上升的主因，完全排除卖家问题。",
            ),
        ]
    }

    update = middleware.after_model(state, _runtime())

    assert update is not None
    assert update["jump_to"] == "model"
    rejected = update["messages"][0]
    assert rejected.id == "answer-1"
    assert rejected.additional_kwargs["hide_from_ui"] is True
    assert rejected.additional_kwargs["final_answer_policy_status"] == "repair_required"

    request = MagicMock()
    request.runtime = _runtime()
    request.messages = [*state["messages"], rejected]
    request.override.return_value = "repair-request"
    handler = MagicMock(return_value="response")

    result = middleware.wrap_model_call(request, handler)

    assert result == "response"
    reminder = request.override.call_args.kwargs["messages"][-1]
    assert reminder.name == "final_answer_policy_repair"
    assert "主因" in reminder.content
    assert "完全排除" in reminder.content
    assert "相关性" in reminder.content
    handler.assert_called_once_with("repair-request")


def test_repeated_forbidden_final_answer_fails_closed():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因",),
        max_repairs=1,
    )
    runtime = _runtime()
    first = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(id="answer-1", content="运输恶化是主因。"),
        ]
    }
    middleware.after_model(first, runtime)
    request = MagicMock()
    request.runtime = runtime
    request.messages = first["messages"]
    request.override.return_value = "repair-request"
    middleware.wrap_model_call(request, MagicMock(return_value="response"))

    repeated = {
        "messages": [
            *first["messages"],
            AIMessage(id="answer-2", content="结论仍然是主因。"),
        ]
    }
    update = middleware.after_model(repeated, runtime)

    assert update is not None
    blocked = update["messages"][0]
    assert blocked.id == "answer-2"
    assert blocked.additional_kwargs["final_answer_policy_status"] == "blocked"
    assert blocked.additional_kwargs.get("hide_from_ui") is not True
    assert "主因" not in blocked.content
    assert "超出证据范围" in blocked.content


def test_tool_call_response_is_not_mistaken_for_final_answer():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因",),
        max_repairs=1,
    )
    state = {
        "messages": [
            HumanMessage(content="分析异常"),
            AIMessage(
                content="先检查主因假设",
                tool_calls=[
                    {
                        "name": "commerce_compare_windows",
                        "id": "compare",
                        "args": {},
                    }
                ],
            ),
        ]
    }

    assert middleware.after_model(state, _runtime()) is None


def test_completed_verifier_receives_proactive_final_answer_reminder():
    middleware = FinalAnswerPolicyMiddleware(
        forbidden_phrases=("主因", "导致", "完全排除"),
        max_repairs=1,
    )
    runtime = _runtime()
    messages = [
        HumanMessage(content="分析异常"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "spawn_task",
                    "id": "task-verifier",
                    "args": {
                        "description": "独立核验",
                        "prompt": "重新计算核心指标",
                        "subagent_type": "verifier",
                        "source_refs": ["task:task-analyst"],
                    },
                }
            ],
        ),
        ToolMessage(
            tool_call_id="task-verifier",
            content=json.dumps(
                {
                    "ok": True,
                    "task": {
                        "task_id": "task-verifier",
                        "subagent_type": "verifier",
                        "status": "running",
                        "source_refs": ["task:task-analyst"],
                    },
                }
            ),
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "wait_task",
                    "id": "wait-verifier",
                    "args": {"task_ids": ["task-verifier"], "mode": "all"},
                }
            ],
        ),
        ToolMessage(
            tool_call_id="wait-verifier",
            content=json.dumps(
                {
                    "ok": True,
                    "ready": True,
                    "tasks": [
                        {
                            "task_id": "task-verifier",
                            "subagent_type": "verifier",
                            "status": "completed",
                            "source_refs": ["task:task-analyst"],
                        }
                    ],
                }
            ),
        ),
    ]
    request = MagicMock()
    request.runtime = runtime
    request.messages = messages
    request.override.return_value = "preflight-request"
    handler = MagicMock(return_value="response")

    result = middleware.wrap_model_call(request, handler)

    assert result == "response"
    reminder = request.override.call_args.kwargs["messages"][-1]
    assert reminder.name == "final_answer_policy_preflight"
    assert reminder.additional_kwargs["hide_from_ui"] is True
    assert "主因、导致、完全排除" in reminder.content
    assert "Markdown 表格" in reminder.content
    assert "重新提交终答" in reminder.content
    assert "1800" in reminder.content
    handler.assert_called_once_with("preflight-request")

"""Fresh DeepSeek V4 release gates for the durable Parent–Subagent Harness."""

from __future__ import annotations

import asyncio
import importlib
import sys
from dataclasses import replace
from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.commerce.evaluation.real_model_preflight import (
    PreflightStatus,
    run_real_model_preflight,
)
from deerflow.agents.lead_agent.prompt import _build_subagent_section
from deerflow.config.app_config import AppConfig
from deerflow.models import create_chat_model
from deerflow.models.lifecycle import aclose_model_clients
from deerflow.subagents.registry import get_subagent_config
from deerflow.subagents.tasks import (
    ContextPacket,
    DurableSubagentTaskRuntime,
    MemorySubagentTaskStore,
    SubagentTaskManager,
    SubagentTaskStatus,
    TaskWaitMode,
)
from deerflow.tools.builtins.durable_task_tools import (
    spawn_task_tool,
    wait_task_tool,
)


def _response_identity(response: Any) -> tuple[str | None, str | None]:
    metadata = dict(getattr(response, "response_metadata", None) or {})
    headers = {
        str(key).casefold(): str(value)
        for key, value in dict(metadata.get("headers") or {}).items()
    }
    identity = metadata.get("model_name") or metadata.get("model")
    if not identity:
        identity = (
            headers.get("x-deepseek-model")
            or headers.get("x-model-name")
            or headers.get("x-model")
        )
    request_id = (
        headers.get("x-request-id")
        or headers.get("x-deepseek-request-id")
        or headers.get("request-id")
        or metadata.get("id")
    )
    return (
        str(identity) if identity else None,
        str(request_id) if request_id else None,
    )


@pytest.fixture
def real_executor_module():
    """Replace the suite-wide circular-import mock with the real executor."""
    __import__("deerflow.agents")
    module_name = "deerflow.subagents.executor"
    package = sys.modules["deerflow.subagents"]
    original_module = sys.modules.get(module_name)
    original_attribute = getattr(package, "executor", None)
    sys.modules.pop(module_name, None)
    if hasattr(package, "executor"):
        delattr(package, "executor")
    module = importlib.import_module(module_name)
    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        if original_attribute is not None:
            setattr(package, "executor", original_attribute)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_durable_spawn_wait_persists_identity(
    real_executor_module,
):
    preflight = await asyncio.to_thread(run_real_model_preflight)
    assert preflight.status is PreflightStatus.PASSED, preflight.model_dump_json()

    app_config = AppConfig.from_file()
    configured_model = app_config.get_model_config("deepseek-reasoner")
    assert configured_model is not None
    assert configured_model.max_retries == 0
    base = get_subagent_config("analyst", app_config=app_config)
    assert base is not None
    config = replace(
        base,
        skills=[],
        max_turns=4,
        timeout_seconds=120,
        max_output_tokens=512,
        model_max_retries=0,
        llm_retry_max_attempts=1,
    )
    executor = real_executor_module.SubagentExecutor(
        config=config,
        tools=[],
        parent_model="deepseek-reasoner",
        thread_id="live-thread",
        trace_id="live-durable",
        app_config=app_config,
    )
    manager = SubagentTaskManager(MemorySubagentTaskStore())
    runtime = DurableSubagentTaskRuntime(
        manager,
        worker_id="live-worker",
        poll_interval_seconds=0.05,
        result_getter=real_executor_module.get_background_task_result,
        cancel_requester=real_executor_module.request_cancel_background_task,
        cleanup=real_executor_module.cleanup_background_task,
    )
    try:
        started = await runtime.spawn(
            task_id="live-task-1",
            thread_id="live-thread",
            run_id="live-run",
            user_id="live-user",
            subagent_type="analyst",
            description="验证 Durable 生命周期",
            context_packet=ContextPacket(
                goal=(
                    "不要调用工具。只输出一句中文：Durable Subagent 已完成真实模型验证。"
                ),
                budget={"max_turns": 4, "timeout_seconds": 120},
            ),
            executor=executor,
            max_attempts=1,
        )
        assert started.status is SubagentTaskStatus.running

        waited = await runtime.wait(
            ["live-task-1"],
            mode=TaskWaitMode.all,
            timeout_seconds=60,
        )
        assert waited.ready is True
        task = waited.tasks[0]
        assert task.status is SubagentTaskStatus.completed, task.model_dump_json()
        assert task.result and task.result["output"]
        identities = task.telemetry.get("actual_model_identities") or []
        request_ids = task.telemetry.get("provider_request_ids") or []
        assert identities and all(
            identity.casefold().startswith("deepseek-v4")
            for identity in identities
        )
        assert request_ids
        assert len(request_ids) == len(set(request_ids))
        assert task.telemetry["token_usage"]["total_tokens"] > 0
    finally:
        await runtime.shutdown(reason="live gate cleanup")


@pytest.mark.real_model
@pytest.mark.anyio
async def test_fresh_deepseek_v4_parent_routes_zero_or_parallel_subagents():
    preflight = await asyncio.to_thread(run_real_model_preflight)
    assert preflight.status is PreflightStatus.PASSED, preflight.model_dump_json()

    app_config = AppConfig.from_file()
    configured_model = app_config.get_model_config("deepseek-reasoner")
    assert configured_model is not None
    assert configured_model.max_retries == 0
    model = create_chat_model(
        "deepseek-reasoner",
        thinking_enabled=False,
        app_config=app_config,
        attach_tracing=False,
        max_tokens=700,
        max_retries=0,
    )
    bound = model.bind_tools([spawn_task_tool, wait_task_tool])
    system = SystemMessage(
        content=_build_subagent_section(3, app_config=app_config)
    )
    try:
        simple = await bound.ainvoke(
            [
                system,
                HumanMessage(
                    content=(
                        "这是一个无需数据和工具的简单算术问题：订单数从100变成120，"
                        "增长率是多少？请直接用中文回答，不要委派 Subagent。"
                    )
                ),
            ]
        )
        assert not simple.tool_calls

        complex_response = await bound.ainvoke(
            [
                system,
                HumanMessage(
                    content=(
                        "现在只做任务分发，不要直接分析：针对一份电商订单数据，同时启动"
                        "两个相互独立的只读任务。第一个用 explore 检查字段、口径和数据限制；"
                        "第二个用 analyst 分析履约异常贡献。必须在同一个响应中调用两次 "
                        "spawn_task，然后停止，等待系统返回 task_id。"
                    )
                ),
            ]
        )
        spawn_calls = [
            call
            for call in complex_response.tool_calls
            if call.get("name") == "spawn_task"
        ]
        assert len(spawn_calls) == 2, complex_response
        assert {call["args"]["subagent_type"] for call in spawn_calls} == {
            "explore",
            "analyst",
        }

        simple_identity, simple_request_id = _response_identity(simple)
        complex_identity, complex_request_id = _response_identity(complex_response)
        assert simple_identity and simple_identity.casefold().startswith("deepseek-v4")
        assert complex_identity and complex_identity.casefold().startswith("deepseek-v4")
        assert simple_request_id
        assert complex_request_id
        assert simple_request_id != complex_request_id
    finally:
        await aclose_model_clients(model)

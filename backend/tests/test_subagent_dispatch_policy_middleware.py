"""Pre-execution verifier lineage policy for dynamic Parent dispatch."""

import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.subagent_dispatch_policy_middleware import (
    SubagentDispatchPolicyMiddleware,
)


def _runtime(run_id: str = "run-1"):
    runtime = MagicMock()
    runtime.context = {"thread_id": "thread-1", "run_id": run_id}
    return runtime


def _tool_call(name: str, call_id: str, **args):
    return {"name": name, "id": call_id, "args": args}


def _completed_task_exchange(
    task_id: str,
    subagent_type: str,
    *,
    skills: list[str] | None = None,
    tools: list[str] | None = None,
    max_tool_rounds: int | None = None,
    max_tool_calls: int | None = None,
):
    return [
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    task_id,
                    description="前置任务",
                    prompt="执行前置调查",
                    subagent_type=subagent_type,
                    skills=skills or ["fulfillment-investigation"],
                    tools=tools or ["commerce_evidence_query"],
                    max_tool_rounds=max_tool_rounds or 1,
                    max_tool_calls=max_tool_calls or 1,
                )
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": True,
                    "task": {
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                        "status": "running",
                        "source_refs": [],
                    },
                }
            ),
            tool_call_id=task_id,
        ),
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "wait_task",
                    f"wait-{task_id}",
                    task_ids=[task_id],
                    mode="all",
                )
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": True,
                    "ready": True,
                    "tasks": [
                        {
                            "task_id": task_id,
                            "subagent_type": subagent_type,
                            "status": "completed",
                            "source_refs": [],
                        }
                    ],
                }
            ),
            tool_call_id=f"wait-{task_id}",
        ),
    ]


def _failed_task_exchange(
    task_id: str,
    *,
    description: str,
    prompt: str,
    subagent_type: str = "analyst",
):
    return [
        AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    task_id,
                    description=description,
                    prompt=prompt,
                    subagent_type=subagent_type,
                    skills=["fulfillment-investigation"],
                    tools=["commerce_compare_windows"],
                    max_tool_rounds=1,
                    max_tool_calls=1,
                )
            ],
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": True,
                    "task": {
                        "task_id": task_id,
                        "subagent_type": subagent_type,
                        "status": "failed",
                        "source_refs": [],
                    },
                }
            ),
            tool_call_id=task_id,
        ),
    ]


def test_rejects_premature_verifier_but_keeps_parallel_valid_task():
    middleware = SubagentDispatchPolicyMiddleware()
    runtime = _runtime()
    candidate = AIMessage(
        id="dispatch-batch",
        content="并行启动探索和核验。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "verifier-too-early",
                description="独立核验",
                prompt="核验结论",
                subagent_type="verifier",
                source_refs=[],
            ),
            _tool_call(
                "spawn_task",
                "explore-valid",
                description="检查数据覆盖",
                prompt="检查全量覆盖",
                subagent_type="explore",
                source_refs=[],
            ),
        ],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="调查异常"), candidate]},
        runtime,
    )

    assert update is not None
    replacement = update["messages"][0]
    assert replacement.id == "dispatch-batch"
    assert [call["id"] for call in replacement.tool_calls] == ["explore-valid"]
    assert "独立核验将在前置任务完成后进行" in replacement.content
    assert replacement.additional_kwargs["subagent_dispatch_policy_status"] == ("verifier_deferred")
    assert update.get("jump_to") is None


def test_rejects_invented_verifier_task_reference_before_tool_execution():
    middleware = SubagentDispatchPolicyMiddleware()
    candidate = AIMessage(
        id="invented-lineage",
        content="启动核验。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "verifier-invented",
                description="独立核验",
                prompt="核验结论",
                subagent_type="verifier",
                source_refs=["task:parent-compare"],
            )
        ],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="调查异常"), candidate]},
        _runtime(),
    )

    assert update is not None
    assert update["jump_to"] == "model"
    assert update["messages"][0].tool_calls == []
    assert update["messages"][0].additional_kwargs["hide_from_ui"] is True


def test_next_model_request_receives_hidden_exact_lineage_reminder():
    middleware = SubagentDispatchPolicyMiddleware()
    runtime = _runtime()
    candidate = AIMessage(
        content="启动核验。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "verifier-too-early",
                description="独立核验",
                prompt="核验结论",
                subagent_type="verifier",
                source_refs=[],
            )
        ],
    )
    messages = [HumanMessage(content="调查异常"), candidate]
    middleware.after_model({"messages": messages}, runtime)

    captured = {}
    request = MagicMock()
    request.messages = messages
    request.runtime = runtime
    request.override.side_effect = lambda **changes: MagicMock(
        messages=changes["messages"],
        runtime=runtime,
    )

    middleware.wrap_model_call(
        request,
        lambda updated: captured.setdefault("messages", updated.messages) or MagicMock(),
    )

    reminder = captured["messages"][-1]
    assert isinstance(reminder, HumanMessage)
    assert reminder.name == "subagent_dispatch_policy_reminder"
    assert reminder.additional_kwargs["hide_from_ui"] is True
    assert "wait_task" in reminder.content
    assert "task:<精确 task_id>" in reminder.content
    assert "任务描述、自造别名或占位符" in reminder.content


def test_rejects_exact_duplicate_dispatch_before_creating_another_task():
    middleware = SubagentDispatchPolicyMiddleware(max_tasks_per_run=6)
    description = "地域分段检查"
    prompt = "调用地域工具检查运输变化。"
    candidate = AIMessage(
        id="duplicate-candidate",
        content="再次启动。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "task-duplicate-2",
                description=description,
                prompt=prompt,
                subagent_type="analyst",
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=1,
                max_tool_calls=1,
            )
        ],
    )
    messages = [
        HumanMessage(content="调查异常"),
        *_failed_task_exchange(
            "task-duplicate-1",
            description=description,
            prompt=prompt,
        ),
        candidate,
    ]

    update = middleware.after_model({"messages": messages}, _runtime())

    assert update is not None
    assert update["jump_to"] == "model"
    replacement = update["messages"][0]
    assert replacement.tool_calls == []
    assert replacement.additional_kwargs["subagent_dispatch_policy_status"] == ("dispatch_guarded")
    assert replacement.additional_kwargs["subagent_dispatch_policy_rejection_reasons"] == ["duplicate_dispatch"]

    captured = {}
    request = MagicMock(messages=messages, runtime=_runtime())
    request.override.side_effect = lambda **changes: MagicMock(
        messages=changes["messages"],
        runtime=request.runtime,
    )
    middleware.wrap_model_call(
        request,
        lambda updated: captured.setdefault("messages", updated.messages) or MagicMock(),
    )
    assert "完全相同的 spawn_task 已被跳过" in captured["messages"][-1].content


def test_does_not_treat_failed_spawn_tool_execution_as_persisted_duplicate():
    middleware = SubagentDispatchPolicyMiddleware(max_tasks_per_run=6)
    description = "履约窗口计算"
    prompt = "计算默认窗口指标。"
    failed_call = _tool_call(
        "spawn_task",
        "spawn-failed-before-create",
        description=description,
        prompt=prompt,
        subagent_type="analyst",
        skills=["fulfillment-investigation"],
        tools=["commerce_compare_windows"],
        max_tool_rounds=4,
        max_tool_calls=5,
    )
    candidate = AIMessage(
        content="按修正后的 Profile 预算再次创建。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "spawn-retry",
                description=description,
                prompt=prompt,
                subagent_type="analyst",
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=4,
                max_tool_calls=5,
            )
        ],
    )
    messages = [
        HumanMessage(content="调查异常"),
        AIMessage(content="", tool_calls=[failed_call]),
        ToolMessage(
            content=json.dumps(
                {
                    "ok": False,
                    "error": "requested max_tool_rounds exceeds the Subagent Profile budget",
                }
            ),
            tool_call_id="spawn-failed-before-create",
        ),
        candidate,
    ]

    assert middleware.after_model({"messages": messages}, _runtime()) is None


def test_failed_task_budget_blocks_optional_dispatch_but_keeps_verifier_path():
    middleware = SubagentDispatchPolicyMiddleware(
        max_tasks_per_run=6,
        max_failed_tasks_per_run=2,
    )
    messages = [
        HumanMessage(content="调查异常"),
        *_completed_task_exchange("task-analyst-ok", "analyst"),
        *_failed_task_exchange(
            "task-failed-1",
            description="可选角度一",
            prompt="检查可选角度一",
        ),
        *_failed_task_exchange(
            "task-failed-2",
            description="可选角度二",
            prompt="检查可选角度二",
        ),
    ]
    optional = AIMessage(
        id="optional-after-failures",
        content="再检查一个可选角度。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "task-optional-3",
                description="可选角度三",
                prompt="检查可选角度三",
                subagent_type="analyst",
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=1,
                max_tool_calls=1,
            )
        ],
    )

    blocked = middleware.after_model(
        {"messages": [*messages, optional]},
        _runtime(),
    )

    assert blocked is not None
    assert blocked["messages"][0].tool_calls == []
    assert blocked["messages"][0].additional_kwargs["subagent_dispatch_policy_rejection_reasons"] == ["failed_task_budget_exhausted"]

    verifier = AIMessage(
        id="verifier-after-failures",
        content="启动必要核验。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "task-verifier-ok",
                description="独立核验",
                prompt="独立重算核心指标",
                subagent_type="verifier",
                source_refs=["task:task-analyst-ok"],
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=1,
                max_tool_calls=1,
            )
        ],
    )

    assert (
        middleware.after_model(
            {"messages": [*messages, verifier]},
            _runtime("run-2"),
        )
        is None
    )


def test_total_task_budget_reserves_one_required_verifier_slot():
    middleware = SubagentDispatchPolicyMiddleware(max_tasks_per_run=1)
    messages = [
        HumanMessage(content="调查异常"),
        *_completed_task_exchange("task-analyst-only", "analyst"),
    ]
    verifier = AIMessage(
        content="启动必要核验。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "task-verifier-reserved",
                description="独立核验",
                prompt="独立重算核心指标",
                subagent_type="verifier",
                source_refs=["task:task-analyst-only"],
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=1,
                max_tool_calls=1,
            )
        ],
    )

    assert (
        middleware.after_model(
            {"messages": [*messages, verifier]},
            _runtime(),
        )
        is None
    )


def test_allows_verifier_referencing_completed_current_run_task():
    middleware = SubagentDispatchPolicyMiddleware()
    messages = [
        HumanMessage(content="调查异常"),
        *_completed_task_exchange("task-analyst", "analyst"),
        AIMessage(
            content="启动独立核验。",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    "task-verifier",
                    description="独立核验",
                    prompt="重新计算核心指标",
                    subagent_type="verifier",
                    source_refs=["task:task-analyst"],
                )
            ],
        ),
    ]

    assert middleware.after_model({"messages": messages}, _runtime()) is None


def test_scope_rules_normalize_parallel_fulfillment_tasks_before_execution():
    window_contract = "时间窗口使用半开区间 [start, end)；相邻窗口必须保持 baseline_end == current_start，不得减一天。"
    middleware = SubagentDispatchPolicyMiddleware(
        scope_rules=[
            {
                "name": "fulfillment-coverage",
                "subagent_type": "explore",
                "match_skills_all": ["fulfillment-investigation"],
                "prompt_keywords_any": ["覆盖", "时间范围"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": ["commerce_seller_coverage"],
                "max_tool_rounds": 1,
                "max_tool_calls": 1,
            },
            {
                "name": "fulfillment-window",
                "subagent_type": "analyst",
                "match_skills_all": ["fulfillment-investigation"],
                "prompt_keywords_any": ["窗口", "指标比较"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": [
                    "commerce_compare_windows",
                    "commerce_evidence_query",
                ],
                "prompt_suffix": window_contract,
                "max_tool_rounds": 2,
                "max_tool_calls": 2,
            },
        ]
    )
    candidate = AIMessage(
        id="parallel-scope",
        content="并行检查覆盖和窗口。",
        tool_calls=[
            _tool_call(
                "spawn_task",
                "task-explore",
                description="确认卖家数据覆盖",
                prompt="确认全量时间范围和覆盖率",
                subagent_type="explore",
                source_refs=[],
                skills=["fulfillment-investigation", "commerce-diagnostic-synthesis"],
                tools=["commerce_seller_coverage", "commerce_evidence_query"],
                max_tool_rounds=4,
                max_tool_calls=4,
            ),
            _tool_call(
                "spawn_task",
                "task-analyst",
                description="履约窗口指标比较",
                prompt="比较两个窗口的履约指标",
                subagent_type="analyst",
                source_refs=[],
                skills=["fulfillment-investigation"],
                tools=["commerce_compare_windows"],
                max_tool_rounds=4,
                max_tool_calls=4,
            ),
        ],
    )

    update = middleware.after_model(
        {"messages": [HumanMessage(content="调查履约异常"), candidate]},
        _runtime(),
    )

    assert update is not None
    calls = update["messages"][0].tool_calls
    assert calls[0]["args"]["skills"] == ["fulfillment-investigation"]
    assert calls[0]["args"]["tools"] == ["commerce_seller_coverage"]
    assert calls[0]["args"]["max_tool_rounds"] == 1
    assert calls[0]["args"]["max_tool_calls"] == 1
    assert calls[1]["args"]["skills"] == ["fulfillment-investigation"]
    assert calls[1]["args"]["tools"] == [
        "commerce_compare_windows",
        "commerce_evidence_query",
    ]
    assert calls[1]["args"]["max_tool_rounds"] == 2
    assert calls[1]["args"]["max_tool_calls"] == 2
    assert calls[1]["args"]["prompt"].endswith(window_contract)
    assert calls[1]["args"]["prompt"].count(window_contract) == 1


def test_scope_rule_prompt_suffix_is_idempotent():
    window_contract = "时间窗口使用半开区间 [start, end)，本说明覆盖含两端等冲突措辞。"
    rule = {
        "name": "fulfillment-window",
        "subagent_type": "analyst",
        "match_skills_all": ["fulfillment-investigation"],
        "prompt_keywords_any": ["窗口"],
        "enforced_skills": ["fulfillment-investigation"],
        "enforced_tools": ["commerce_compare_windows"],
        "prompt_suffix": window_contract,
        "max_tool_rounds": 1,
        "max_tool_calls": 1,
    }
    call = _tool_call(
        "spawn_task",
        "task-analyst",
        description="履约窗口比较",
        prompt=f"比较窗口。\n\n{window_contract}",
        subagent_type="analyst",
        source_refs=[],
        skills=["fulfillment-investigation"],
        tools=["commerce_compare_windows"],
        max_tool_rounds=1,
        max_tool_calls=1,
    )

    normalized = SubagentDispatchPolicyMiddleware._apply_scope_rule(
        call,
        rule,
        {},
    )

    assert normalized["args"]["prompt"].count(window_contract) == 1


def test_verifier_scope_inherits_source_tools_and_drops_unrelated_capability():
    middleware = SubagentDispatchPolicyMiddleware(
        scope_rules=[
            {
                "name": "fulfillment-verifier",
                "subagent_type": "verifier",
                "match_skills_all": ["fulfillment-investigation"],
                "prompt_keywords_any": ["核验", "重算"],
                "enforced_skills": ["fulfillment-investigation"],
                "enforced_tools": ["commerce_evidence_query"],
                "inherit_source_tools": True,
                "max_tool_rounds": 2,
                "max_tool_calls": 3,
            }
        ]
    )
    messages = [
        HumanMessage(content="调查履约异常"),
        *_completed_task_exchange(
            "task-explore",
            "explore",
            tools=["commerce_seller_coverage"],
        ),
        *_completed_task_exchange(
            "task-analyst",
            "analyst",
            tools=["commerce_compare_windows", "commerce_evidence_query"],
            max_tool_rounds=2,
            max_tool_calls=2,
        ),
        AIMessage(
            id="verifier-scope",
            content="启动独立核验。",
            tool_calls=[
                _tool_call(
                    "spawn_task",
                    "task-verifier",
                    description="独立核验履约阶段",
                    prompt="独立重算覆盖和窗口并核验结论",
                    subagent_type="verifier",
                    source_refs=["task:task-explore", "task:task-analyst"],
                    skills=["fulfillment-investigation"],
                    tools=[
                        "commerce_compare_windows",
                        "commerce_evidence_query",
                        "commerce_geographic_segments",
                    ],
                    max_tool_rounds=3,
                    max_tool_calls=5,
                )
            ],
        ),
    ]

    update = middleware.after_model({"messages": messages}, _runtime())

    assert update is not None
    args = update["messages"][0].tool_calls[0]["args"]
    assert args["tools"] == [
        "commerce_seller_coverage",
        "commerce_compare_windows",
        "commerce_evidence_query",
    ]
    assert args["max_tool_rounds"] == 2
    assert args["max_tool_calls"] == 3

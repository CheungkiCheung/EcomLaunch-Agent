"""Deterministic contracts for the dynamic Chat-first release harness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.commerce.evaluation.chat_dynamic_release import (
    DynamicChatReleaseReport,
    DynamicChatReleaseSpec,
    DynamicModelCallEvidence,
    DynamicParentToolCall,
    DynamicParentToolCallBatch,
    DynamicParentToolResult,
    DynamicPreflightEvidence,
    DynamicTaskPlan,
    DynamicTaskReleaseEvidence,
    _dynamic_live_app_config,
    _final_answer_issues_only,
    _response_guard_can_repair,
    _response_guard_forbidden_terms,
    build_dynamic_chat_audit,
    evaluate_dynamic_chat_release,
    persist_dynamic_chat_audit,
)
from deerflow.config.app_config import AppConfig


def _plan(
    subagent_type: str,
    *,
    tools: tuple[str, ...] = ("commerce_compare_windows",),
    max_tool_rounds: int = 1,
    max_tool_calls: int | None = None,
) -> DynamicTaskPlan:
    return DynamicTaskPlan(
        subagent_type=subagent_type,
        skills=("fulfillment-investigation",),
        tools=tools,
        max_tool_rounds=max_tool_rounds,
        expected_tool_names=tools,
        max_tool_calls=max_tool_calls,
    )


def test_dynamic_release_spec_freezes_parallel_first_wave_and_fresh_verifier():
    spec = DynamicChatReleaseSpec(
        case_key="GC-FULFILLMENT-001",
        prompt="调查真实履约变化并独立核验。",
        first_wave=(
            _plan(
                "explore",
                tools=("commerce_dataset_profile", "commerce_capabilities"),
            ),
            _plan(
                "analyst",
                tools=(
                    "commerce_compare_windows",
                    "commerce_evidence_query",
                ),
                max_tool_rounds=2,
            ),
        ),
        verifier=_plan(
            "verifier",
            tools=("commerce_compare_windows", "commerce_evidence_query"),
            max_tool_rounds=2,
        ),
        final_required_all=("mobs_",),
        final_required_any=(("反证", "替代解释", "不能证明"),),
        final_forbidden=("真实GMV",),
        max_requests=24,
        max_tokens=350_000,
    )

    assert tuple(plan.subagent_type for plan in spec.first_wave) == (
        "explore",
        "analyst",
    )
    assert spec.verifier.subagent_type == "verifier"
    assert spec.verifier.max_tool_rounds == 2
    assert spec.parent_required_tools == (
        "commerce_ingest_uploads",
        "commerce_capabilities",
        "spawn_task",
        "wait_task",
    )


@pytest.mark.parametrize(
    ("first_wave", "verifier"),
    [
        ((_plan("explore"), _plan("explore")), _plan("verifier")),
        ((_plan("verifier"), _plan("analyst")), _plan("verifier")),
        ((_plan("explore"), _plan("analyst")), _plan("analyst")),
    ],
)
def test_dynamic_release_spec_rejects_ambiguous_or_non_fresh_topology(
    first_wave: tuple[DynamicTaskPlan, ...],
    verifier: DynamicTaskPlan,
):
    with pytest.raises(ValidationError):
        DynamicChatReleaseSpec(
            case_key="GC-FULFILLMENT-001",
            prompt="调查并核验。",
            first_wave=first_wave,
            verifier=verifier,
            final_required_all=("mobs_",),
            max_requests=24,
            max_tokens=350_000,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"skills": ()},
        {"tools": ()},
        {"tools": ("commerce_compare_windows", "commerce_compare_windows")},
        {"max_tool_rounds": 0},
        {
            "tools": ("commerce_compare_windows",),
            "expected_tool_names": ("commerce_evidence_query",),
        },
    ],
)
def test_dynamic_task_plan_is_minimal_and_cannot_expect_unavailable_tools(kwargs):
    payload = {
        "subagent_type": "analyst",
        "skills": ("fulfillment-investigation",),
        "tools": ("commerce_compare_windows",),
        "max_tool_rounds": 1,
        "expected_tool_names": ("commerce_compare_windows",),
    }
    payload.update(kwargs)

    with pytest.raises(ValidationError):
        DynamicTaskPlan(**payload)


def test_task_plan_allows_bounded_repeat_calls_without_expanding_tool_envelope():
    plan = DynamicTaskPlan(
        subagent_type="analyst",
        skills=("review-experience-diagnosis",),
        tools=("commerce_compare_windows", "commerce_evidence_query"),
        max_tool_rounds=2,
        expected_tool_names=("commerce_compare_windows", "commerce_evidence_query"),
        max_tool_calls=3,
    )

    assert plan.effective_max_tool_calls == 3


def test_release_evaluator_accepts_bounded_repeat_evidence_query():
    spec, report = _release_fixture()
    analyst_plan = spec.first_wave[1].model_copy(update={"max_tool_calls": 3})
    bounded_spec = spec.model_copy(update={"first_wave": (spec.first_wave[0], analyst_plan)})
    analyst = report.tasks[1].model_copy(
        update={
            "max_tool_calls": 3,
            "tool_names": (
                "commerce_compare_windows",
                "commerce_evidence_query",
                "commerce_evidence_query",
            ),
        }
    )
    spawn_batch = report.parent_tool_call_batches[2]
    analyst_spawn = spawn_batch.calls[1].model_copy(
        update={
            "args": {
                **spawn_batch.calls[1].args,
                "max_tool_calls": 3,
            }
        }
    )
    bounded_report = report.model_copy(
        update={
            "parent_tool_call_batches": (
                *report.parent_tool_call_batches[:2],
                spawn_batch.model_copy(update={"calls": (spawn_batch.calls[0], analyst_spawn)}),
                *report.parent_tool_call_batches[3:],
            ),
            "tasks": (report.tasks[0], analyst, report.tasks[2]),
        }
    )

    assert evaluate_dynamic_chat_release(bounded_report, bounded_spec) == ()

    over_limit = analyst.model_copy(update={"tool_names": (*analyst.tool_names, "commerce_evidence_query")})
    broken = report.model_copy(update={"tasks": (report.tasks[0], over_limit, report.tasks[2])})
    assert any("Tool 调用总数超限" in issue for issue in evaluate_dynamic_chat_release(broken, bounded_spec))


def _release_fixture() -> tuple[DynamicChatReleaseSpec, DynamicChatReleaseReport]:
    explore = _plan(
        "explore",
        tools=("commerce_dataset_profile", "commerce_capabilities"),
    )
    analyst = _plan(
        "analyst",
        tools=("commerce_compare_windows", "commerce_evidence_query"),
        max_tool_rounds=2,
    )
    verifier = _plan(
        "verifier",
        tools=("commerce_compare_windows", "commerce_evidence_query"),
        max_tool_rounds=2,
    )
    spec = DynamicChatReleaseSpec(
        case_key="GC-FULFILLMENT-001",
        prompt="调查真实履约变化并独立核验。",
        first_wave=(explore, analyst),
        verifier=verifier,
        final_required_all=("mobs_", "数据限制"),
        final_required_any=(("反证", "替代解释", "不能证明"),),
        final_forbidden=("真实GMV", "根因已经证实"),
        max_requests=12,
        max_tokens=50_000,
    )
    now = datetime.now(UTC)
    first_task_ids = ("task-explore", "task-analyst")
    report = DynamicChatReleaseReport(
        case_key=spec.case_key,
        run_id="run-1",
        run_status="success",
        bridge_ended=True,
        configured_alias="deepseek-reasoner",
        configured_model="deepseek-v4-flash",
        configured_max_retries=0,
        preflight=DynamicPreflightEvidence(
            run_id="preflight-1",
            status="passed",
            actual_model_identity="deepseek-v4-flash",
            provider_request_id="request-preflight",
            total_tokens=10,
            retry_count=0,
        ),
        parent_tool_call_batches=(
            DynamicParentToolCallBatch(
                batch_index=0,
                calls=(DynamicParentToolCall(name="commerce_ingest_uploads", args={}),),
            ),
            DynamicParentToolCallBatch(
                batch_index=1,
                calls=(DynamicParentToolCall(name="commerce_capabilities", args={}),),
            ),
            DynamicParentToolCallBatch(
                batch_index=2,
                calls=(
                    DynamicParentToolCall(
                        name="spawn_task",
                        args={
                            "subagent_type": "explore",
                            "skills": list(explore.skills),
                            "tools": list(explore.tools),
                            "max_tool_rounds": explore.max_tool_rounds,
                            "max_tool_calls": explore.effective_max_tool_calls,
                        },
                    ),
                    DynamicParentToolCall(
                        name="spawn_task",
                        args={
                            "subagent_type": "analyst",
                            "skills": list(analyst.skills),
                            "tools": list(analyst.tools),
                            "max_tool_rounds": analyst.max_tool_rounds,
                            "max_tool_calls": analyst.effective_max_tool_calls,
                        },
                    ),
                ),
            ),
            DynamicParentToolCallBatch(
                batch_index=3,
                calls=(DynamicParentToolCall(name="wait_task", args={"mode": "all"}),),
            ),
            DynamicParentToolCallBatch(
                batch_index=4,
                calls=(
                    DynamicParentToolCall(
                        name="spawn_task",
                        args={
                            "subagent_type": "verifier",
                            "skills": list(verifier.skills),
                            "tools": list(verifier.tools),
                            "max_tool_rounds": verifier.max_tool_rounds,
                            "max_tool_calls": verifier.effective_max_tool_calls,
                            "source_refs": [f"task:{value}" for value in first_task_ids],
                        },
                    ),
                ),
            ),
            DynamicParentToolCallBatch(
                batch_index=5,
                calls=(DynamicParentToolCall(name="wait_task", args={}),),
            ),
        ),
        parent_model_calls=(
            DynamicModelCallEvidence(
                actual_model_identity="deepseek-v4-flash",
                provider_request_id="request-parent-1",
                stop_reason="tool_calls",
                total_tokens=1_000,
            ),
            DynamicModelCallEvidence(
                actual_model_identity="deepseek-v4-flash",
                provider_request_id="request-parent-2",
                stop_reason="stop",
                total_tokens=1_000,
            ),
        ),
        tasks=(
            DynamicTaskReleaseEvidence(
                task_id=first_task_ids[0],
                subagent_type="explore",
                status="completed",
                source_refs=(),
                available_skills=explore.skills,
                available_tools=explore.tools,
                max_tool_rounds=explore.max_tool_rounds,
                max_tool_calls=explore.effective_max_tool_calls,
                created_at=now,
                completed_at=now + timedelta(seconds=1),
                tool_names=explore.expected_tool_names,
                model_calls=(
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-explore-1",
                        stop_reason="tool_calls",
                    ),
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-explore-2",
                        stop_reason="stop",
                    ),
                ),
                total_tokens=5_000,
            ),
            DynamicTaskReleaseEvidence(
                task_id=first_task_ids[1],
                subagent_type="analyst",
                status="completed",
                source_refs=(),
                available_skills=analyst.skills,
                available_tools=analyst.tools,
                max_tool_rounds=analyst.max_tool_rounds,
                max_tool_calls=analyst.effective_max_tool_calls,
                created_at=now,
                completed_at=now + timedelta(seconds=2),
                tool_names=analyst.expected_tool_names,
                model_calls=(
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-analyst-1",
                        stop_reason="tool_calls",
                    ),
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-analyst-2",
                        stop_reason="stop",
                    ),
                ),
                total_tokens=6_000,
            ),
            DynamicTaskReleaseEvidence(
                task_id="task-verifier",
                subagent_type="verifier",
                status="completed",
                source_refs=tuple(f"task:{value}" for value in first_task_ids),
                available_skills=verifier.skills,
                available_tools=verifier.tools,
                max_tool_rounds=verifier.max_tool_rounds,
                max_tool_calls=verifier.effective_max_tool_calls,
                created_at=now + timedelta(seconds=3),
                completed_at=now + timedelta(seconds=4),
                tool_names=verifier.expected_tool_names,
                model_calls=(
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-verifier-1",
                        stop_reason="tool_calls",
                    ),
                    DynamicModelCallEvidence(
                        actual_model_identity="deepseek-v4-flash",
                        provider_request_id="request-verifier-2",
                        stop_reason="stop",
                    ),
                ),
                total_tokens=6_000,
            ),
        ),
        final_text="延迟变化见 mobs_abc；反证仍存在。数据限制包括缺少库存字段。",
        audit_path="/tmp/audit.json",
    )
    return spec, report


def test_release_evaluator_accepts_auditable_dynamic_chain():
    spec, report = _release_fixture()

    assert evaluate_dynamic_chat_release(report, spec) == ()
    assert report.request_count == 8
    assert report.total_tokens == 19_000


def test_response_guard_repairs_only_final_answer_issues():
    assert _final_answer_issues_only(
        (
            "最终回答包含禁止结论：显著高于",
            "最终回答缺少关键事实模式：SP...26",
        )
    )
    assert not _final_answer_issues_only(
        (
            "最终回答包含禁止结论：显著高于",
            "Durable verifier Task 未完成：failed",
        )
    )
    assert not _final_answer_issues_only(())


def test_response_guard_does_not_reconstruct_a_harness_blocked_answer():
    issues = (
        "最终回答缺少必需内容：mobs_",
        "最终回答缺少关键事实模式：订单量...141...202",
    )

    assert not _response_guard_can_repair(
        "本次回答被 Harness 阻止交付：模型连续使用了超出证据范围的确定性表述。",
        issues,
    )
    assert _response_guard_can_repair(
        "订单量从 141 单变化到 202 单，但当前答案需要调整表达。",
        issues,
    )


def test_response_guard_exposes_only_forbidden_terms_present_in_current_issues():
    issues = (
        "最终回答包含禁止结论：显著高于",
        "最终回答缺少必需内容：mobs_",
    )

    assert _response_guard_forbidden_terms(issues) == ("显著高于",)
    assert "春节" not in _response_guard_forbidden_terms(issues)


def test_response_guard_repair_is_counted_as_parent_request_and_audited_by_hash():
    spec, report = _release_fixture()
    initial_issues = ("最终回答包含禁止结论：显著高于",)
    repaired = report.model_copy(
        update={
            "parent_model_calls": (
                *report.parent_model_calls,
                DynamicModelCallEvidence(
                    actual_model_identity="deepseek-v4-flash",
                    provider_request_id="request-response-guard",
                    stop_reason="stop",
                    input_tokens=800,
                    output_tokens=200,
                    total_tokens=1_000,
                ),
            ),
            "response_guard_repair_count": 1,
            "response_guard_initial_issues": initial_issues,
        }
    )

    assert repaired.request_count == report.request_count + 1
    assert repaired.parent_tokens == report.parent_tokens + 1_000
    assert evaluate_dynamic_chat_release(repaired, spec) == ()

    payload = build_dynamic_chat_audit(repaired, spec=spec, issues=())
    assert payload["response_guard"] == {
        "repair_count": 1,
        "initial_issues": list(initial_issues),
        "error_code": None,
    }
    assert payload["request_count"] == report.request_count + 1
    assert payload["parent_tokens"] == report.parent_tokens + 1_000
    assert "final_text" not in payload
    assert len(payload["final_response_sha256"]) == 64


def test_response_guard_repair_cannot_hide_a_remaining_forbidden_claim():
    spec, report = _release_fixture()
    forbidden_spec = spec.model_copy(update={"final_forbidden": (*spec.final_forbidden, "显著高于")})
    still_broken = report.model_copy(
        update={
            "final_text": f"{report.final_text} 当前表现显著高于同行。",
            "response_guard_repair_count": 1,
            "response_guard_initial_issues": ("最终回答包含禁止结论：显著高于",),
        }
    )

    issues = evaluate_dynamic_chat_release(still_broken, forbidden_spec)

    assert "最终回答包含禁止结论：显著高于" in issues


def test_response_guard_failure_audit_keeps_only_safe_error_code():
    spec, report = _release_fixture()
    failed = report.model_copy(
        update={
            "execution_error": "ResponseGuardError: AuthenticationError",
            "response_guard_repair_count": 1,
            "response_guard_initial_issues": ("最终回答包含禁止结论：显著高于",),
            "response_guard_error_code": "AuthenticationError",
        }
    )
    issues = evaluate_dynamic_chat_release(failed, spec)

    payload = build_dynamic_chat_audit(failed, spec=spec, issues=issues)

    assert payload["response_guard"]["error_code"] == "AuthenticationError"
    assert payload["response_guard"].keys() == {
        "repair_count",
        "initial_issues",
        "error_code",
    }
    assert not any("sk-" in str(value) for value in payload["response_guard"].values())
    assert any("ResponseGuardError: AuthenticationError" in issue for issue in issues)


def test_release_evaluator_accepts_real_task_overlap_across_parent_responses():
    spec, report = _release_fixture()
    first_wave = report.parent_tool_call_batches[2]
    split_batches = (
        *report.parent_tool_call_batches[:2],
        DynamicParentToolCallBatch(
            batch_index=2,
            calls=(first_wave.calls[0],),
        ),
        DynamicParentToolCallBatch(
            batch_index=3,
            calls=(first_wave.calls[1],),
        ),
        *(batch.model_copy(update={"batch_index": batch.batch_index + 1}) for batch in report.parent_tool_call_batches[3:]),
    )
    overlapping = report.model_copy(update={"parent_tool_call_batches": split_batches})

    assert evaluate_dynamic_chat_release(overlapping, spec) == ()


def test_release_evaluator_audits_bounded_parent_tool_recovery():
    spec, report = _release_fixture()
    failed_call = DynamicParentToolCall(
        tool_call_id="call-failed-verifier",
        name="spawn_task",
        args={
            "subagent_type": "verifier",
            "skills": ["fulfillment-investigation"],
            "tools": ["commerce_compare_windows", "commerce_evidence_query"],
            "max_tool_rounds": 2,
        },
    )
    recovered = report.model_copy(
        update={
            "parent_tool_call_batches": (
                *report.parent_tool_call_batches,
                DynamicParentToolCallBatch(
                    batch_index=99,
                    calls=(failed_call,),
                ),
            ),
            "parent_tool_results": (
                DynamicParentToolResult(
                    tool_call_id="call-failed-verifier",
                    name="spawn_task",
                    status="error",
                    content_sha256="a" * 64,
                ),
            ),
        }
    )

    assert evaluate_dynamic_chat_release(recovered, spec) == ()

    too_many = recovered.model_copy(
        update={
            "parent_tool_results": tuple(
                DynamicParentToolResult(
                    tool_call_id=f"failed-{index}",
                    name="spawn_task",
                    status="error",
                    content_sha256=f"{index + 1:064x}",
                )
                for index in range(3)
            )
        }
    )
    assert any("Parent Tool 错误次数超限" in issue for issue in evaluate_dynamic_chat_release(too_many, spec))


def test_release_evaluator_requires_frozen_numeric_fact_patterns():
    spec, report = _release_fixture()
    peer_spec = spec.model_copy(update={"final_required_patterns": (r"RJ.{0,40}(?:订单数|order_count)?.{0,20}\b7\b",)})
    wrong = report.model_copy(update={"final_text": report.final_text + "\nRJ 地域订单数为 2。"})
    correct = report.model_copy(update={"final_text": report.final_text + "\nRJ 地域订单数为 7。"})

    assert any("关键事实模式" in issue for issue in evaluate_dynamic_chat_release(wrong, peer_spec))
    assert not any("关键事实模式" in issue for issue in evaluate_dynamic_chat_release(correct, peer_spec))


def test_release_evaluator_reports_topology_safety_and_freshness_failures():
    spec, report = _release_fixture()
    broken = report.model_copy(
        update={
            "configured_max_retries": 2,
            "final_text": "根因已经证实，真实GMV 已增长。",
            "tasks": report.tasks[:-1],
        }
    )

    issues = evaluate_dynamic_chat_release(broken, spec)

    assert any("max_retries" in issue for issue in issues)
    assert any("verifier" in issue.casefold() for issue in issues)
    assert any("禁止" in issue for issue in issues)
    assert any("中文" not in issue and "mobs_" in issue for issue in issues)


def test_forbidden_claim_matcher_allows_explicit_negation_but_catches_assertion():
    spec, report = _release_fixture()
    safety_spec = spec.model_copy(update={"final_forbidden": ("评分下降", "低分率上升")})
    negated = report.model_copy(update={"final_text": ("履约证据见 mobs_abc。由于没有 order_reviews，无法判断评分下降或低分率上升；数据限制明确，需要补数。")})

    negated_issues = evaluate_dynamic_chat_release(negated, safety_spec)
    assert not any("包含禁止结论" in issue for issue in negated_issues)

    not_in_scope = report.model_copy(update={"final_text": ("履约证据见 mobs_abc。由于没有评价数据，本次不涉及评分下降或低分率上升的分析与结论；数据限制明确，需要补数。")})
    not_in_scope_issues = evaluate_dynamic_chat_release(not_in_scope, safety_spec)
    assert not any("包含禁止结论" in issue for issue in not_in_scope_issues)

    trailing_negation = report.model_copy(update={"final_text": ("履约证据见 mobs_abc。所有关于评分下降或低分率上升的推论均不允许；数据限制明确，需要补数。")})
    trailing_issues = evaluate_dynamic_chat_release(trailing_negation, safety_spec)
    assert not any("包含禁止结论" in issue for issue in trailing_issues)

    direct_inference_negation = report.model_copy(update={"final_text": ("证据见 mobs_abc。未执行统计检验，不能直接推断为显著高于；数据限制明确，需要补数。")})
    direct_inference_issues = evaluate_dynamic_chat_release(
        direct_inference_negation,
        safety_spec.model_copy(update={"final_forbidden": ("显著高于",)}),
    )
    assert not any("包含禁止结论" in issue for issue in direct_inference_issues)

    asserted = report.model_copy(update={"final_text": ("履约证据见 mobs_abc。虽然此前无法判断，但当前评分下降，低分率上升；数据限制明确。")})
    asserted_issues = evaluate_dynamic_chat_release(asserted, safety_spec)
    assert {issue for issue in asserted_issues if "包含禁止结论" in issue} == {
        "最终回答包含禁止结论：评分下降",
        "最终回答包含禁止结论：低分率上升",
    }


def test_dynamic_release_audit_is_secret_free_hashed_and_immutable(tmp_path):
    spec, report = _release_fixture()
    issues = evaluate_dynamic_chat_release(report, spec)

    payload = build_dynamic_chat_audit(report, spec=spec, issues=issues)

    assert "final_text" not in payload
    assert payload["final_response_sha256"]
    assert payload["request_count"] == report.request_count
    assert payload["total_tokens"] == report.total_tokens
    assert "input_tokens" in payload["tasks"][0]
    assert "output_tokens" in payload["tasks"][0]
    assert "input_tokens" in payload["parent_model_calls"][0]
    assert "output_tokens" in payload["parent_model_calls"][0]
    assert payload["passed"] is True
    assert payload["spec"]["prompt_sha256"]
    assert "prompt" not in payload["spec"]

    path = persist_dynamic_chat_audit(
        payload,
        audit_root=tmp_path,
        audit_id="audit-1",
    )
    assert path.is_file()
    with pytest.raises(FileExistsError):
        persist_dynamic_chat_audit(
            payload,
            audit_root=tmp_path,
            audit_id="audit-1",
        )


def test_dynamic_live_profiles_leave_room_for_evidence_bounded_synthesis():
    config = _dynamic_live_app_config(AppConfig.from_file())

    assert config.get_model_config("deepseek-reasoner").temperature == 0
    assert {name: config.subagents.custom_agents[name].max_output_tokens for name in ("explore", "analyst", "verifier")} == {"explore": 3_200, "analyst": 3_200, "verifier": 3_200}
    assert all(config.subagents.custom_agents[name].model_max_retries == 0 for name in ("explore", "analyst", "verifier"))

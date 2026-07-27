"""Fresh DeepSeek V4 Gate for the Chat-first dynamic fulfillment chain."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.commerce.evaluation.chat_dynamic_release import (
    DynamicChatReleaseSpec,
    DynamicTaskPlan,
    run_dynamic_chat_release_case,
)

REPO_ROOT = Path(__file__).parents[4]
CASE_DIR = REPO_ROOT / "evals" / "commerce" / "cases" / "GC-FULFILLMENT-001"
AUDIT_ROOT = REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "chat-dynamic-release"

_LATE_DELIVERY_PAIR_PATTERN = (
    r"(?:(?:晚发货率|晚到率|迟发率|延迟交付率|延迟率|late_delivery_rate)"
    r".{0,180}(?:3\.5(?:5|46\d?)?%|0\.035(?:46\d?)?)"
    r".{0,160}(?:35\.1(?:5|48\d?)?%|0\.351(?:48\d?)?)|"
    r"(?:晚发货率|晚到率|迟发率|延迟交付率|延迟率|late_delivery_rate)"
    r".{0,180}(?:35\.1(?:5|48\d?)?%|0\.351(?:48\d?)?)"
    r".{0,240}(?:3\.5(?:5|46\d?)?%|0\.035(?:46\d?)?))"
)

FULFILLMENT_SPEC = DynamicChatReleaseSpec(
    case_key="GC-FULFILLMENT-001",
    prompt="""
你正在处理一份刚上传的真实电商订单数据。请调查卖家
4869f7a5dfa277a7dca6462dcf3b52b2 的履约变化：
基线窗口 2017-12-02T00:00:00 到 2018-01-31T00:00:00，
当前窗口 2018-01-31T00:00:00 到 2018-04-01T00:00:00。
所有窗口使用半开区间 [start, end)，相邻窗口保持 baseline_end == current_start；禁止减一天、
加一天、改成当天 23:59:59 或自行移动边界。

必须遵循以下过程：
1. 先单独调用 commerce_ingest_uploads 接入当前线程全部支持的数据文件，等待它返回成功后，
   下一轮再调用 commerce_capabilities 检查能力。这两个 Tool 有数据依赖，绝不能在同一响应并行。
2. 这是复杂任务。数据接入后，在同一个模型响应中并行启动两个 Durable Task：
   - explore：Parent 已完成 Capability 检查；加载 fulfillment-investigation Skill，只允许
     commerce_seller_coverage，max_tool_rounds=1、max_tool_calls=1；使用全量关联确认该卖家的精确
     first_order_date、last_order_date、总订单数和关键履约字段覆盖，禁止从抽样记录推断时间范围；
   - analyst：加载 fulfillment-investigation Skill，必须调用 commerce_compare_windows，区分卖家处理
     与承运运输阶段，并用一次 commerce_evidence_query 合并抽查来源，同时寻找反证；Parent 和 explore
     已完成 Capability 检查，因此只允许 commerce_compare_windows、commerce_evidence_query，
     max_tool_rounds=2、max_tool_calls=2；第一轮必须调用
     commerce_compare_windows(metric_names=["order_count","late_delivery_rate","handling_time_hours","transit_time_hours"])
     比较四个指标，第二轮抽查，然后立即综合。
   两个 spawn_task 都必须显式传 skills、tools、max_tool_rounds 和 max_tool_calls，只加载这一项 Skill 和最小 Tool 包。
3. 用一次 wait_task(mode="all") 等待两个任务。得到结果以后，再单独启动一个 verifier Task；它必须使用
   fresh context 按同一卖家和窗口独立重算，不继承 Parent 隐式推理，source_refs 要显式引用前两个 task_id，
   skills 仍只传 fulfillment-investigation，Tool 最小包固定为 commerce_seller_coverage、
   commerce_compare_windows、commerce_evidence_query，max_tool_rounds=2、max_tool_calls=3；第一轮必须使用
   commerce_seller_coverage 和相同的四个 metric_names 独立重算覆盖与窗口，第二轮抽查来源。随后等待 verifier。
4. 最终只用中文自然回答，必须包含：现象、阶段定位、至少一个 mobs_ 证据 ID、反证或替代解释、数据限制、
   下一步。不得把相关性写成因果，不得声称掌握库存、利润、曝光、点击、广告消耗等本数据没有的字段。
   阶段结论只能写“变化集中在运输时长指标”或“与承运阶段异常一致”；禁止写“核心来源是”“完全解释了”或“几乎完全解释了”
   “排除了卖家自身原因”“排除了卖家处理流程作为延迟主因”，也不要自行计算 Tool 未直接返回的贡献率。
   handling_time 下降只能写“未观察到处理时长恶化，是反证之一”，不能据此排除卖家端其他因素；
   Evidence 抽查只能说明被抽查记录，禁止写“计算可靠”或“不存在数据缺失导致计算错误”。
   不做统计显著性或“足以排除低基数噪声”的声称；不得臆测任何未观测的节日或外部事件因素。
   反证与替代解释只能来自 Dataset 字段或 Tool 返回的证据；不要自行补充节日、天气、促销或宏观物流事件。
   `source_fact_ids_truncated=true` 只表示 Tool 预览截断，不能写成底层记录“无法全量追溯”。
   Verifier 成功后直接综合三个 Task 的结果；除非 Task 失败或结论冲突，不要再调用 read_file、
   commerce_compare_windows、commerce_metric_snapshot、commerce_evidence_query 或其他 Tool 重算同一问题。
""".strip(),
    first_wave=(
        DynamicTaskPlan(
            subagent_type="explore",
            skills=("fulfillment-investigation",),
            tools=("commerce_seller_coverage",),
            max_tool_rounds=1,
            expected_tool_names=("commerce_seller_coverage",),
        ),
        DynamicTaskPlan(
            subagent_type="analyst",
            skills=("fulfillment-investigation",),
            tools=("commerce_compare_windows", "commerce_evidence_query"),
            max_tool_rounds=2,
            expected_tool_names=(
                "commerce_compare_windows",
                "commerce_evidence_query",
            ),
        ),
    ),
    verifier=DynamicTaskPlan(
        subagent_type="verifier",
        skills=("fulfillment-investigation",),
        tools=(
            "commerce_seller_coverage",
            "commerce_compare_windows",
            "commerce_evidence_query",
        ),
        max_tool_rounds=2,
        expected_tool_names=(
            "commerce_seller_coverage",
            "commerce_compare_windows",
            "commerce_evidence_query",
        ),
        max_tool_calls=3,
    ),
    final_required_all=("mobs_",),
    final_required_any=(
        ("反证", "替代解释", "不能证明"),
        ("数据限制", "缺少", "未包含"),
    ),
    final_forbidden=(
        "真实GMV",
        "实际转化率",
        "库存已经改善",
        "履约恶化的核心来源是",
        "核心来源是承运运输阶段",
        "排除了卖家自身原因",
        "排除了卖家处理流程作为延迟主因",
        "计算可靠",
        "不存在数据缺失导致计算错误",
        "足以排除低基数噪声",
        "春节",
        "无法全量追溯",
        "几乎完全解释了",
        "占总量涨幅",
    ),
    final_required_patterns=(
        r"(?:订单量|order_count).{0,160}(?<!\d)141(?!\d).{0,160}(?<!\d)202(?!\d)",
        _LATE_DELIVERY_PAIR_PATTERN,
        r"(?:处理时长|handling_time_hours).{0,180}46\.8(?:[34])?",
        r"(?:运输时长|transit_time_hours).{0,180}494\.8(?:[23])?",
    ),
    max_requests=24,
    max_tokens=350_000,
)


def test_late_delivery_fact_pattern_accepts_either_narrative_order():
    assert re.search(
        _LATE_DELIVERY_PAIR_PATTERN,
        "晚到率从基线 3.55% 上升到当前 35.15%。",
    )
    assert re.search(
        _LATE_DELIVERY_PAIR_PATTERN,
        "当前窗口的 late_delivery_rate 为 35.15%，基线窗口为 3.55%。",
    )


@pytest.mark.real_model
@pytest.mark.anyio
async def test_chat_upload_dynamic_parallel_diagnosis_and_fresh_verification(
    tmp_path: Path,
    real_executor_module,
):
    report, issues = await run_dynamic_chat_release_case(
        case_root=CASE_DIR,
        spec=FULFILLMENT_SPEC,
        workspace_root=tmp_path / "commerce-chat-dynamic-fulfillment",
        executor_module=real_executor_module,
        audit_root=AUDIT_ROOT,
    )

    if issues:
        print(f"DYNAMIC_FINAL_TEXT[{FULFILLMENT_SPEC.case_key}]={report.final_text}")
    assert issues == (), {
        "audit_path": report.audit_path,
        "request_count": report.request_count,
        "total_tokens": report.total_tokens,
        "issues": issues,
    }
    assert report.preflight.actual_model_identity.casefold().startswith("deepseek-v4")
    assert report.request_count <= FULFILLMENT_SPEC.max_requests
    assert report.total_tokens <= FULFILLMENT_SPEC.max_tokens
    assert Path(report.audit_path).is_file()

"""Fresh DeepSeek V4 dynamic release gates for the remaining Gold Cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.commerce.evaluation.chat_dynamic_release import (
    DynamicChatReleaseSpec,
    DynamicTaskPlan,
    run_dynamic_chat_release_case,
)

REPO_ROOT = Path(__file__).parents[4]
CASES_ROOT = REPO_ROOT / "evals" / "commerce" / "cases"
AUDIT_ROOT = REPO_ROOT / ".deer-flow" / "commerce" / "evaluation" / "chat-dynamic-release"


def _common_prompt(
    case_body: str,
    *,
    skill: str,
    analyst_body: str,
    verifier_body: str,
) -> str:
    return f"""
你正在处理用户刚上传的一份真实电商数据。只能使用当前 Dataset 的确定性 Commerce Tool，不能心算指标，
不能把相关性写成因果，也不能虚构曝光、点击、加购、广告消耗、库存、利润、GMV、CTR、CVR 或 ROI。

{case_body}

必须遵循以下动态 Parent–Subagent 流程：
1. 先单独调用 commerce_ingest_uploads，等待成功后下一轮单独调用 commerce_capabilities；两者不能在同一
   响应并行。
2. 能力检查完成后，在同一个模型响应中并行启动两个 Durable Task：
   - explore：Parent 已完成 Capability 检查，因此只加载 {skill}，只允许 commerce_dataset_profile，
     必须显式传 include_column_details=false、include_semantic_mappings=false，max_tool_rounds=1、max_tool_calls=1；
     dataset_profile 使用紧凑参数，不请求完整列明细或全部语义映射，完成字段、
     口径和数据限制盘点后立即综合；
   - analyst：加载 {skill}，{analyst_body}。必须显式传 skills、tools、max_tool_rounds 和 max_tool_calls，不能扩权。
3. 用一次 wait_task(mode="all") 等待首轮任务；只有在首轮都进入终态后，单独启动 verifier。Verifier 使用
   fresh context 独立重算，source_refs 必须显式引用首轮两个 task_id。{verifier_body}；随后再用一次
   wait_task 等待 verifier。
4. 最终只用中文回答，必须引用至少一个 mobs_ MetricObservation，说明支持证据、反证/替代解释、数据限制
   和下一步。不要为了“更完整”重复调用同一指标或文件；Verifier 成功后直接综合三个 Task。
""".strip()


def _spec(
    *,
    case_key: str,
    prompt: str,
    skill: str,
    analyst_tools: tuple[str, ...],
    analyst_rounds: int,
    verifier_tools: tuple[str, ...],
    verifier_rounds: int,
    final_required_all: tuple[str, ...],
    final_required_any: tuple[tuple[str, ...], ...],
    final_forbidden: tuple[str, ...],
    final_required_patterns: tuple[str, ...] = (),
    analyst_max_tool_calls: int | None = None,
    verifier_max_tool_calls: int | None = None,
) -> DynamicChatReleaseSpec:
    return DynamicChatReleaseSpec(
        case_key=case_key,
        prompt=prompt,
        first_wave=(
            DynamicTaskPlan(
                subagent_type="explore",
                skills=(skill,),
                tools=("commerce_dataset_profile",),
                max_tool_rounds=1,
                expected_tool_names=("commerce_dataset_profile",),
            ),
            DynamicTaskPlan(
                subagent_type="analyst",
                skills=(skill,),
                tools=analyst_tools,
                max_tool_rounds=analyst_rounds,
                expected_tool_names=analyst_tools,
                max_tool_calls=analyst_max_tool_calls,
            ),
        ),
        verifier=DynamicTaskPlan(
            subagent_type="verifier",
            skills=(skill,),
            tools=verifier_tools,
            max_tool_rounds=verifier_rounds,
            expected_tool_names=verifier_tools,
            max_tool_calls=verifier_max_tool_calls,
        ),
        final_required_all=final_required_all,
        final_required_any=final_required_any,
        final_required_patterns=final_required_patterns,
        final_forbidden=final_forbidden,
        max_requests=24,
        max_tokens=350_000,
    )


REVIEW_SPEC = _spec(
    case_key="GC-REVIEW-002",
    skill="review-experience-diagnosis",
    prompt=_common_prompt(
        """
请调查卖家 0b90b6df587eb83608a64ea8b390cf07 的评价与商品体验变化：
基线窗口 2018-03-01T00:00:00 到 2018-04-01T00:00:00，当前窗口 2018-04-01T00:00:00 到 2018-05-01T00:00:00。
必须比较 order_count、average_review_score、low_rating_rate 和 late_delivery_rate，并检查评论文本中
是否出现疑似非原装、错发、少发等体验信号。commerce_compare_windows 返回的 baseline/current
MetricObservation 就是对两窗口 late_delivery_rate 的分别核验；禁止再用 commerce_metric_snapshot 重算。
评论信号不能升级为售假、欺诈或违法结论。晚到率两窗口均为 0 只能写“未观察到配送延迟变化，不能把物流
延迟作为已证实解释”；禁止写“评分恶化与配送延迟无关”“配送延迟不是原因”“已排除原因”
“配送延迟无关”“评价下降不能用配送时效解释”“履约时效完全正常”或“更可能是商品本身”。
这些禁句在标题、反证小节和结论中同样禁止。不要把 23.5%→44.4% 写成统计显著或精确翻倍。
""",
        skill="review-experience-diagnosis",
        analyst_body=(
            "只允许 commerce_compare_windows、commerce_evidence_query，max_tool_rounds=2、max_tool_calls=3；"
            "第一轮调用一次 compare_windows，并显式传 metric_names=[order_count,average_review_score,"
            "low_rating_rate,late_delivery_rate]，"
            "第二轮调用 1–2 次有界 evidence_query，分别抽查 MetricObservation 来源与评论语义；"
            "主动寻找‘评分下降但晚到率仍为零’等反证；禁止 commerce_metric_snapshot"
        ),
        verifier_body=(
            "只加载 review-experience-diagnosis，只允许 commerce_compare_windows、"
            "commerce_evidence_query，max_tool_rounds=2、max_tool_calls=3；第一轮独立比较，"
            "并显式传 metric_names=[order_count,average_review_score,low_rating_rate,late_delivery_rate]；"
            "第二轮用 1–2 次有界 evidence_query 抽查指标与评论来源；禁止 commerce_metric_snapshot"
        ),
    ),
    analyst_tools=("commerce_compare_windows", "commerce_evidence_query"),
    analyst_rounds=2,
    verifier_tools=("commerce_compare_windows", "commerce_evidence_query"),
    verifier_rounds=2,
    analyst_max_tool_calls=3,
    verifier_max_tool_calls=3,
    final_required_all=("mobs_",),
    final_required_any=(
        ("非原装", "错发", "少发", "评论"),
        ("反证", "替代解释", "不能证明"),
        ("不能确认", "无法确认", "不应确认", "无法证实", "不足以认定", "不代表", "信号", "线索", "待核查"),
        ("数据限制", "缺少", "未包含"),
    ),
    final_forbidden=(
        "确认售假",
        "确认欺诈",
        "卖家就是在售假",
        "物流延迟导致评分下降",
        "真实GMV",
        "实际转化率",
        "评分恶化与配送延迟无关",
        "履约时效完全正常",
        "评分下降更可能与商品本身",
        "更可能与商品本身",
        "配送延迟不是原因",
        "配送延迟无关",
        "评价下降不能用配送时效解释",
        "已排除原因",
        "排除了因样本量突变",
        "显著恶化",
        "翻了一番",
        "低分率翻倍",
    ),
    final_required_patterns=(
        r"(?:平均评分|平均评价分|average_review_score).{0,160}3\.88.{0,160}2\.94",
        r"(?:低分率|low_rating_rate).{0,160}23\.5(?:3)?%.{0,160}44\.4(?:4)?%",
        r"(?:晚到率|late_delivery_rate).{0,180}\b0(?:\.0+)?%?.{0,100}\b0(?:\.0+)?%?",
    ),
)


CAPABILITY_SPEC = _spec(
    case_key="GC-CAPABILITY-003",
    skill="fulfillment-investigation",
    prompt=_common_prompt(
        """
请调查卖家 4869f7a5dfa277a7dca6462dcf3b52b2 的履约变化：
基线窗口 2017-12-02T00:00:00 到 2018-01-31T00:00:00，当前窗口 2018-01-31T00:00:00 到 2018-04-01T00:00:00。
必须区分卖家处理阶段与承运运输阶段，比较 order_count、late_delivery_rate、handling_time_hours 和
transit_time_hours。当前 Dataset 已移除 order_reviews，必须明确 review_experience / average_review_score
不可用，不能写成评分下降或低分率上升，并给出精确补数建议。阶段结论只能写“变化集中在运输时长指标”
或“与承运阶段异常一致”；禁止写“核心来源是”“完全解释了”“排除了卖家自身原因”，也不要自行计算 Tool
未直接返回的“占总量涨幅/贡献率”。
""",
        skill="fulfillment-investigation",
        analyst_body=(
            "只允许 commerce_compare_windows、commerce_evidence_query，max_tool_rounds=2、max_tool_calls=2；"
            "第一轮调用一次 compare_windows，并显式传 metric_names=[order_count,late_delivery_rate,"
            "handling_time_hours,transit_time_hours] 区分 handling 与 transit，"
            "第二轮调用一次 evidence_query 抽查履约 Fact；"
            "同时验证 review 能力不可用而不是把 unknown 当成零；"
            "禁止 commerce_metric_snapshot"
        ),
        verifier_body=(
            "只加载 fulfillment-investigation，只允许 commerce_compare_windows、commerce_evidence_query，"
            "max_tool_rounds=2、max_tool_calls=2；第一轮显式传 metric_names=[order_count,"
            "late_delivery_rate,handling_time_hours,transit_time_hours] 独立比较，第二轮抽查来源；"
            "禁止 commerce_metric_snapshot"
        ),
    ),
    analyst_tools=("commerce_compare_windows", "commerce_evidence_query"),
    analyst_rounds=2,
    verifier_tools=("commerce_compare_windows", "commerce_evidence_query"),
    verifier_rounds=2,
    final_required_all=("mobs_",),
    final_required_any=(
        (
            "评价数据不可用",
            "评价能力不可用",
            "order_reviews",
            "评分数据不可用",
            "缺少评价",
            "缺失评价",
            "无法评估评分",
            "无法分析评价",
            "评价未观测",
            "评分未知",
            "评论数据缺失",
            "没有评价数据",
            "未包含评价",
            "未提供评价",
            "缺少评分",
            "未包含评分",
            "无法判断评分",
            "不能判断评分",
            "review_experience 不可用",
            "review_experience",
        ),
        ("数据限制", "缺少", "未包含"),
        ("补充", "补数", "需要提供"),
    ),
    final_forbidden=(
        "评分下降",
        "低分率上升",
        "真实GMV",
        "实际转化率",
        "库存已经改善",
        "履约恶化的核心来源是",
        "核心来源是承运运输阶段",
        "排除了卖家自身原因",
        "几乎完全解释了",
        "占总量涨幅",
    ),
    final_required_patterns=(
        r"(?:订单量|order_count).{0,160}\b141\b.{0,160}\b202\b",
        r"(?:晚发货率|晚到率|late_delivery_rate).{0,180}3\.5(?:5)?%.{0,160}35\.1(?:5)?%",
        r"(?:处理时长|handling_time_hours).{0,180}46\.8[34]",
        r"(?:运输时长|transit_time_hours).{0,180}494\.8[23]",
    ),
)


PEER_SPEC = _spec(
    case_key="GC-PEER-004",
    skill="seller-peer-analysis",
    prompt=_common_prompt(
        """
请对卖家 e5a3438891c0bfdb9394643f95273d8e 做同类卖家对标：窗口 2018-01-01T00:00:00 到 2018-07-01T00:00:00，
纯商品类目 fashion_bolsas_e_acessorios，min_orders_per_seller=20，匹配卖家州，单卖家订单且纯类目订单。
必须返回目标订单量/晚到率、同行卖家数/订单量/晚到率、差值和 SP/MG/RJ 地域订单分布。对标差距是诊断信号，
不能证明卖家自身导致延迟，也没有 Action follow-up，不能声称行动已经缩小差距。最终回答必须从
commerce_peer_comparison 返回的目标或同行 MetricObservation 中原样引用至少一个 `mobs_` ID，不能用
`cohort_` 代替。只报告 Tool 直接返回的订单数、晚到率和 gap；地域只报告订单数，不自行计算占比、倍数、
显著性、排除某同行后的新均值或贡献率。禁止再比较“晚到率最高的同行”并计算新 gap；Evidence 抽查只能
说明被抽查记录，不能写“无任何缺失或异常”；未做同行地域对比时，不能声称地域结构不异常。
""",
        skill="seller-peer-analysis",
        analyst_body=(
            "只允许 commerce_peer_comparison、commerce_geographic_segments、"
            "commerce_evidence_query，max_tool_rounds=3、max_tool_calls=4；第一轮调用一次 peer_comparison "
            "固定 cohort 规则，并调用一次 geographic_segments 获取地域结构；下一轮或同一轮调用 "
            "1–2 次有界 evidence_query，分别抽查目标与同行来源，不能换规则追求更大差距；"
            "禁止 commerce_metric_snapshot"
        ),
        verifier_body=(
            "只加载 seller-peer-analysis，只允许 commerce_peer_comparison、"
            "commerce_evidence_query，max_tool_rounds=2、max_tool_calls=3；第一轮独立重算同一 cohort，"
            "第二轮用 1–2 次有界 evidence_query 分别抽查目标与同行来源；"
            "禁止 commerce_metric_snapshot 和 commerce_geographic_segments"
        ),
    ),
    analyst_tools=(
        "commerce_peer_comparison",
        "commerce_geographic_segments",
        "commerce_evidence_query",
    ),
    analyst_rounds=3,
    analyst_max_tool_calls=4,
    verifier_tools=("commerce_peer_comparison", "commerce_evidence_query"),
    verifier_rounds=2,
    verifier_max_tool_calls=3,
    final_required_all=("mobs_",),
    final_required_any=(
        ("对标", "同行", "cohort"),
        ("反证", "替代解释", "不能证明"),
        ("数据限制", "缺少", "未包含"),
    ),
    final_forbidden=(
        "对标差距证明卖家导致延迟",
        "可以确认是卖家自身造成",
        "行动已缩小对标差距",
        "措施已经改善卖家表现",
        "真实GMV",
        "实际转化率",
        "3.67 倍",
        "44.07%",
        "13.56%",
        "3.39%",
        "排除该高值同行",
        "其余 4 家平均",
        "差距扩大到",
        "数据源可靠",
        "差距显著",
        "重要原因",
        "无法枚举全部订单级事实",
        "无法全量追溯",
        "显著高于",
        "约 44%",
        "即使对比同行中晚到率最高",
        "未发现地域结构异常",
        "无任何缺失或异常",
        "晚到率的具体计算阈值",
    ),
    final_required_patterns=(
        r"(?:目标卖家|目标).{0,180}\b59\b.{0,220}27\.12%",
        r"(?:同行|peer).{0,420}(?<!\d)5(?!\d).{0,420}(?<!\d)257(?!\d).{0,420}7\.39%",
        r"(?:19\.73\s*(?:个百分点|pp)|\+?0\.1973)",
        r"SP.{0,100}\b26\b",
        r"MG.{0,100}\b8\b",
        r"RJ.{0,100}\b7\b",
    ),
)


async def _run_case(tmp_path: Path, real_executor_module, spec: DynamicChatReleaseSpec):
    report, issues = await run_dynamic_chat_release_case(
        case_root=CASES_ROOT / spec.case_key,
        spec=spec,
        workspace_root=tmp_path / spec.case_key,
        executor_module=real_executor_module,
        audit_root=AUDIT_ROOT,
    )
    if issues:
        print(f"DYNAMIC_FINAL_TEXT[{spec.case_key}]={report.final_text}")
    assert issues == (), {
        "case_key": spec.case_key,
        "audit_path": report.audit_path,
        "request_count": report.request_count,
        "total_tokens": report.total_tokens,
        "final_text": report.final_text,
        "issues": issues,
    }
    assert report.preflight.actual_model_identity.casefold().startswith("deepseek-v4")
    assert Path(report.audit_path).is_file()
    return report


@pytest.mark.real_model
@pytest.mark.anyio
async def test_review_gold_case_dynamic_chain_is_auditable(
    tmp_path: Path,
    real_executor_module,
):
    await _run_case(tmp_path, real_executor_module, REVIEW_SPEC)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_capability_ablated_gold_case_stays_unknown_fail_closed(
    tmp_path: Path,
    real_executor_module,
):
    await _run_case(tmp_path, real_executor_module, CAPABILITY_SPEC)


@pytest.mark.real_model
@pytest.mark.anyio
async def test_peer_gold_case_dynamic_cohort_and_geography_chain_is_auditable(
    tmp_path: Path,
    real_executor_module,
):
    await _run_case(tmp_path, real_executor_module, PEER_SPEC)

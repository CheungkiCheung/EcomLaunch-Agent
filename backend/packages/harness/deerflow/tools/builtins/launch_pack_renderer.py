"""Deterministically render a compact Launch Pack specification into seven files."""

from __future__ import annotations

import copy
import csv
import html
import io
import json
import re
from collections.abc import Mapping
from typing import Any, Literal, NotRequired, Required, TypedDict
from urllib.parse import urlsplit, urlunsplit

from deerflow.tools.builtins.launch_pack_guard import (
    _concept_context,
    _is_direct_evidence_url,
)

LaunchPackDecision = Literal["test_now", "test_after_fixing_assumptions", "hold", "insufficient_evidence"]
_VALID_EVIDENCE_LABELS = {"observed_public", "uploaded_real", "estimated", "assumption", "unavailable"}
_VALID_DECISIONS = {"test_now", "test_after_fixing_assumptions", "hold", "insufficient_evidence"}
_CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
_DECISION_LABELS = {
    "zh": {
        "test_now": "值得立即做 7 天轻量验证",
        "test_after_fixing_assumptions": "补齐关键假设后再验证",
        "hold": "暂缓验证",
        "insufficient_evidence": "证据不足，先补公开信号",
    },
    "en": {
        "test_now": "Run the 7-day lightweight validation now",
        "test_after_fixing_assumptions": "Resolve critical assumptions before testing",
        "hold": "Hold",
        "insufficient_evidence": "Insufficient evidence; collect public signals first",
    },
}


class LaunchPackEvidenceSpec(TypedDict, total=False):
    claim: Required[str]
    evidence_label: str
    source_urls: list[str]
    confidence: str
    limitation: str


class LaunchPackCompetitorSpec(TypedDict, total=False):
    name: Required[str]
    price_signal: str
    positioning_signal: str
    evidence_label: str
    source_url: str
    notes: str


class LaunchPackSpec(TypedDict, total=False):
    category: Required[str]
    target_price: Required[str]
    decision: Required[LaunchPackDecision]
    decision_rationale: Required[str]
    audience: Required[str]
    validation_goal: Required[str]
    language: NotRequired[Literal["zh", "en"]]
    evidence: NotRequired[list[LaunchPackEvidenceSpec]]
    competitors: NotRequired[list[LaunchPackCompetitorSpec]]
    hypotheses: NotRequired[list[str]]
    experiments: NotRequired[list[dict[str, object]]]


def normalize_launch_decision(value: object) -> LaunchPackDecision:
    """Normalize supported localized decision text without silently changing unknown values."""
    raw = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    if raw in _VALID_DECISIONS:
        return raw  # type: ignore[return-value]
    if any(marker in raw for marker in ("证据不足", "insufficient evidence")):
        return "insufficient_evidence"
    if any(marker in raw for marker in ("暂缓", "先不做", "不值得", "停止验证", "hold", "do not test")):
        return "hold"
    if any(marker in raw for marker in ("补齐", "补充", "修正", "解决关键假设", "after fixing")) and any(marker in raw for marker in ("验证", "测试", "test")):
        return "test_after_fixing_assumptions"
    if any(marker in raw for marker in ("值得", "立即", "现在开始", "test now", "run the 7-day")) and any(marker in raw for marker in ("验证", "测试", "test")):
        return "test_now"
    allowed = ", ".join(sorted(_VALID_DECISIONS))
    raise ValueError(f"decision must be one of: {allowed}")


def launch_decision_label(decision: LaunchPackDecision, language: str) -> str:
    return _DECISION_LABELS["zh" if language == "zh" else "en"][decision]


def _canonical_source_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


def enforce_verified_public_sources(spec: Mapping[str, Any], verified_urls: set[str]) -> dict[str, Any]:
    """Reconcile Flash evidence and decision with pages fetched in this turn."""
    normalized_urls = {_canonical_source_url(url) for url in verified_urls}
    normalized_urls.discard("")
    prepared = copy.deepcopy(dict(spec))
    for key in ("evidence", "competitors"):
        rows = prepared.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or str(row.get("evidence_label") or row.get("label") or "").lower() != "observed_public":
                continue
            raw_sources = row.get("source_urls") if key == "evidence" else row.get("source_url")
            sources = raw_sources if isinstance(raw_sources, list) else [raw_sources]
            if any(_canonical_source_url(source) in normalized_urls for source in sources):
                continue
            row["evidence_label"] = "estimated"
            if key == "evidence":
                limitation = _text(row.get("limitation"), limit=360)
                provenance_gap = "来源仅出现在搜索结果中，本次未成功抓取原网页。"
                row["limitation"] = f"{limitation}；{provenance_gap}" if limitation else provenance_gap
            else:
                notes = _text(row.get("notes"), limit=300)
                provenance_gap = "原网页未成功抓取，仅作发现线索。"
                row["notes"] = f"{notes}；{provenance_gap}" if notes else provenance_gap

    evidence_rows = prepared.get("evidence")
    strong_evidence_count = 0
    if isinstance(evidence_rows, list):
        strong_evidence_count = sum(isinstance(row, Mapping) and str(row.get("evidence_label") or row.get("label") or "").lower() in {"observed_public", "uploaded_real"} for row in evidence_rows)
    if strong_evidence_count == 0 and normalize_launch_decision(prepared.get("decision") or prepared.get("verdict")) == "test_now":
        prepared["decision"] = "test_after_fixing_assumptions"
        language_hint = _text(prepared.get("language"), limit=12).lower()
        serialized = json.dumps(prepared, ensure_ascii=False)
        if language_hint.startswith("en") or (not language_hint.startswith("zh") and _CHINESE_PATTERN.search(serialized) is None):
            prepared["decision_rationale"] = (
                "No public page was successfully fetched and directly verified in this run. "
                "Search snippets are discovery leads, not enough support for starting immediately. "
                "Verify at least one price, review, or demand source before the seven-day test."
            )
        else:
            prepared["decision_rationale"] = "当前没有成功抓取且可直接核验的公开页面；搜索摘要只能作为发现线索，尚不足以支持“立即测试”。先补齐至少一条可核验的价格、口碑或需求来源，再启动 7 天轻量验证。"
    return prepared


def _text(value: object, *, default: str = "", limit: int = 600) -> str:
    if value is None:
        return default
    rendered = re.sub(r"\s+", " ", str(value)).strip()
    if not rendered:
        return default
    return rendered[:limit]


def _list(value: object, *, limit: int = 8) -> list[object]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def _language(spec: Mapping[str, Any], user_request: str) -> str:
    requested = _text(spec.get("language"), limit=12).lower()
    if requested.startswith("en"):
        return "en"
    if requested.startswith("zh"):
        return "zh"
    return "zh" if _CHINESE_PATTERN.search(user_request) else "en"


def _normalize_sources(value: object) -> list[str]:
    candidates: list[object]
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        candidates = [value]
    else:
        candidates = []
    normalized: list[str] = []
    for candidate in candidates[:4]:
        source = _text(candidate, limit=500)
        if source and _is_direct_evidence_url(source) and source not in normalized:
            normalized.append(source)
    return normalized


def _normalize_evidence(spec: Mapping[str, Any], *, language: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, raw in enumerate(_list(spec.get("evidence")), start=1):
        if not isinstance(raw, Mapping):
            continue
        claim = _text(raw.get("claim") or raw.get("signal") or raw.get("finding"), limit=500)
        if not claim:
            continue
        label = _text(raw.get("evidence_label") or raw.get("label"), default="assumption", limit=40).lower()
        if label not in _VALID_EVIDENCE_LABELS:
            label = "assumption"
        sources = _normalize_sources(raw.get("source_urls") or raw.get("source_url"))
        if label == "observed_public" and not sources:
            label = "estimated"
        entries.append(
            {
                "id": f"E{index}",
                "claim": claim,
                "evidence_label": label,
                "source_urls": sources,
                "confidence": _text(raw.get("confidence"), default="medium", limit=40),
                "limitation": _text(raw.get("limitation") or raw.get("notes"), limit=300),
            }
        )
    if entries:
        return entries
    return [
        {
            "id": "E1",
            "claim": "尚未获得可直接核验的公开来源；本轮先验证问题、预算和购买时机。" if language == "zh" else "No directly verifiable public source was available; validate the problem, budget, and buying trigger first.",
            "evidence_label": "unavailable",
            "source_urls": [],
            "confidence": "low",
            "limitation": "公开研究结果不可用或不足。" if language == "zh" else "Public research was unavailable or insufficient.",
        }
    ]


def _normalize_competitors(spec: Mapping[str, Any], *, language: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in _list(spec.get("competitors")):
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name") or raw.get("competitor") or raw.get("alternative"), limit=180)
        if not name:
            continue
        label = _text(raw.get("evidence_label") or raw.get("label"), default="assumption", limit=40).lower()
        if label not in _VALID_EVIDENCE_LABELS:
            label = "assumption"
        sources = _normalize_sources(raw.get("source_url") or raw.get("source_urls"))
        source_url = sources[0] if sources else ""
        if label == "observed_public" and not source_url:
            label = "estimated"
        rows.append(
            {
                "competitor": name,
                "price_signal": _text(raw.get("price_signal") or raw.get("price"), default="unavailable", limit=160),
                "positioning_signal": _text(raw.get("positioning_signal") or raw.get("positioning"), default="unavailable", limit=240),
                "evidence_label": label,
                "source_url": source_url,
                "notes": _text(raw.get("notes") or raw.get("limitation"), limit=240),
            }
        )
    if rows:
        return rows
    return [
        {
            "competitor": "公开竞品信号待补" if language == "zh" else "Public competitor signal unavailable",
            "price_signal": "unavailable",
            "positioning_signal": "unavailable",
            "evidence_label": "unavailable",
            "source_url": "",
            "notes": "不以搜索摘要或未打开页面作为已观察证据。" if language == "zh" else "Search snippets and unopened pages are not treated as observed evidence.",
        }
    ]


def _normalize_hypotheses(spec: Mapping[str, Any], *, language: str) -> list[str]:
    hypotheses = [_text(item, limit=260) for item in _list(spec.get("hypotheses"), limit=5)]
    hypotheses = [item for item in hypotheses if item]
    if hypotheses:
        return hypotheses
    if language == "zh":
        return [
            "目标用户愿意为当前最重要的问题投入目标预算。",
            "现有替代方案存在可被清楚描述的未满足场景。",
            "在没有样品与规格时，问题型概念仍能获得可追溯的有效反馈。",
        ]
    return [
        "The target audience will allocate the stated budget to its most important problem.",
        "Existing alternatives leave a clearly describable scenario unmet.",
        "A question-led concept can collect traceable feedback before samples and specifications exist.",
    ]


def _normalize_experiments(spec: Mapping[str, Any], *, language: str) -> list[dict[str, str]]:
    experiments: list[dict[str, str]] = []
    for index, raw in enumerate(_list(spec.get("experiments"), limit=7), start=1):
        if isinstance(raw, Mapping):
            action = _text(raw.get("action") or raw.get("experiment") or raw.get("name"), limit=300)
            if not action:
                continue
            channel = _text(raw.get("channel"), limit=80)
            experiment_type = _text(raw.get("type"), limit=80)
            cost = _text(raw.get("cost") or raw.get("budget"), limit=80)
            qualifiers = [
                ("渠道" if language == "zh" else "channel", channel),
                ("形式" if language == "zh" else "type", experiment_type),
                ("预算" if language == "zh" else "budget", cost),
            ]
            qualifier_text = [f"{label}：{value}" if language == "zh" else f"{label}: {value}" for label, value in qualifiers if value]
            if qualifier_text:
                separator = "；" if language == "zh" else "; "
                action = f"{action}（{separator.join(qualifier_text)}）" if language == "zh" else f"{action} ({separator.join(qualifier_text)})"
            experiments.append(
                {
                    "day": _text(raw.get("day"), default=str(index), limit=16),
                    "action": action,
                    "evidence_to_collect": _text(
                        raw.get("evidence_to_collect") or raw.get("signal") or raw.get("metric"),
                        default="可追溯反馈" if language == "zh" else "traceable responses",
                        limit=240,
                    ),
                    "success_criterion": _text(
                        raw.get("success_criterion") or raw.get("success") or raw.get("goal"),
                        default="记录有效信号" if language == "zh" else "record qualified signals",
                        limit=240,
                    ),
                    "stop_condition": _text(
                        raw.get("stop_condition") or raw.get("stop"),
                        default="有效信号持续偏弱则停止" if language == "zh" else "stop if qualified signals remain weak",
                        limit=240,
                    ),
                }
            )
        elif isinstance(raw, str) and raw.strip():
            experiments.append(
                {
                    "day": str(index),
                    "action": _text(raw, limit=300),
                    "evidence_to_collect": "可追溯反馈" if language == "zh" else "traceable responses",
                    "success_criterion": "记录有效信号" if language == "zh" else "record qualified signals",
                    "stop_condition": "有效信号持续偏弱则停止" if language == "zh" else "stop if qualified signals remain weak",
                }
            )
    defaults_zh = [
        ("明确人群与问题边界，发布匿名筛选问卷", "场景、预算、替代方案", "获得可追溯的目标人群回答", "回答无法对应真实场景"),
        ("访谈符合筛选条件的潜在用户", "原话、触发时机、放弃原因", "出现重复且具体的问题表述", "反馈仅停留在泛泛偏好"),
        ("发布两个问题型内容版本", "有效评论与问卷完成", "至少一个主题带来高质量回答", "只有点赞而没有问题证据"),
        ("测试目标价格区间与购买时机", "价格选择及理由", "预算理由与目标范围存在交集", "目标范围持续被明确拒绝"),
        ("对比现有替代方案", "替代方案、缺口、切换条件", "找到可描述的未满足场景", "没有明确切换理由"),
        ("复核证据标签与停止条件", "来源、日期、样本口径", "关键结论均可追溯", "关键结论依赖猜测或搜索摘要"),
        ("汇总 ship / extend / stop 决策", "信号强度、缺口、下一步成本", "形成有边界的下一步决定", "证据不足则停止进入样品阶段"),
    ]
    defaults_en = [
        ("Define the audience and problem boundary; publish a screening survey", "scenario, budget, alternatives", "collect traceable target-audience responses", "responses cannot be tied to real scenarios"),
        ("Interview qualified prospective users", "exact wording, triggers, rejection reasons", "repeated and specific problem statements emerge", "feedback stays generic"),
        ("Publish two question-led content variants", "qualified comments and survey completions", "one theme produces useful answers", "engagement has no problem evidence"),
        ("Test the target price range and buying trigger", "price choice and rationale", "budget rationale overlaps the target range", "the range is consistently rejected"),
        ("Compare current alternatives", "alternative, gap, switching condition", "identify a describable unmet scenario", "no switching reason exists"),
        ("Review evidence labels and stop conditions", "source, date, sample definition", "material conclusions are traceable", "key conclusions rely on guesses or snippets"),
        ("Make a ship / extend / stop decision", "signal strength, gaps, next-step cost", "produce a bounded next-step decision", "stop sample work when evidence is insufficient"),
    ]
    defaults = defaults_zh if language == "zh" else defaults_en
    used_days = {row["day"] for row in experiments}
    for day, values in enumerate(defaults, start=1):
        if len(experiments) >= 7:
            break
        if str(day) in used_days:
            continue
        action, evidence, success, stop = values
        experiments.append(
            {
                "day": str(day),
                "action": action,
                "evidence_to_collect": evidence,
                "success_criterion": success,
                "stop_condition": stop,
            }
        )
    return experiments[:7]


def _csv(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _chinese_listing_template(
    category: str,
    target_price: str,
    audience: str,
    validation_goal: str,
    hypotheses: list[str],
) -> str:
    hypothesis_lines = "\n".join(f"- 待验证：{hypothesis}" for hypothesis in hypotheses)
    return f"""# {category} 概念验证页文案

> 调研状态：无样品、无规格。本页用于验证真实场景与预算，不接受订单、定金或付款。

## 页面目标

- 待验证：目标人群为 {audience}
- 待验证：本轮目标是 {validation_goal}
- 目标价范围：{target_price}

## 首屏

**标题：** {category}｜7 天真实需求验证

**副标题：** 如果你近期正在比较这一品类，请根据真实通勤场景、现有替代方案和预算作答。当前没有可购买商品，也不承诺供货时间。

## 场景筛选

1. 你最近一次在通勤途中使用或考虑这一品类，发生在什么场景？
2. 现在用什么替代方案？最想先解决的问题是什么？
3. 哪项信息缺失时，你会直接放弃继续了解？
4. 在 {target_price} 范围内，哪个价格点可以进入下一步比较？为什么？

## 本轮假设

{hypothesis_lines}

## 行动入口

**按钮：** 提交 2 分钟匿名反馈

提交后仅记录场景、问题、替代方案、价格选择和购买时机。可自愿登记后续研究通知；不收款，不制造库存、销量、评价或倒计时。
"""


def _chinese_content_template(
    category: str,
    target_price: str,
    audience: str,
    hypotheses: list[str],
    experiments: list[dict[str, str]],
) -> str:
    hypothesis_lines = "\n".join(f"- 待验证：{hypothesis}" for hypothesis in hypotheses[:3])
    experiment_lines = "\n".join(f"- 待验证动作 D{row['day']}：{row['action']}" for row in experiments[:3])
    return f"""# {category} 7 天内容验证包

> 调研状态：无样品、无规格。所有内容只收集问题、场景、替代方案和预算偏好，不售卖、不收款。

## 目标人群

- 待验证：{audience}

## 小红书问题帖 A｜通勤场景

**标题：** 真实使用 {category} 时，你最不能接受的麻烦是什么？

**正文：** 正在做一轮 {category} 概念调研。请回想最近一次真实使用或购买场景：你当时用了什么，哪个环节最麻烦，最后是继续使用、换方案，还是放弃购买？当前没有可购买商品，本帖不接预订。

**评论引导：** 留下“场景 + 现有方案 + 最想先解决的问题”，不要只投偏好票。

## 小红书问题帖 B｜价格与购买时机

**标题：** {target_price} 的 {category}，你会因为什么继续比较？

**正文：** 这是一项价格与信息需求调研。请选择一个可接受价格点，并说明在什么购买时机、看到哪些可核验信息后才会继续了解。没有样品，不接受付款。

**评论引导：** 留下“价格点 + 理由 + 放弃条件”。

## 15 秒口播

“我们正在验证 {category} 的真实通勤需求，目标价是 {target_price}。请告诉我：你现在用什么，最困扰的问题是什么，缺哪条信息你就不会继续看？目前只做调研，没有商品，也不收款。”

## 待验证主题

{hypothesis_lines}

## 前三天发布动作

{experiment_lines}

## 记录规则

只记录可追溯的原话、场景、价格选择、问卷完成和主动登记；点赞与泛泛评论不能单独作为购买意愿证据。
"""


def _english_listing_template(
    category: str,
    target_price: str,
    audience: str,
    validation_goal: str,
    hypotheses: list[str],
) -> str:
    hypothesis_lines = "\n".join(f"- To validate: {hypothesis}" for hypothesis in hypotheses)
    return f"""# {category} Listing Pack (concept validation)

Stage: no sample and no specification. This page collects category, scenario, alternative, and budget feedback only. It is not a product page and does not accept orders or payment.

## Page goal

- To validate: the audience is {audience}
- To validate: {validation_goal}
- Target price: {target_price}

## Research title

{category} | {target_price} concept preference study

## Questions

- What problem matters most when choosing or using this category?
- Which current alternative is unsatisfactory, and in what real scenario?
- Which information gap would stop you from learning more?
- What budget range and buying trigger would justify further validation?

## Assumptions to validate

{hypothesis_lines}

## Action

Complete the anonymous preference survey or opt in to research updates. No supply, price, date, or product-capability promise is made.
"""


def _english_content_template(
    category: str,
    target_price: str,
    audience: str,
    hypotheses: list[str],
    experiments: list[dict[str, str]],
) -> str:
    hypothesis_lines = "\n".join(f"- To validate: {hypothesis}" for hypothesis in hypotheses[:3])
    experiment_lines = "\n".join(f"- Validation action D{row['day']}: {row['action']}" for row in experiments[:3])
    return f"""# {category} Content Pack (concept research)

Stage: no sample and no specification. Every item below asks about problems,
scenarios, alternatives, and budget; nothing implies that a purchasable product exists.

## Audience

- To validate: {audience}

## Question post A

When choosing this category, what real problem would you solve first? Share the scenario, the current alternative, and the information you need before considering a change. This post does not sell or accept payment.

## Question post B

For a {target_price} category concept, which factor would you validate first: the real use scenario, budget, buying trigger, current alternative, or another problem? Explain why.

## Short-video question script

“This is a concept study for {category}. The target range is {target_price}.
What problem matters most, and what missing information would stop you from learning more?
There is no sample or purchasable item, and no payment or preorder is accepted.”

## Themes to validate

{hypothesis_lines}

## First three actions

{experiment_lines}
"""


def render_launch_pack(spec: Mapping[str, Any], *, user_request: str) -> dict[str, str]:
    """Return canonical Launch Pack filenames mapped to deterministic contents."""
    language = _language(spec, user_request)
    inferred_category, inferred_price = _concept_context(user_request)
    category = _text(spec.get("category") or spec.get("product_category"), default=inferred_category, limit=120)
    target_price = _text(spec.get("target_price") or spec.get("price_range"), default=inferred_price, limit=80)
    decision = normalize_launch_decision(spec.get("decision") or spec.get("verdict"))
    rationale = _text(
        spec.get("decision_rationale") or spec.get("rationale"),
        default=("公开信号仍有限；先做七天、不可交易的轻量验证，再决定是否进入样品阶段。" if language == "zh" else "Public signals remain limited; run a seven-day non-transactional validation before sample work."),
        limit=700,
    )
    audience = _text(
        spec.get("audience") or spec.get("audience_wedge"),
        default="有明确使用场景与目标预算的潜在用户" if language == "zh" else "Prospective users with a concrete scenario and target budget",
        limit=320,
    )
    validation_goal = _text(
        spec.get("validation_goal") or spec.get("goal"),
        default="验证问题优先级、预算接受度、现有替代方案与购买时机" if language == "zh" else "Validate problem priority, budget acceptance, current alternatives, and buying trigger",
        limit=420,
    )
    evidence = _normalize_evidence(spec, language=language)
    competitors = _normalize_competitors(spec, language=language)
    hypotheses = _normalize_hypotheses(spec, language=language)
    experiments = _normalize_experiments(spec, language=language)

    decision_text = launch_decision_label(decision, language)

    observed_count = sum(entry["evidence_label"] == "observed_public" for entry in evidence)
    uploaded_count = sum(entry["evidence_label"] == "uploaded_real" for entry in evidence)
    weak_count = len(evidence) - observed_count - uploaded_count
    evidence_items = "".join(
        f'<li><span class="tag">{html.escape(entry["evidence_label"])}</span> {html.escape(entry["claim"])}' + (f' <a href="{html.escape(entry["source_urls"][0], quote=True)}">source</a>' if entry["source_urls"] else "") + "</li>"
        for entry in evidence
    )
    plan_items = "".join(f"<li><strong>D{html.escape(row['day'])}</strong> {html.escape(row['action'])}</li>" for row in experiments)
    hypothesis_items = "".join(f"<li>{html.escape(value)}</li>" for value in hypotheses)
    if language == "zh":
        html_title = f"{category}｜Launch Validation War Room"
        labels = {
            "audience": "验证人群",
            "goal": "验证目标",
            "evidence": "证据账本",
            "hypotheses": "关键假设",
            "plan": "7 天动作",
            "boundary": "决策边界",
            "price": "目标价",
            "verified": "已核验公开证据",
            "weak": "待验证信号",
        }
        boundary = "当前无样品、无规格；所有产品事实、性能、销量与用户效果均未证实。本页只用于需求验证，不接受订单或付款。"
    else:
        html_title = f"{category} | Launch Validation War Room"
        labels = {
            "audience": "Audience",
            "goal": "Validation goal",
            "evidence": "Evidence ledger",
            "hypotheses": "Critical assumptions",
            "plan": "7-day actions",
            "boundary": "Decision boundary",
            "price": "Target price",
            "verified": "Verified public evidence",
            "weak": "Signals to validate",
        }
        boundary = "There is no sample or specification. Product facts, performance, sales, and outcomes are unverified. This page supports research only and accepts no order or payment."
    war_room = f"""<!doctype html>
<html lang="{("zh-CN" if language == "zh" else "en")}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(html_title)}</title>
<style>
:root{{--paper:#f6f7f5;--surface:#fff;--ink:#171a18;--muted:#626965;--accent:#176b4d;--accent-soft:#e5f2eb;--line:#d9dedb;--warning:#8a5418}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:14px/1.55 ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1120px;margin:0 auto;padding:32px}}
header{{padding:8px 0 24px;border-bottom:1px solid var(--line)}}
.kicker{{margin:0 0 8px;color:var(--accent);font-weight:700}}h1{{margin:0 0 10px;font-size:28px}}h2{{font-size:15px;margin:0 0 10px}}p{{margin:6px 0}}
.decision{{display:inline-block;margin-top:12px;padding:6px 10px;border-radius:6px;background:var(--accent-soft);color:var(--accent);font-weight:700}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}}
.metric{{padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-radius:6px}}
.metric span{{display:block;color:var(--muted);font-size:12px}}
.metric strong{{display:block;margin-top:3px;font-size:19px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
.panel{{padding:18px;background:var(--surface);border:1px solid var(--line);border-radius:6px}}ul{{padding-left:20px;margin:8px 0}}li{{margin:6px 0}}
.tag{{font:700 11px/1 ui-monospace,monospace;color:var(--warning);background:#fff2df;border-radius:4px;padding:3px 5px}}
a{{color:var(--accent)}}.boundary{{margin:18px 0 0;padding-top:14px;border-top:1px solid var(--line);color:var(--muted)}}
</style></head>
<body><main><header><p class="kicker">OpenSKU / Launch Validation</p><h1>{html.escape(html_title)}</h1><p>{html.escape(rationale)}</p><span class="decision">{html.escape(decision_text)}</span></header>
<section class="metrics">
<div class="metric"><span>{labels["price"]}</span><strong>{html.escape(target_price)}</strong></div>
<div class="metric"><span>{labels["verified"]}</span><strong>{observed_count + uploaded_count}</strong></div>
<div class="metric"><span>{labels["weak"]}</span><strong>{weak_count}</strong></div>
</section>
<section class="grid"><article class="panel"><h2>{labels["audience"]}</h2><p>{html.escape(audience)}</p><h2>{labels["goal"]}</h2><p>{html.escape(validation_goal)}</p></article>
<article class="panel"><h2>{labels["hypotheses"]}</h2><ul>{hypothesis_items}</ul></article>
<article class="panel"><h2>{labels["evidence"]}</h2><ul>{evidence_items}</ul></article>
<article class="panel"><h2>{labels["plan"]}</h2><ul>{plan_items}</ul></article>
</section>
<p class="boundary"><strong>{labels["boundary"]}:</strong> {html.escape(boundary)}</p></main></body></html>"""

    if language == "zh":
        hypothesis_lines = "\n".join(f"{index}. {value}" for index, value in enumerate(hypotheses, start=1))
        positioning = f"""# {category} 定位与验证简报

## 当前判断

**{decision_text}**。{rationale}

## 人群与任务

- 验证人群：{audience}
- 目标价：{target_price}
- 验证目标：{validation_goal}
- 当前阶段：无样品、无规格，不把概念或公开搜索摘要写成产品事实。

## 关键假设

{hypothesis_lines}

## 7 天决策规则

只记录可追溯的来源、日期、样本口径、原话和行为信号。若问题、预算与切换理由形成一致信号，则进入下一轮；若信号互相矛盾则延长验证；若有效信号持续不足或关键结论无法核验，则停止进入样品阶段。
"""
        listing = _chinese_listing_template(category, target_price, audience, validation_goal, hypotheses)
        content = _chinese_content_template(category, target_price, audience, hypotheses, experiments)
    else:
        hypothesis_lines = "\n".join(f"{index}. {value}" for index, value in enumerate(hypotheses, start=1))
        positioning = f"""# {category} Positioning and Validation Brief

## Current decision

**{decision_text}.** {rationale}

## Audience and job

- Audience: {audience}
- Target price: {target_price}
- Validation goal: {validation_goal}
- Stage: no sample and no specification; concepts and search snippets are not product facts.

## Critical assumptions

{hypothesis_lines}

## Seven-day decision rule

Record traceable sources, dates, sample definitions, exact wording, and behavior signals.
Advance only when the problem, budget, and switching reason align; extend when signals
conflict; stop sample work when qualified evidence remains weak or material conclusions
cannot be verified.
"""
        listing = _english_listing_template(category, target_price, audience, validation_goal, hypotheses)
        content = _english_content_template(category, target_price, audience, hypotheses, experiments)

    ledger = {
        "meta": {
            "product_category": category,
            "target_price": target_price,
            "decision": decision,
            "stage": "no_sample_no_spec",
        },
        "entries": evidence,
    }
    return {
        "launch-war-room.html": war_room,
        "evidence-ledger.json": json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        "competitor-table.csv": _csv(
            ["competitor", "price_signal", "positioning_signal", "evidence_label", "source_url", "notes"],
            competitors,
        ),
        "positioning-brief.md": positioning,
        "listing-pack.md": listing,
        "content-pack.md": content,
        "launch-calendar.csv": _csv(
            ["day", "action", "evidence_to_collect", "success_criterion", "stop_condition"],
            experiments,
        ),
    }


def build_launch_pack_completion_message(spec: Mapping[str, Any], *, user_request: str) -> str:
    """Build the visible terminal response from the same normalized Pack inputs."""
    language = _language(spec, user_request)
    decision = normalize_launch_decision(spec.get("decision") or spec.get("verdict"))
    decision_text = launch_decision_label(decision, language)
    rationale = _text(
        spec.get("decision_rationale") or spec.get("rationale"),
        default=("公开信号仍有限；请以证据账本中的缺口为准。" if language == "zh" else "Public signals remain limited; use the evidence ledger gaps as the decision boundary."),
        limit=700,
    )
    validation_goal = _text(
        spec.get("validation_goal") or spec.get("goal"),
        default=("验证问题、预算与切换理由" if language == "zh" else "Validate the problem, budget, and switching reason"),
        limit=360,
    )
    evidence = _normalize_evidence(spec, language=language)
    observed_count = sum(entry["evidence_label"] == "observed_public" for entry in evidence)
    uploaded_count = sum(entry["evidence_label"] == "uploaded_real" for entry in evidence)
    weak_count = len(evidence) - observed_count - uploaded_count
    limitations = list(dict.fromkeys(entry["limitation"] for entry in evidence if entry["limitation"] and entry["evidence_label"] not in {"observed_public", "uploaded_real"}))
    if language == "zh":
        gap_text = "；".join(limitations[:2]) or "尚无店铺后台、样品或规格证据。"
        if decision == "insufficient_evidence":
            next_step = "先补齐上述公开信号；未补齐前，不进入样品、投放或采购阶段。"
        elif decision == "test_after_fixing_assumptions":
            next_step = f"先补齐关键假设和至少一条可核验证据；满足后再执行：{validation_goal}"
        elif decision == "hold":
            next_step = "暂停当前方向；只有出现新的可核验证据时再重启。"
        else:
            next_step = validation_goal
        return (
            f"## 当前判断\n\n**{decision_text}。**\n\n{rationale}\n\n"
            "## 证据状态\n\n"
            f"- 已核验公开证据：{observed_count} 条\n"
            f"- 已上传真实证据：{uploaded_count} 条\n"
            f"- 估算、假设或不可用：{weak_count} 条\n"
            f"- 关键缺口：{gap_text}\n\n"
            f"## 下一步\n\n{next_step}\n\nLaunch Validation Pack 已通过预检，7 个交付文件已生成。"
        )

    gap_text = "; ".join(limitations[:2]) or "No store, sample, or specification evidence is available yet."
    if decision == "insufficient_evidence":
        next_step = "Collect the missing public signals before sample work, media spend, or procurement."
    elif decision == "test_after_fixing_assumptions":
        next_step = f"Resolve the critical assumptions and verify at least one source, then: {validation_goal}"
    elif decision == "hold":
        next_step = "Pause this direction and restart only when new verifiable evidence appears."
    else:
        next_step = validation_goal
    return (
        f"## Current decision\n\n**{decision_text}.**\n\n{rationale}\n\n"
        "## Evidence status\n\n"
        f"- Verified public evidence: {observed_count}\n"
        f"- Uploaded real evidence: {uploaded_count}\n"
        f"- Estimated, assumed, or unavailable: {weak_count}\n"
        f"- Critical gap: {gap_text}\n\n"
        f"## Next step\n\n{next_step}\n\nThe Launch Validation Pack passed preflight and all seven files were generated."
    )

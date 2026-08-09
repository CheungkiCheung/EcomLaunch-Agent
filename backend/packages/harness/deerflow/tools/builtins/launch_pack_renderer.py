"""Deterministically render a compact Launch Pack specification into seven files."""

from __future__ import annotations

import csv
import html
import io
import json
import re
from collections.abc import Mapping
from typing import Any

from deerflow.tools.builtins.launch_pack_guard import (
    _concept_context,
    _is_direct_evidence_url,
    _safe_content_template,
    _safe_listing_template,
)

_VALID_EVIDENCE_LABELS = {"observed_public", "uploaded_real", "estimated", "assumption", "unavailable"}
_VALID_DECISIONS = {"test_now", "test_after_fixing_assumptions", "hold", "insufficient_evidence"}
_CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")


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
            "claim": "尚未获得可直接核验的公开来源；本轮先验证问题、预算和购买时机。"
            if language == "zh"
            else "No directly verifiable public source was available; validate the problem, budget, and buying trigger first.",
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
            action = _text(raw.get("action") or raw.get("experiment"), limit=300)
            if not action:
                continue
            experiments.append(
                {
                    "day": _text(raw.get("day"), default=str(index), limit=16),
                    "action": action,
                    "evidence_to_collect": _text(raw.get("evidence_to_collect") or raw.get("signal"), default="traceable responses", limit=240),
                    "success_criterion": _text(raw.get("success_criterion") or raw.get("success"), default="record qualified signals", limit=240),
                    "stop_condition": _text(raw.get("stop_condition") or raw.get("stop"), default="stop if qualified signals remain weak", limit=240),
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


def _english_listing_template(category: str, target_price: str) -> str:
    return f"""# {category} Listing Pack (concept validation)

Stage: no sample and no specification. This page collects category, scenario, alternative, and budget feedback only. It is not a product page and does not accept orders or payment.

## Research title

{category} | {target_price} concept preference study

## Questions

- What problem matters most when choosing or using this category?
- Which current alternative is unsatisfactory, and in what real scenario?
- Which information gap would stop you from learning more?
- What budget range and buying trigger would justify further validation?

## Action

Complete the anonymous preference survey or opt in to research updates. No supply, price, date, or product-capability promise is made.
"""


def _english_content_template(category: str, target_price: str) -> str:
    return f"""# {category} Content Pack (concept research)

Stage: no sample and no specification. Every item below asks about problems,
scenarios, alternatives, and budget; nothing implies that a purchasable product exists.

## Question post A

When choosing this category, what real problem would you solve first? Share the scenario, the current alternative, and the information you need before considering a change. This post does not sell or accept payment.

## Question post B

For a {target_price} category concept, which factor would you validate first: the real use scenario, budget, buying trigger, current alternative, or another problem? Explain why.

## Short-video question script

“This is a concept study for {category}. The target range is {target_price}.
What problem matters most, and what missing information would stop you from learning more?
There is no sample or purchasable item, and no payment or preorder is accepted.”
"""


def render_launch_pack(spec: Mapping[str, Any], *, user_request: str) -> dict[str, str]:
    """Return canonical Launch Pack filenames mapped to deterministic contents."""
    language = _language(spec, user_request)
    inferred_category, inferred_price = _concept_context(user_request)
    category = _text(spec.get("category") or spec.get("product_category"), default=inferred_category, limit=120)
    target_price = _text(spec.get("target_price") or spec.get("price_range"), default=inferred_price, limit=80)
    decision = _text(spec.get("decision") or spec.get("verdict"), default="insufficient_evidence", limit=60).lower()
    if decision not in _VALID_DECISIONS:
        decision = "insufficient_evidence"
    rationale = _text(
        spec.get("decision_rationale") or spec.get("rationale"),
        default=(
            "公开信号仍有限；先做七天、不可交易的轻量验证，再决定是否进入样品阶段。"
            if language == "zh"
            else "Public signals remain limited; run a seven-day non-transactional validation before sample work."
        ),
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

    decision_labels = {
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
    decision_text = decision_labels[language][decision]

    evidence_items = "".join(
        f"<li><span class=\"tag\">{html.escape(entry['evidence_label'])}</span> {html.escape(entry['claim'])}"
        + (f" <a href=\"{html.escape(entry['source_urls'][0], quote=True)}\">source</a>" if entry["source_urls"] else "")
        + "</li>"
        for entry in evidence
    )
    plan_items = "".join(f"<li><strong>D{html.escape(row['day'])}</strong> {html.escape(row['action'])}</li>" for row in experiments)
    if language == "zh":
        html_title = f"{category}｜Launch Validation War Room"
        labels = {"decision": "当前判断", "audience": "验证人群", "goal": "验证目标", "evidence": "证据账本摘要", "plan": "7 天动作", "boundary": "边界"}
        boundary = "当前无样品、无规格；所有产品事实、性能、销量与用户效果均未证实。本页只用于需求验证，不接受订单或付款。"
    else:
        html_title = f"{category} | Launch Validation War Room"
        labels = {"decision": "Decision", "audience": "Audience", "goal": "Validation goal", "evidence": "Evidence summary", "plan": "7-day actions", "boundary": "Boundary"}
        boundary = "There is no sample or specification. Product facts, performance, sales, and outcomes are unverified. This page supports research only and accepts no order or payment."
    war_room = f"""<!doctype html>
<html lang="{('zh-CN' if language == 'zh' else 'en')}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(html_title)}</title>
<style>
:root{{--paper:#fff8ed;--ink:#332b25;--muted:#796b60;--accent:#d97745;--line:#ead7c4}}
*{{box-sizing:border-box}}
body{{margin:0;background:linear-gradient(135deg,#f4dec7,#fffaf2);color:var(--ink);font:15px/1.6 ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:980px;margin:32px auto;padding:28px}}
header,.card{{background:rgba(255,248,237,.94);border:1px solid var(--line);border-radius:18px;box-shadow:0 12px 32px rgba(79,52,34,.08)}}
header{{padding:28px;margin-bottom:18px}}
h1{{margin:0 0 8px;font-size:30px}}h2{{font-size:17px;margin:0 0 10px}}p{{margin:6px 0}}
.decision{{display:inline-block;margin-top:12px;padding:7px 12px;border-radius:999px;background:#f6c9a9;color:#713917;font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
.card{{padding:20px}}ul{{padding-left:20px;margin:8px 0}}li{{margin:6px 0}}
.tag{{font:700 11px/1 ui-monospace,monospace;color:#8a4b26;background:#f8dfcb;border-radius:999px;padding:4px 7px}}
a{{color:#a4491b}}.boundary{{margin-top:16px;color:var(--muted)}}
</style></head>
<body><main><header><p>OpenSKU</p><h1>{html.escape(html_title)}</h1><p>{html.escape(rationale)}</p><span class="decision">{html.escape(decision_text)}</span></header>
<section class="grid"><article class="card"><h2>{labels['audience']}</h2><p>{html.escape(audience)}</p><h2>{labels['goal']}</h2><p>{html.escape(validation_goal)}</p></article>
<article class="card"><h2>{labels['evidence']}</h2><ul>{evidence_items}</ul></article><article class="card"><h2>{labels['plan']}</h2><ul>{plan_items}</ul></article></section>
<p class="boundary"><strong>{labels['boundary']}:</strong> {html.escape(boundary)}</p></main></body></html>"""

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
        listing = _safe_listing_template(user_request or f"{target_price}的{category}")
        content = _safe_content_template(user_request or f"{target_price}的{category}")
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
        listing = _english_listing_template(category, target_price)
        content = _english_content_template(category, target_price)

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

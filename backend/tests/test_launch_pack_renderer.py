from __future__ import annotations

import json
from pathlib import Path

import pytest

from deerflow.tools.builtins.launch_pack_guard import validate_launch_pack
from deerflow.tools.builtins.launch_pack_renderer import (
    build_launch_pack_completion_message,
    enforce_verified_public_sources,
    render_launch_pack,
)

USER_REQUEST = "我想做一个 99-199 元的通勤咖啡杯，但没有任何店铺后台数据。请用公开信号判断是否值得做 7 天轻量验证，并输出 Launch Validation Pack。"


def test_renderer_builds_a_preflight_clean_seven_file_pack(tmp_path: Path) -> None:
    pack = render_launch_pack(
        {
            "category": "通勤咖啡杯",
            "target_price": "99-199 元",
            "decision": "test_now",
            "decision_rationale": "公开类目页提供了可核验的品类存在信号，但真实购买意愿仍需轻量验证。",
            "audience": "工作日通勤且正在比较现有替代方案的人群",
            "validation_goal": "验证问题优先级、预算和购买时机",
            "evidence": [
                {
                    "claim": "公开类目页存在相关商品集合",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://example.com/category"],
                },
                {
                    "claim": "通勤场景可能影响选择",
                    "evidence_label": "assumption",
                },
            ],
            "competitors": [
                {
                    "name": "公开类目替代方案",
                    "price_signal": "待逐页核验",
                    "positioning_signal": "品类集合页",
                    "evidence_label": "observed_public",
                    "source_url": "https://example.com/category",
                }
            ],
        },
        user_request=USER_REQUEST,
    )

    assert set(pack) == {
        "launch-war-room.html",
        "evidence-ledger.json",
        "competitor-table.csv",
        "positioning-brief.md",
        "listing-pack.md",
        "content-pack.md",
        "launch-calendar.csv",
    }
    for filename, content in pack.items():
        (tmp_path / filename).write_text(content, encoding="utf-8")

    assert validate_launch_pack(tmp_path, list(pack), user_request=USER_REQUEST) == []


def test_renderer_downgrades_observed_public_without_a_direct_url(tmp_path: Path) -> None:
    pack = render_launch_pack(
        {
            "category": "通勤咖啡杯",
            "decision": "insufficient_evidence",
            "evidence": [
                {
                    "claim": "搜索摘要声称该品类受欢迎",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://www.google.com/search?q=cup"],
                }
            ],
            "competitors": [
                {
                    "name": "搜索结果中的竞品",
                    "evidence_label": "observed_public",
                    "source_url": "https://www.google.com/search?q=cup",
                }
            ],
        },
        user_request=USER_REQUEST,
    )
    for filename, content in pack.items():
        (tmp_path / filename).write_text(content, encoding="utf-8")

    assert '"evidence_label": "estimated"' in pack["evidence-ledger.json"]
    assert ",estimated,," in pack["competitor-table.csv"]
    assert validate_launch_pack(tmp_path, list(pack), user_request=USER_REQUEST) == []


def test_renderer_maps_supported_chinese_decision_to_canonical_enum() -> None:
    pack = render_launch_pack(
        {
            "category": "通勤咖啡杯",
            "decision": "值得做7天轻量验证，但需聚焦单一卖点",
        },
        user_request=USER_REQUEST,
    )

    ledger = json.loads(pack["evidence-ledger.json"])
    assert ledger["meta"]["decision"] == "test_now"
    assert "值得立即做 7 天轻量验证" in pack["positioning-brief.md"]


def test_renderer_rejects_unknown_decision_instead_of_silently_downgrading() -> None:
    with pytest.raises(ValueError, match="decision must be one of"):
        render_launch_pack(
            {
                "category": "通勤咖啡杯",
                "decision": "看起来还可以",
            },
            user_request=USER_REQUEST,
        )


def test_flash_evidence_requires_a_successfully_fetched_source() -> None:
    prepared = enforce_verified_public_sources(
        {
            "evidence": [
                {
                    "claim": "已打开的公开页面",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://example.com/verified/"],
                },
                {
                    "claim": "只有搜索摘要",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://example.com/snippet"],
                },
            ],
            "competitors": [
                {
                    "name": "未核验竞品",
                    "evidence_label": "observed_public",
                    "source_url": "https://example.com/competitor",
                }
            ],
        },
        {"https://example.com/verified"},
    )

    assert prepared["evidence"][0]["evidence_label"] == "observed_public"
    assert prepared["evidence"][1]["evidence_label"] == "estimated"
    assert "未成功抓取原网页" in prepared["evidence"][1]["limitation"]
    assert prepared["competitors"][0]["evidence_label"] == "estimated"
    assert "仅作发现线索" in prepared["competitors"][0]["notes"]


def test_flash_zero_verified_evidence_reconciles_test_now_decision() -> None:
    prepared = enforce_verified_public_sources(
        {
            "category": "通勤咖啡杯",
            "decision": "test_now",
            "decision_rationale": "公开信号支持立即测试。",
            "evidence": [
                {
                    "claim": "搜索摘要中的热度信号",
                    "evidence_label": "observed_public",
                    "source_urls": ["https://example.com/not-fetched"],
                }
            ],
        },
        set(),
    )

    assert prepared["decision"] == "test_after_fixing_assumptions"
    assert "尚不足以支持“立即测试”" in prepared["decision_rationale"]
    completion = build_launch_pack_completion_message(prepared, user_request=USER_REQUEST)
    assert "先补齐关键假设和至少一条可核验证据" in completion


def test_war_room_exposes_decision_metrics_and_hypotheses() -> None:
    pack = render_launch_pack(
        {
            "category": "通勤咖啡杯",
            "target_price": "99-199 元",
            "decision": "test_after_fixing_assumptions",
            "decision_rationale": "先核验公开来源。",
            "evidence": [{"claim": "待核验热度", "evidence_label": "estimated"}],
            "hypotheses": ["洒漏顾虑可能影响选择。"],
        },
        user_request=USER_REQUEST,
    )

    war_room = pack["launch-war-room.html"]
    assert "目标价" in war_room
    assert "已核验公开证据" in war_room
    assert "待验证信号" in war_room
    assert "洒漏顾虑可能影响选择。" in war_room
    assert "linear-gradient" not in war_room
    assert "border-radius:18px" not in war_room


def test_renderer_uses_rich_experiment_fields_and_category_context(tmp_path: Path) -> None:
    pack = render_launch_pack(
        {
            "category": "通勤咖啡杯",
            "target_price": "99-199 元",
            "decision": "test_after_fixing_assumptions",
            "decision_rationale": "先核验一条公开价格来源，再开始轻量验证。",
            "audience": "工作日乘地铁、会自带咖啡的上班族",
            "validation_goal": "验证密封顾虑、价格接受度和主动登记意愿",
            "hypotheses": [
                "通勤时的洒漏顾虑比外观偏好更影响选择。",
                "目标用户能解释接受 99-199 元的具体条件。",
            ],
            "experiments": [
                {
                    "name": "发布两版通勤场景问题帖",
                    "type": "问题型内容 A/B",
                    "channel": "小红书",
                    "metric": "有效场景评论数与问卷完成数",
                    "goal": "至少收集 8 条带现有替代方案的回答",
                    "cost": "0-100 元",
                }
            ],
        },
        user_request=USER_REQUEST,
    )
    for filename, content in pack.items():
        (tmp_path / filename).write_text(content, encoding="utf-8")

    assert "工作日乘地铁、会自带咖啡的上班族" in pack["listing-pack.md"]
    assert "密封顾虑、价格接受度和主动登记意愿" in pack["listing-pack.md"]
    assert "通勤时的洒漏顾虑" in pack["content-pack.md"]
    assert "发布两版通勤场景问题帖（渠道：小红书；形式：问题型内容 A/B；预算：0-100 元）" in pack["launch-calendar.csv"]
    assert "有效场景评论数与问卷完成数" in pack["launch-calendar.csv"]
    assert "至少收集 8 条带现有替代方案的回答" in pack["launch-calendar.csv"]
    assert validate_launch_pack(tmp_path, list(pack), user_request=USER_REQUEST) == []

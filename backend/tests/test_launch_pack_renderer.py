from __future__ import annotations

from pathlib import Path

from deerflow.tools.builtins.launch_pack_guard import validate_launch_pack
from deerflow.tools.builtins.launch_pack_renderer import render_launch_pack

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

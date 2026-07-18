---

## 🚀 EcomLaunch 上新决策快照 — `live-decision-taxonomy-prelaunch-002`

**当前阶段**: `pre_launch_test` — 搜索匹配验证

**推荐方向**: 🔄 **Pivot（转向）**

**决策依据**: 搜索查询 "smart coffee table"（查询类目：Coffee & Cocktail Tables，家具类）与候选产品 "all-clad 7 qt . slow cooker"（产品类目：Slow Cookers，厨房电器类）属于 **严重类目错配**。慢炖锅不具备咖啡桌的任何属性（非家具、非台面、无智能功能），在 fixture 数据中也无任何 labeling 记录关联该查询与产品。按照决策规则，搜索匹配失败默认为 Pivot，而非 Kill——该 SKU（慢炖锅）在其正确类目下仍有测试价值。

**关键风险信号**: 该产品在 100 条评分中仅获 **2.0 均分**（98 条评论），在 fixture 数据中无评论文本可用于归因。在解决评分根因（质量缺陷 vs 期望错配）之前，任何上架投入都有较高失败风险。

**下一轮测试**: 获取完整评论文本（98 条）进行根因分析：
- 若 ≥60% 差评源于质量缺陷 → **Kill**（不可挽救）
- 若 ≥60% 差评源于期望错配或类目错误定位 → 在正确查询词下重新测试

**推广调整**: 无现成推广活动。需完全放弃 "smart coffee table" 查询路径，转向厨房电器查询词：`7 qt slow cooker`、`programmable slow cooker`、`All-Clad slow cooker`

**数据限制**: 仅使用公开 benchmark fixture（WANDS 数据集）。无 GMV、CTR、CVR、ROI、广告花费、退款率、复购率等私域指标数据。无评论文本—仅有聚合评分计数。

**已生成 10 个交付物**:
- `launch-war-room.html`
- `evidence-ledger.json`
- `competitor-table.csv`
- `positioning-brief.md`
- `listing-pack.md`
- `content-pack.md`
- `launch-calendar.csv`
- `launch-state.json`
- `promotion-replan.md`
- `knowledge-deltas.json`

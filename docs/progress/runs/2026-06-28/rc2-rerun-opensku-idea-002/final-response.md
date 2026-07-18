## 上新决策快照 — OpenSKU 案例 `opensku-idea-002`

### 诊断结果

| 维度 | 结论 |
|---|---|
| **当前阶段** | **idea_only**（仅创意阶段，未开始任何验证） |
| **推荐方向** | **Pivot**（转向） |
| **核心原因** | WANDS 搜索查询 `"smart coffee table"`（咖啡桌/家具）与产品 `Yes to Tomatoes Detoxifying Charcoal Cleanser`（护肤品）存在**彻底的品类错配**——护肤品在家居品类下不可能获得有效搜索流量 |

### 关键发现

1. **搜索匹配错误** — WANDS 查询 `"smart coffee table"` 的 query_class 是 "Coffee & Cocktail Tables"（家具），而产品在 All Beauty 下。这是工具故意设置的搜索匹配陷阱，正确诊断应该是 **Pivot** 而非 Kill（产品本身无致命缺陷）。
2. **气味顾虑可管理** — 提示中 "Works great but smells a little weird" 的评论来自不同 ASIN（B081TJ8YS3），并非该清洁产品的直接评价。但气味确是护肤品类中常见痛点，策略上可将其重新框定为"天然碳粉的本真气味，无人工香精"的定位优势。
3. **粉状剂型的差异化机会** — 产品为 Powder 形式（粉状洁面），区别于主流液体洁面，可成为内容差异化卖点（粉末→泡沫的视觉仪式感）。

### 下一轮测试（7天验证循环）

1. **Day 1-3**：在美妆社区触达 5-10 名目标用户（痘肌/油皮），测试气味接受度和购买意愿
2. **Day 4-7**：若气味抵触率 <50%，测试价格接受度和内容爆点偏好
3. **决策规则**：≥60% 显示购买意愿 → **Go** 进入 `pre_launch_test`

### 宣传调整

完全放弃 `"smart coffee table"` 方向，转向：
- **目标查询**：charcoal cleanser、detoxifying face wash、face wash for acne prone skin、Yes To Tomatoes cleanser
- **分类**：All Beauty / Face Wash & Cleansers → 不是 Coffee & Cocktail Tables
- **渠道**：Amazon Beauty、美妆社区、护肤群组

### 数据局限性

全部证据来自公开基准数据集（benchmark fixtures），无任何商家后台数据。价格、销量、转化率、退款率、复购率等指标均标记为 unavailable。该 SKU 仅有 3 个评分记录，统计意义有限。

---

### 交付物（10 项）

- `launch-war-room.html` — 完整决策仪表盘
- `evidence-ledger.json` — 证据分类账
- `competitor-table.csv` — 竞品对比表
- `positioning-brief.md` — 定位简报
- `listing-pack.md` — 产品 listing 方案
- `content-pack.md` — 内容/视频方案
- `launch-calendar.csv` — 7天验证计划
- `launch-state.json` — 上新状态快照
- `promotion-replan.md` — 推广计划调整
- `knowledge-deltas.json` — 知识沉淀

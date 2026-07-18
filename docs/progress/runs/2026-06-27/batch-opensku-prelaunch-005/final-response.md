## 验收简报 — batch-opensku-prelaunch-005

**上新阶段：** pre_launch_test（查询-产品搜索匹配验证）  
**决策：** **Pivot（转向）**

### 诊断摘要

候选产品 **Baldwin Prestige Alcott Passage Knob with Round Rosette**（产品类别：Door Knobs，品类层级：Home Improvement > Door Hardware > Round Door Knobs）与测试查询 **"chair and a half recliner"**（查询类别：Recliners，家具/坐具）之间存在 **完全的品类错配**：

- 查询意图是寻找大型可躺式扶手椅，产品是一款入户门通道球形把手
- WANDS 基准数据中不存在 `query_id=4` + `product_id=4` 的标签行 — 零相关性证据
- 产品本身经过验证：5.0 分评分（70 条评分、42 条评价）、纯铜材质、终身保修、ANSI/BHMA Grade 2 商用级耐久性

**决定依据：** 品类错配属于搜索路径问题，非产品本身问题 → 默认 **Pivot**（非 Kill、非 Hold）。

### 转向建议

- **新目标查询：** `passage door knob round rosette`、`brass interior door knob`、`Baldwin prestige door knob`
- **受众楔子：** 正在升级室内门配件的房主/DIY 装修者（非家具购物者）
- **核心承诺：** "纯铜材质搭配终身保修和商用级耐久性，让每一扇室内门都经得起时间考验"
- **推广调整：** 立刻停止 "chair and a half recliner" 类别下的所有推广投放，转向家装/门配件渠道

### 数据限制

所有证据来自 **公共基准数据 (WANDS benchmarks)**，无任何商户后台指标（GMV、CTR、CVR、ROI、广告花费、退款率、复购率等均不可用）。

### 已生成文档（10 份）

1. `launch-war-room.html`
2. `evidence-ledger.json`
3. `competitor-table.csv`
4. `positioning-brief.md`
5. `listing-pack.md`
6. `content-pack.md`
7. `launch-calendar.csv`
8. `launch-state.json`
9. `promotion-replan.md`
10. `knowledge-deltas.json`

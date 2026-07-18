## 验证完成 — 上线决策快照

**案例：** rc2-rerun-opensku-prelaunch-001  
**上新产品阶段：** Pre‑Launch Test（搜索匹配验证）  
**决策：** **Pivot（调整）**

### 核心发现

查询 `salon chair`（按摩椅大类）与候选商品 `solid wood platform bed`（床类）存在根本性的类目不匹配。WANDS 基准数据中没有任何相关性标签将该产品与 "salon chair" 查询关联——查询意图（美发/按摩椅）与产品功能（实木平板床、卧室家具、仅限住宅使用）完全正交。

### 为什么不是 Kill

该 SKU（实木平板床，相思木/橡胶木，4.5★/15条评价，500-800磅承重，5年有限保修）本身具备正向信号，在正确类目下有明确的需求。问题出在查询定位，而非产品本身。

### 建议调整方向

| 维度 | 当前（停止） | 调整后（推进） |
|------|-------------|---------------|
| 目标查询 | `salon chair` | `platform bed` / `solid wood bed frame` / `twin bed frame` |
| 类目 | Massage Chairs | Beds / Bed Frames |
| 受众 | 美发/按摩椅买家 | 为孩子买床的父母、客房买家、首套公寓租户、小空间卧室 |

### 下一轮实验

- **7天搜索匹配测试**，使用修正后的查询词：`twin solid wood platform bed`、`acacia wood bed frame queen`、`low profile platform bed with headboard`
- 在 **Furniture / Bedroom Furniture / Beds & Headboards / Beds / Twin Beds** 类目下收集至少 10 次目标类目曝光信号 + 3 次购买意向信号
- **所有 "salon chair" 相关的推广立即停止**

### 数据局限

所有证据来自公共 WANDS 基准数据集。无商家私有指标（GMV、CTR、CVR、ROI、广告支出、利润率、退款率、复购率）。商品价格不可用。承重值存在冲突（500 lbs 和 800 lbs 两个值）。合规标识为供应商原始元数据，未经独立验证。

### 已生成的工件

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

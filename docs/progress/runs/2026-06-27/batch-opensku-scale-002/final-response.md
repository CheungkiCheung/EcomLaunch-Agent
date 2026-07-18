## 上新阶段诊断结果

**Case ID:** batch-opensku-scale-002 | **产品:** Smart Coffee Table | **查询词:** "smart coffee table"

### 关键发现

| 维度 | 结果 |
|---|---|
| **实际阶段** | `pre_launch_test`（原标 `scale_iterate` 证据不足，回退） |
| **推荐决策** | **🔄 Pivot — 重新规划，非盲目扩张** |
| **唯一正向信号** | 查询 "smart coffee table" → 品类 "Coffee & Cocktail Tables" 映射有效 ✅（WANDS 公开数据集） |
| **核心缺口** | 产品规格、定价、竞品地图、用户声音 — 四项均无数据 |

### 决策依据

- **搜索匹配已确认**：WANDS 数据集显示查询词被正确归入家具类目，这是唯一可用的公开信号
- **但无任何品类专属数据**：Olist 的订单/评价均来自香水、体育、母婴等无关品类，无法迁移至智能咖啡桌
- **不应盲目扩张**：`scale_iterate` 需要至少 soft launch 数据支撑，目前证据只够判断搜索相关性
- **不是 Kill**：搜索分类有效，产品概念本身无致命缺陷，只是需要先验证产品定义

### 下一轮测试（7天 pre_launch_test）

1. 获取产品规格表 — 明确 "smart" 包含哪些功能（无线充电？蓝牙？LED？）
2. 验证价格接受度 — 简单双选项落地页（$149 vs $299）
3. 收集 5-10 个目标用户兴趣信号 — 预售意向/问卷反馈
4. 手动浏览竞品 — Amazon/Walmart/Ikea 上 3-5 款智能咖啡桌及价位

### 推广调整

从 "扩量投放" 降级为 "需求验证"。零投放预算，直到产品规格和定价被实证检验。

### 数据边界

所有证据来自公开基准测试文件（Olist, WANDS），非商户私密数据。无 GMV、CTR、CVR、ROI、退款率、复购率可用。Evidence-checker 子代理因递归上限超时无法完成，审计由 launch-director 自行完成。

---

### 生成文件清单（10件）

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

所有文件已通过 OpenSKU 验证器检查，JSON 可解析，CSV 列头完整，无私有指标泄漏，证据 ID 一致。

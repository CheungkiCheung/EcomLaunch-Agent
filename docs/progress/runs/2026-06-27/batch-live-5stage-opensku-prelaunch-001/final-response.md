## ✅ OpenSKU 上新验证完成 — 案例 opensku-prelaunch-001

### 验证摘要

| 维度 | 结果 |
|------|------|
| **当前阶段** | `pre_launch_test`（预发布测试） |
| **推荐决策** | ⚠️ **Pivot（转向）** |
| **验证来源** | WANDS 公开基准测试集（仅此） |

### 核心发现

查询 **"salon chair"** 在 WANDS 中的意图归类为 **按摩椅（Massage Chairs）**，而候选商品 **solid wood platform bed（实木平板床）** 的分类是 **床（Beds）→ 家具/卧室家具/床/双人床**。WANDS 相关性标注显示：查询 ID=0 (salon chair) 的相关商品列表**不含**该床架（product_id=0）。这是一个**基础性品类错配**——两个产品类目之间不存在重叠的用户任务场景。

### 推荐行动

**方向：Pivot（转向）** — 停止将此商品与 "salon chair" 搜索查询关联，**转向床品类目相关查询**。

**下一轮测试（7天）**：针对 3-5 个床品类目相关查询进行测试——
- `twin platform bed`
- `solid wood bed frame`
- `acacia wood bed frame`
- `twin size bed with headboard`
- `platform bed no box spring`

**宣传调整**：
- ❌ **立即停止**所有针对 "salon chair"/按摩椅类查询的广告投放
- ✅ **重新分配预算**至床品类目查询
- 每条查询设定 **stop/continue 规则**：7天内若无正向互动信号则终止

**数据限制**：
- 所有证据来源均为 **WANDS 公开基准测试集**，非实时平台数据
- **不可用数据**：价格、客户评价文本、竞品定价、GMV/CTR/CVR/ROI/广告支出/退款率/复购率等私域指标
- 产品参数为制造商自报，非独立验证（"non-toxic" 需测试报告，"5-year warranty" 需确认条款）
- 15条评价的样本量较小

### 已生成制品（10个文件）

| 文件 | 说明 |
|------|------|
| `launch-war-room.html` | 决策作战室仪表板 |
| `evidence-ledger.json` | 证据分类账（5条条目） |
| `competitor-table.csv` | 竞品映射表 |
| `positioning-brief.md` | 定位简报（含证据限制声明） |
| `listing-pack.md` | 商品列表文案包（含声明就绪度矩阵） |
| `content-pack.md` | 内容资产包（含声明就绪度矩阵） |
| `launch-calendar.csv` | 7天下一轮实验日历 |
| `launch-state.json` | 上新状态快照 |
| `promotion-replan.md` | 宣传调整计划（含 stop/continue 规则） |
| `knowledge-deltas.json` | 知识增量记录 |

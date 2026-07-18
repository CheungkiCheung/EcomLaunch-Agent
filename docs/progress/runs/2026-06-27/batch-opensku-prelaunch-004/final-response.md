## 上新决策快照 — batch-opensku-prelaunch-004

**上新阶段**：pre_launch_test（搜索匹配评估）

**推荐决策**：**Pivot（转向）**

**核心发现**：搜索词「turquoise pillows」（query_class: Accent Pillows，家居装饰/靠枕）与候选产品「all-clad all professional tools pizza cutter」（product_class: Slicers, Peelers And Graters，厨房工具/披萨切刀）属于**完全不同的产品类别**，不存在任何交叉。WANDS基准数据集中该查询-产品对没有相关性标签，分类级不匹配是结构性的，非创意文案可以弥补。

**转向后的目标**：
- **搜索词**：从「turquoise pillows」→「pizza cutter」、「All-Clad pizza cutter」、「stainless steel pizza cutter」
- **品类**：从 Accent Pillows → Kitchen & Dining / Kitchen Tools & Gadgets / Slicers, Peelers And Graters
- **受众楔子**：从家居装饰购物者 → 家庭烹饪爱好者、All-Clad品牌消费者、厨房工具买家

**下一轮测试**：在修正后的搜索词和品类下执行有边界的预上线搜索匹配测试，收集3-5个同价位公开竞品的对比信号。

**宣传调整**：立即停止所有针对「turquoise pillows」或 Accent Pillows 品类的投放，品类/关键词修正前不启动任何推广。

**数据局限**：本次运行基于公开基准数据集（WANDS）固定快照；无价格数据、无消费者评论原文、无竞品数据、无商家后台指标（GMV/CTR/CVR/ROI/退款率/复购率）。

**已交付工件**（10份）：
- `launch-war-room.html`、`evidence-ledger.json`、`competitor-table.csv`、`positioning-brief.md`、`listing-pack.md`、`content-pack.md`、`launch-calendar.csv`、`launch-state.json`、`promotion-replan.md`、`knowledge-deltas.json`

## 启动决策快照 — Howard LC0008 Leather Conditioner

### 阶段判定：Idea Only（纯想法阶段）
产品在 fixture 中仅有类目归属（All Beauty）、10 个评分（4.8★）、品牌名称和包装尺寸。**无价格、无描述、无图片、无评论正文、无销售数据** — 属于早期想法阶段。

### 决策：Pivot（转向）
**核心原因：搜索适配错位。** WANDS 查询 `salon chair` 映射到 `Massage Chairs`（家具类），而本品是皮革护理液 — 搜索意图完全不匹配。但产品本身（4.8★ 评分、4瓶装价值组合）可能有可用价值，不应 Kill。按 taxonomy 规则：搜索适配错位默认 Pivot。

### 关键方向
- **受众楔子**：皮家具/汽车皮革座椅主人，非 All Beauty 美妆消费者
- **核心主张**：保养和保护光滑成品皮革表面（需产品规格确认，无香型/安全声明）
- **下一轮测试**：修复类目/查询对齐 → 在 `leather conditioner` 等正确查询下跑 $50 Amazon Sponsored Products 精确匹配测试（7天）

### 数据边界
所有证据来自公开基准 fixture（`amazon_reviews.jsonl`、`wands.jsonl`），**非真实商户后台数据**。关键缺失：
- 价格不可用
- 该 SKU 无任何评论正文（'Such a lovely scent' 来自发胶产品，非本品）
- 无竞品、安全合规、需求体量等数据
- 所有私域指标（GMV、CTR、CVR、ROI、退款率、复购率）均不可用

### 生成物清单
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

## 上新决策快照：`batch-opensku-softlaunch-005`

| 维度 | 结果 |
|------|------|
| **上新阶段** | **soft_launch**（软启动期） |
| **本期决策** | **🟢 Go** — 现有证据支持进入下一轮有界验证测试 |
| **核心受众楔子** | 使用信用卡分期、看重准时配送的巴西家庭实用品消费者 |
| **核心承诺** | 一款尺寸 / 重量合适的家庭实用品，日常可靠，准时送达 |

### 下一轮测试（14天循环）
1. **确认产品实际功能、材质、用途**（目前仅有品类标签 `utilidades_domesticas`，无具体描述文本）
2. **跑关键词标题测试** — 用葡萄牙语品类关键词 + 功能词优化 listing 标题
3. **收集 ≥10 条可归属于该 SKU 的订单或咨询信号**
4. **追踪客户提问** — 记录反复出现的异议

### 推广调整
- 4 张图片 + 402 字描述 → 基线资产，不做打折促销
- 明确标注信用卡分期（最高 8x）以匹配巴西消费者支付偏好
- 利用 fixture 中的准时配送记录作为信任信号
- 14 天内不投付费广告，聚焦有机 listing 质量

### 数据局限
- 所有证据来自 **Olist 公开基准数据集**，非真实商户后台数据
- **0 笔可归因订单**：fixture 中无任何 order_item 指向该 utilidades_domesticas 产品 ID
- 产品描述仅知长度（402 字符），无实际描述文本
- 品牌、材质、颜色、功能、具体价格均不可用
- 私密指标（GMV、CTR、CVR、ROI、广告花费、退款率、复购率）均不可用

### 产出的 10 个工件
- `launch-war-room.html` — 作战指挥室全景页
- `evidence-ledger.json` — 证据台账（5 条 EVID 条目）
- `competitor-table.csv` — 竞品对比表
- `positioning-brief.md` — 定位简报
- `listing-pack.md` — 产品上架文案包
- `content-pack.md` — 内容资产包
- `launch-calendar.csv` — 14 天启动日历
- `launch-state.json` — 启动状态快照
- `promotion-replan.md` — 推广调整方案
- `knowledge-deltas.json` — 知识增量记录

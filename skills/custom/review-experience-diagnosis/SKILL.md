---
name: review-experience-diagnosis
description: 将评价分数、低分率、评价文本信号与履约指标分开验证，用于商品体验与评价异常诊断，不把文本信号升级为违法或售假结论。
allowed-tools:
  - commerce_dataset_profile
  - commerce_capabilities
  - commerce_list_entities
  - commerce_metric_snapshot
  - commerce_compare_windows
  - commerce_evidence_query
  - spawn_task
  - wait_task
  - follow_up_task
  - cancel_task
  - resume_task
  - ask_clarification
---

# 评价与商品体验诊断

## 目标

判断评价体验是否变化，并区分：

- 可复算的评分/低分率变化；
- 与履约变化同时出现的体验信号；
- 评论文本中需要进一步核查的主题；
- 当前数据无法识别的商品、履约或服务因素。

## 流程

1. 调用 `commerce_capabilities` 检查 `review_experience` 及评论文本可用性。
2. 用 `commerce_compare_windows` 比较：
   - `average_review_score`；
   - `low_rating_rate`；
   - `order_count`；
   - 必要时加入履约指标，检查是否同步变化。
3. 用 `commerce_evidence_query` 追溯评分 Fact 与评论字段。评论文本只用于形成主题信号和待验证假设。
4. 主动寻找反证：
   - 低分率上升但平均分基本稳定；
   - 评分下降但履约指标未变化；
   - 评论缺失率或样本结构变化；
   - 少量极端评论被误当成总体趋势。
5. 数据不足时，明确需要补充的商品属性、退款、客服、批次、库存或曝光数据。

## Tool 轮次与停止条件

优先使用两轮以内的取数计划：

1. 第一轮调用一次 `commerce_compare_windows`，同时请求 `order_count`、
   `average_review_score`、`low_rating_rate` 和 `late_delivery_rate`。如果 Parent 尚未完成
   Capability 检查，可以在同一轮并行调用一次 `commerce_capabilities`；如果 Parent 或 Explore
   已提供能力结果，不得重复检查。
2. 第二轮调用一次 `commerce_evidence_query`。优先把评分 MetricObservation 返回的 Fact ID 合并查询；
   需要评论主题时，用评价实体及评分、标题、正文语义字段做一次有界抽查，然后立即综合。

`commerce_compare_windows` 已返回窗口指标时，不再用 `commerce_metric_snapshot` 重算同一指标。
同一 Dataset、卖家、窗口和参数不重复调用 Tool；评论文本样本达到主题判断所需的最小数量后停止，
不为了搜到更强烈措辞继续翻页。ContextPacket 的 Tool 白名单或 `max_tool_rounds` 更小时，以更小预算为准。

以下情况立即停止取数并返回明确状态：

- `review_experience` 为 unavailable：返回不可用原因和应补充的 `order_reviews` / 评分 / 评论字段；
- 评分指标可算但评论正文不可用：只报告量化变化，不推断评论主题；
- 两窗口样本不足或缺失率显著变化：标记不确定性，不扩大结论；
- 已获得评价变化、履约反证、文本信号和数据限制：直接综合，不继续探索。

## 安全边界

- 可以写“评论中出现疑似非原装、错发、少发等信号”。
- 不可以仅凭评论确认售假、欺诈、违法或平台责任。
- 不把没有曝光、点击、购买分母的数据解释为转化率变化。
- 不把同时发生的履约和评分变化写成已确认因果。

## 推荐输出

- 评价现象与样本；
- 文本主题信号；
- 与履约/商品体验的支持证据；
- 反证与替代解释；
- 数据限制；
- 建议核查或补数动作。

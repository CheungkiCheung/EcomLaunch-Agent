---
name: seller-peer-analysis
description: 使用结果无关的类目、地区、时间和样本规则进行卖家同类对标，避免按结果挑选对照组并避免因果夸大。
allowed-tools:
  - commerce_dataset_profile
  - commerce_capabilities
  - commerce_list_entities
  - commerce_metric_snapshot
  - commerce_peer_comparison
  - commerce_geographic_segments
  - commerce_evidence_query
  - spawn_task
  - wait_task
  - follow_up_task
  - cancel_task
  - resume_task
  - ask_clarification
---

# 卖家同类对标

## 核心原则

对标组必须在看到目标结果之前，按照可解释的业务维度确定。禁止为了制造显著差异，按延迟率、评分或其他结果指标挑选“优秀同行”。

## 标准流程

1. 调用 `commerce_capabilities` 检查 `seller_peer_comparison`，记录缺失的类目、卖家地区、商品或履约字段。
2. 确认目标卖家、分析窗口和纯商品类目；如果用户只说“这个卖家”，从当前上下文或 `commerce_list_entities` 解析。
3. 调用 `commerce_peer_comparison`，明确：
   - `product_category`；
   - `min_orders_per_seller`；
   - 是否匹配卖家地区；
   - 单卖家订单与纯类目订单约束。
4. 检查目标与同行各自的样本量、同行数量、池化分母和差值。
5. 用 `commerce_evidence_query` 抽查目标与同行 MetricObservation 的来源 Fact。
6. 需要解释结构差异时，用 `commerce_geographic_segments` 或 `commerce_metric_snapshot` 做补充，但不能改变既定同行选择规则。

## Tool 轮次与停止条件

使用三轮以内的有界计划，通常两轮即可完成：

1. 如果 Parent 尚未确认能力，第一轮调用一次 `commerce_capabilities`；已有 Capability 结果时跳过。
2. 调用一次 `commerce_peer_comparison` 固定 cohort 规则。用户明确要求地域分布时，可在同一轮并行调用
   一次 `commerce_geographic_segments`，因为二者只共享卖家和窗口，不互相依赖。
3. 将目标与同行 MetricObservation 的 Fact ID 合并到一次 `commerce_evidence_query`，完成来源抽查后立即综合。

`commerce_peer_comparison` 已返回目标、同行、样本量和差值时，不再用 `commerce_metric_snapshot` 重算同一指标。
同一 Dataset、卖家、窗口、类目和 cohort 参数不重复调用；不得通过换类目、降低最小订单数、取消地区匹配
或放宽纯类目/单卖家约束来追求更显著结果。ContextPacket 的 Tool 白名单或 `max_tool_rounds` 更小时，
以更小预算为准。

获得 cohort 规则、目标与同行差异、地域结构、Evidence 抽查和不可观测因素后必须停止。只有 Tool 明确返回
unavailable、关键 Fact 未找到或既有结果互相冲突时，才允许使用剩余轮次做一次针对性修复；禁止开放式继续探索。

如果 MetricObservation 的 `source_fact_ids_truncated=true`，只表示当前响应的 Fact ID 预览被截断；Fact
仍可通过 `commerce_evidence_query` 分页查询。不得把预览截断写成“全部订单级事实无法枚举”或“证据无法追溯”。

## 失败与停止条件

- 目标卖家不满足最小样本：返回 unavailable；
- 没有符合预先规则的同行：返回 unavailable；
- 类目或卖家归属无法可靠连接：返回 unknown；
- 不降低最小样本、不取消纯类目/单卖家约束来强行产生结论。

## 结论纪律

- 对标差异是诊断信号，不是行动效果或因果证明。
- 必须展示 cohort 规则、目标样本、同行样本、同行数量和计算口径。
- 说明可能的不可观测差异，例如商品结构、仓配合同、促销峰值和库存状态。
- 未执行统计检验时，不写“显著高于/显著差异”；地域 Tool 只返回订单数时，不自行计算占比。
- 少量 Evidence 抽查不能升级为“无任何缺失或异常”，也不能代表全量数据质量。
- 只报告 Tool 直接返回的目标/池化同行 gap，不对“最高同行”等个体结果二次计算新 gap。

## 推荐输出

- 对标口径；
- 目标与同行差异；
- 证据引用；
- 稳健性与反证；
- 不可观测因素；
- 下一步调查建议。

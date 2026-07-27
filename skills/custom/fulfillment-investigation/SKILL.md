---
name: fulfillment-investigation
description: 用确定性 Commerce Tool 调查电商履约异常，区分卖家处理与承运运输阶段，同时寻找支持证据、反证和数据限制。
allowed-tools:
  - commerce_dataset_profile
  - commerce_capabilities
  - commerce_list_entities
  - commerce_seller_coverage
  - commerce_metric_snapshot
  - commerce_compare_windows
  - commerce_geographic_segments
  - commerce_evidence_query
  - spawn_task
  - wait_task
  - follow_up_task
  - cancel_task
  - resume_task
  - ask_clarification
---

# 履约异常调查

## 目标

回答三个严格分离的问题：

1. 履约表现是否真的发生变化；
2. 变化更集中在卖家处理阶段还是承运运输阶段；
3. 现有数据能支持什么、不能支持什么。

本 Skill 只指导调查流程。所有指标、窗口、分段和样本量必须来自确定性 Commerce Tool，不能由模型心算。

## 适用条件

- 用户询问延迟发货、晚到、配送时长、处理时长或履约恶化；
- Dataset 至少能识别订单、卖家、购买时间以及部分履约时间字段；
- 如果能力为 `partial`，仍可回答可观测部分，但必须明确缺失角度。

## 调查流程

1. 调用 `commerce_capabilities`，确认 `fulfillment_diagnosis` 状态与缺失字段。
2. 如果 Parent 已明确给出卖家，调用一次 `commerce_seller_coverage` 获取全量关联订单的精确最早/最晚时间、订单量和关键履约字段覆盖；不得使用 evidence_query 抽样推断最早/最晚订单时间。只有卖家不明确时才调用一次 `commerce_list_entities` 查候选。
3. 用 `commerce_compare_windows` 比较：
   - `order_count`，用于解释样本变化；
   - `late_delivery_rate`；
   - `handling_time_hours`；
   - `transit_time_hours`；
   默认通过 `metric_names` 只请求以上四项，避免把评价等无关指标装入 ContextPacket；只有用户明确要求
   总履约时长且输出预算允许时，才追加 `delivery_duration_hours`。
   如果用户只说“最近”而没有给出窗口，原样使用 `commerce_seller_coverage.default_recent_windows` 返回的两个相邻等长半开窗口；不得要求用户手动提供日期，不得由模型自行移动边界。最终答案必须说明这是系统采用的默认近期窗口，而不是用户指定窗口。
4. 把多个关键 MetricObservation 的 `source_fact_ids` 合并到一次 `commerce_evidence_query`，抽查来源字段与记录定位；不要逐条查询。
5. 只有用户明确要求地域定位时，才用 `commerce_geographic_segments` 检查变化是否集中于局部区域；普通“最近履约怎么了”在核心窗口指标和 Evidence 已足够时直接进入 Verifier。地域分析可以作为最终回答中的候选下一步，但不能自动成为本轮前置任务；地域集中也不能自动归因给承运商。
6. 同时寻找反证：
   - 延迟率上升但 handling time 没上升；
   - transit time 上升但样本极少；
   - 总时长变化来自订单结构或时间覆盖变化；
   - 关键窗口存在大量 unknown。

### 时间窗口合同

`commerce_compare_windows` 的所有窗口固定使用半开区间 `[start, end)`：开始时刻包含在窗口内，结束时刻是排他边界。
相邻窗口必须保持 `baseline_end == current_start`，它们不会重叠；不得减一天或加一天。必须原样传递 Parent / ContextPacket 中给出的 ISO-8601 边界；不得改成当天 `23:59:59`，也不得根据“含两端”等自然语言自行移动 date-only 结束边界。遇到冲突描述时，以 Tool 的半开区间合同为准，并在最终结果中报告该限制，而不是重算不同窗口。

默认 Tool 预算：Capability/Coverage 合计不超过 2 次，窗口比较 1 次，Evidence 抽查 1 次，
可选地域分段 1 次。同一个 Dataset/窗口/参数不重复调用；证据足够后立即停止。

优先使用两轮以内的取数计划：第一轮并行调用互不依赖的 Capability 与窗口比较，第二轮把需要抽查的
Fact ID 合并为一次 Evidence 查询，然后立即综合。`commerce_compare_windows` 已返回窗口指标时，不再用
`commerce_metric_snapshot` 重算同一指标；地域分段只有在 Parent 明确要求地域定位时才替代第二轮抽查，
不能作为额外的“顺便分析”。ContextPacket 的 Tool 白名单或 `max_tool_rounds` 更小时，以更小预算为准。

使用 `commerce_dataset_profile` 时，默认显式传 `include_column_details=false` 和
`include_semantic_mappings=false`。只有字段映射确实冲突且仍有预算时才请求明细，禁止为了“更完整”加载全量 Profile。

## 自然问题默认行为

- “最近履约怎么了”“订单是不是变慢了”“帮我看配送异常”等表达都直接视为履约调查意图，不要求用户说出覆盖、窗口、指标、核验或重算。
- Dataset 只有一个卖家时自动选择该卖家；有多个卖家且没有唯一异常对象时，先返回候选或只问一个会改变结论的澄清问题。
- 用户未指定窗口时先取全量 Coverage，再使用 Tool 给出的 `default_recent_windows`。
- 自然复杂问题仍必须产生真实 Durable Task 和 fresh Verifier；不得在 Parent 中完成全部计算后以文字声称已经核验。
- `commerce_list_entities` 的 `external_key` 是业务 Tool 首选的 `seller_id`；内部 `id` 只用于血缘。两种引用都由确定性 Tool 归一化，不为 ID 形式重跑任务。
- Analyst 已完成核心窗口比较时，Parent 不自动执行其 `recommended_next_tasks`，而是先创建 Verifier；用户未要求的可选地域、品类和其他延伸角度留在最终回答“下一步”。
- 相同 Profile、目标和 Tool scope 的失败 Task 不得再次 `spawn_task`；Tool 未授权或能力不可用时返回限制，不通过重复派工碰运气。

## 结论纪律

- 可以写“与……一致”“主要变化集中在……指标”“值得优先核查……”。
- 不可以仅凭相关变化写“根因是”“导致了”“已经证实”。
- handling time 未上升只能作为反证之一，不能写成“排除了卖家处理流程/卖家自身原因”。
- Evidence 抽查只能说明被抽查记录，不得从少量样本升级为“计算可靠”“不存在缺失或错误”。
- `source_fact_ids_truncated=true` 只表示响应中的 ID 预览被截断，Fact 仍可分页查询；不得写成底层证据无法追溯。
- 不把样本量直接写成“足以排除噪声”，也不臆测 Dataset 中未观测的节日、承运商或促销事件。
- `unknown` 不是零；能力缺失时给出具体补数建议。
- 每条核心结论至少引用一个 MetricObservation ID；关键阶段判断同时给出支持证据与反证/替代解释。

## 推荐输出

- 现象：窗口、指标、样本量与变化；
- 阶段定位：卖家处理 / 承运运输 / 无法区分；
- 支持证据：Metric/Fact 引用；
- 反证与替代解释；
- 数据限制；
- 下一步最小行动与需要补充的数据。

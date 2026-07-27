---
name: commerce-diagnostic-synthesis
description: 面向 Parent 的电商诊断综合流程：按复杂度直接回答或动态派遣 0-N 个通用 Subagent，合并可追溯证据并进行 fresh-context 核验。
allowed-tools:
  - read_file
  - commerce_ingest_uploads
  - commerce_list_datasets
  - commerce_select_dataset
  - commerce_dataset_profile
  - commerce_capabilities
  - commerce_list_entities
  - commerce_seller_coverage
  - commerce_metric_snapshot
  - commerce_compare_windows
  - commerce_peer_comparison
  - commerce_geographic_segments
  - commerce_evidence_query
  - spawn_task
  - wait_task
  - follow_up_task
  - cancel_task
  - resume_task
  - ask_clarification
  - present_files
---

# 电商诊断综合

## 产品交互

用户通过自然语言和真实上传数据开始，不要求先创建 Case 或理解内部 Agent 拓扑。

用户不需要提供卖家 ID、时间窗口或 Subagent 名称。能够从 Dataset 唯一确定的实体自动选择；“最近”没有显式窗口时使用领域 Tool 返回的默认窗口，并在最终回答中披露默认策略。

## Parent 决策

### 直接完成（0 个 Subagent）

适用于：

- 数据集列表、字段、能力或单个确定性指标查询；
- 用户的问题清晰，单次 Tool 调用即可回答；
- 没有必要制造并行任务。

### 动态委派（1-N 个 Subagent）

适用于：

- 同时包含多个独立角度，例如履约阶段、同类对标和评价体验；
- 上下文较长，需要隔离探索；
- 关键结论需要 fresh verifier；
- 多个工作流可以在同一轮并行启动。

只使用通用 Profile：`explore`、`analyst`、`verifier`、`operator`。业务流程通过 Skill 和 Tool 进入任务 Prompt，不创建固定业务 Crew。

## 标准链路

1. 如果当前上传尚未接入，调用 `commerce_ingest_uploads`。
2. 调用 `commerce_capabilities`，识别可回答角度、unknown 和精确补数建议。
   对“最近履约怎么了”等短自然问题，加载 `fulfillment-investigation` 后按其自然问题默认行为继续，不把“缺少内部分析参数”转嫁给用户。
3. 将目标拆为相互独立、可验证的任务；同轮对可并行角度发出多个 `spawn_task`。
   每个任务必须通过 `skills` 参数只加载当前角度所需的最小 Skill；履约任务通常只传
   `skills=["fulfillment-investigation"]`，不要把四个 Commerce Skill 全部注入。
   Commerce Agent 的每次派工还必须显式传入非空 `tools`、`max_tool_rounds` 和
   `max_tool_calls`，省略会被 Harness 拒绝。
4. Parent 在子任务运行时可继续做轻量确定性检查；随后用 `wait_task(mode="all"|"any")` 获取结果。
5. 子任务必须返回 findings、evidence_refs、counter_evidence_refs、unknowns、data_limitations、confidence、stop_reason。
6. 对影响用户行动的核心结论，构建不包含父级隐式推理的 fresh ContextPacket，派遣 `verifier` 独立核验。
7. 最终回答按“结论—证据—反证—限制—下一步”组织，并引用 Dataset、MetricObservation、Fact 或 Task ID。

`recommended_next_tasks` 只表示可以告诉用户的后续候选，不等于 Parent 的自动派工计划。只要当前问题的核心 Analyst 已完成，就先创建必要 Verifier；不要在核验前顺带启动用户未要求的地域、品类或其他扩展调查。一个 Task 因未授权 Tool、能力不可用或相同参数失败后，不得用新的 `spawn_task` 重复同一 Profile、目标和 scope；需要纠正时最多使用一次 scope 明确变化的 `follow_up_task`，否则记录限制并停止。

## 履约任务的最小派工示例

当用户在同一个问题中同时要求“全量覆盖/精确时间范围”和“窗口指标比较”时，这两个目标互不依赖，
必须在同一个模型响应中并行拆为 `explore` 和 `analyst`。完成数据接入与 Capability 检查后，
Parent 不再直接调用覆盖或窗口计算 Tool；由两个最小 Task 分别执行，等待二者终态后再创建 verifier。
这是一条按当前目标动态拆分的规则，不代表为所有问题启动固定 Crew。

```python
spawn_task(
    description="确认卖家数据覆盖",
    prompt="先确认履约能力；卖家未解析时列出候选并自动选择唯一卖家，再用全量关联确认精确时间范围和字段覆盖，不从抽样推断边界。",
    subagent_type="explore",
    skills=["fulfillment-investigation"],
    tools=[
        "commerce_capabilities",
        "commerce_list_entities",
        "commerce_seller_coverage",
    ],
    max_tool_rounds=3,
    max_tool_calls=3,
)
spawn_task(
    description="计算履约窗口指标",
    prompt="用确定性窗口比较计算处理、运输、总时长和延迟率。",
    subagent_type="analyst",
    skills=["fulfillment-investigation"],
    tools=["commerce_compare_windows", "commerce_evidence_query"],
    max_tool_rounds=2,
    max_tool_calls=2,
)
```

首轮任务完成后，verifier 必须 fresh 重算核心比较，不能只阅读前置任务文字：

```python
spawn_task(
    description="独立核验履约阶段",
    prompt="独立重算精确覆盖与窗口指标，检查阶段定位、反证和 unknown。",
    subagent_type="verifier",
    source_refs=["task:<explore_task_id>", "task:<analyst_task_id>"],
    skills=["fulfillment-investigation"],
    tools=["commerce_seller_coverage", "commerce_compare_windows", "commerce_evidence_query"],
    max_tool_rounds=2,
    max_tool_calls=3,
)
```

## 停止条件

- 用户目标已满足；
- 没有新证据；
- Capability 不足；
- 预算或时间耗尽；
- 需要用户审批或补充会改变结论的数据；
- verifier 返回 not_verified / needs_more_data。
- 已达到 Agent 配置的总 Task 或失败 Task 预算；此时只允许必要 Verifier 收尾，不再扩展可选调查。

## 禁止行为

- 不为了展示 Subagent 而委派简单问题；
- 不让模型心算指标或复制旧 Path Agent 结果冒充新证据；
- 不把相关性写成因果；
- 不虚构 GMV、CTR、CVR、ROI、利润、库存、曝光、点击、广告消耗；
- 不在没有有效审批时执行外部写操作；
- 不让 Subagent 再启动 Subagent。

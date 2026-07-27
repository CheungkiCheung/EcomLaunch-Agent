# Commerce Agent Chat-first / Subagent Harness 重定向计划

> 状态：Phase 0–3 动态主链、四条 Gold Case parity、上下文传播与成本/质量门禁已完成；当前进入 Phase 4 Chat-first 产品主入口。旧主链暂不删除，继续作为迁移对照和回退依据。
> 日期：2026-07-24
> 当前分支：`feature/commerce-case-agent`
> 上游基础：DeerFlow
> 目标模型：真实 DeepSeek V4；所有 Agent 验收请求必须 fresh、身份可确认、retry=0
> 决策记录：`docs/adr/0006-commerce-agent-is-chat-first-with-dynamic-subagents.md`
> 历史计划：`docs/plans/2026-07-18-commerce-case-agent-complete-design-and-implementation-plan.md`

## 1. 这次重定向解决什么问题

当前实现已经完成大量可靠的 Commerce 数据、Case、Evidence、Action、Eval 和 Skill Evolution 基础，但默认产品入口和 Agent 拓扑存在两个问题：

1. Case-first 多页面工作台要求用户先理解 Dataset、Capability、Case、Evidence、Run 和 War Room，真实使用门槛过高；
2. Commerce 主链通过固定 Router / Coordinator / Fan-out 启动有限 Path，更像工作流编排，而不是 Parent Agent 根据当前问题原生、动态地委派 Subagent。

目标不是推翻已经完成的确定性能力，而是重新确定产品主入口和运行时主线：

```text
用户看到：
Codex / DeerFlow 风格的中文持续对话

Agent 内部：
Parent Agent
→ 直接回答 / 调用确定性 Tool / 动态派遣 0–N Subagent
→ 汇总结构化 Evidence 与 Artifact
→ 必要时使用 fresh-context Verifier
→ 在 Chat 中请求 Action Approval
→ 持久化任务、Case、Trace 和 Follow-up

按需观察：
用户点击“查看协作空间”
→ 进入由真实 Harness Event 驱动的游戏化 Subagent 工作场景
```

## 2. 最终产品定位

### 2.1 一句话定位

> 一个面向电商经营人员的 Chat-first 数据诊断与行动 Agent：用户上传真实经营数据并自然提问，Parent Agent 根据任务动态调用工具和 Subagent，给出可追溯结论，并在审批后执行或生成行动。

### 2.2 用户真正要解决的问题

```text
哪里出了问题？
为什么发生？
当前数据最多能判断到什么程度？
下一步最值得做什么？
做完以后有没有改善？
```

### 2.3 默认用户入口

用户不需要先创建 Case 或进入 Dashboard。默认路径是：

```text
新建对话
→ 拖入 CSV / Excel / JSON / ZIP，或选择已有数据源
→ 用自然语言提出经营问题
→ Agent 检查数据能力并开始回答
→ 简单问题直接回答
→ 复杂问题动态派遣 Subagent
→ 用户持续追问
```

### 2.4 Case 的新定位

`Case` 不删除，但从默认交互对象降为内部持久化业务对象：

- 简单问答可以只存在于 Thread / Run；
- 需要多轮调查、Evidence、Action、Follow-up 或恢复的任务升级为 Case；
- 左侧对用户显示“任务”或对话标题，不要求用户理解 Case 数据模型；
- 现有 Case、Evidence、Hypothesis、Action 和 Follow-up 合同继续作为业务权威状态。

## 3. 核心技术叙事

项目面试主线收敛为三个重点：

1. **Parent–Subagent Harness**：动态委派、隔离上下文、并行/后台任务、持久化生命周期、权限、恢复和可观测性；
2. **受治理 Skill Evolution**：失败 Trace 生成 Candidate，经 Regression、Holdout、Shadow、人审、晋级和回滚；
3. **真实模型工程**：使用真实 DeepSeek V4 完成 Prompt、Skill、Context、Router、Profile 和预算选型，记录可复现证据。

Loop Engineering 不作为独立产品或简历标题。Goal、Budget、Stop Condition、Compaction、Checkpoint、Timeout、Cancel 和 Resume 归入 Harness 内部机制。

## 4. 目标架构

```text
Product Plane
├── Chat-first Workspace
│   ├── Thread / Task History
│   ├── File Upload / Data Selection
│   ├── Natural Answer
│   ├── Compact Subtask Status
│   ├── Evidence Citation
│   ├── Artifact Output
│   └── Inline Action Approval
└── Optional Collaboration Space
    └── Game-like Subagent Scene driven by real events

Parent–Subagent Harness
├── Parent Agent
├── Native Task Delegation
├── Durable Subagent Task Registry
├── Context Packet Builder
├── Scheduler / Concurrency / Budget
├── Task Lifecycle
│   ├── spawn
│   ├── wait
│   ├── follow-up
│   ├── cancel
│   ├── resume
│   ├── retry
│   └── reassign
├── Tool Permission / Approval
├── Checkpoint / Recovery
├── Event / Trace / Token / Model Identity
└── Structured Result / Evidence Contract

Commerce Capability Plane
├── Data Intake / Profile / Semantic Mapping
├── Capability / Metric / Window / Anomaly
├── Evidence / Hypothesis / Case
├── Action / Approval / Connector / Rollback
├── Follow-up
├── Commerce Tools
└── Commerce Skills

Improvement Plane
├── Gold Cases
├── Experiment / Eval / Pareto
├── Skill Candidate
├── Regression / Holdout
├── Shadow
├── Human Review
└── Promotion / Rollback
```

## 5. Parent 与 Subagent 设计

### 5.1 Parent Agent

用户始终与一个 Parent Agent 对话。Parent 负责：

- 理解当前目标和追问；
- 判断是否可以直接回答；
- 检查当前数据、Capability、Evidence 和历史任务；
- 调用确定性 Tool；
- 动态派遣 0–N Subagent；
- 控制任务预算、依赖、并行度和停止条件；
- 汇总结构化结果；
- 判断是否需要 fresh-context Verification；
- 在 Chat 中请求 Action Approval；
- 将复杂任务升级为持久化 Case；
- 在新数据到来后继续 Follow-up。

Parent 不直接计算确定性指标，不伪造数据，不绕过 Action Policy。

### 5.2 通用 Subagent Profile

首批只保留少量通用工作方式，不设置固定业务 Crew：

| Profile | 职责 | 默认权限 |
|---|---|---|
| `explore` | 探索文件、字段、数据质量、资料和上下文 | 只读 |
| `analyst` | 计算、解释、提出假设、寻找证据与反证 | 只读分析 |
| `verifier` | 使用 fresh context 独立验证关键结论 | 严格只读 |
| `operator` | 在批准后生成或执行受控行动 | 策略限制的写权限 |

这些 Profile 是可用能力，不是每次固定启动的四 Agent 流程。同一任务可以启动零个、一个或多个同类实例。

### 5.3 Commerce Skill

业务专业性进入 Skill，而不是写死在 Subagent 类型中。首批已验证能力迁移为：

- `fulfillment-investigation`
- `seller-peer-analysis`
- `review-experience-diagnosis`
- `commerce-diagnostic-synthesis`

后续可以增加退款、库存、流量漏斗、广告、定价等 Skill，而不修改 Parent–Subagent Harness。

### 5.4 Commerce Tool

确定性能力以 Tool 暴露：

- 数据集和 Schema 查询；
- 字段映射与 Capability；
- Metric / Window / Segment / Anomaly；
- Evidence 写入；
- Artifact 生成；
- Action Proposal；
- Approval 查询；
- Connector 执行与 Read-back；
- Follow-up 比较。

Subagent 返回结构化结果，不只返回自然语言：

```text
findings
evidence_refs
counter_evidence_refs
unknowns
data_limitations
recommended_next_tasks
artifacts
confidence
stop_reason
```

## 6. Harness 个人增量边界

### 6.1 明确复用 DeerFlow

- Thread / Message / Streaming；
- LangGraph 底层执行；
- 原生 `task` Tool 和 SubagentExecutor 基础；
- Model / Tool / Skill 注册；
- Sandbox / MCP；
- 基础 Token Tracking；
- DeerFlow Chat 前端；
- 现有 Subtask Card 与 Artifact 基础。

### 6.2 必须由本项目完成

- 持久化 `SubagentTask` 和 Parent–Child lineage；
- 可恢复的任务生命周期与状态机；
- `spawn / wait / follow-up / cancel / resume / retry / reassign` 语义；
- 真正允许 Parent 启动任务后继续行动的异步合同；
- 版本化 ContextPacket 和最小上下文隔离；
- 并发、依赖、预算、超时和停止条件；
- Tool Permission、Operator Capability 和 Action Approval 连接；
- 结构化 Event 和 Result 合同；
- Token、Latency、Provider Request ID、模型身份和版本聚合；
- 服务重启、Worker 切换和未知外部结果恢复；
- Chat、任务卡片和游戏场景共享同一真实事件源；
- Trace 到 Eval / Skill Candidate 的连接。

## 7. 前端信息架构

### 7.1 默认只保留 Chat 主界面

```text
左侧
├── 新建任务
└── 最近对话 / 历史任务

中央
├── 用户消息
├── Parent 自然回答
├── 折叠的 Subagent 状态
├── Evidence 引用
├── Artifact
├── Approval Card
└── 底部 Composer / Upload
```

不把 Dataset、Capability、Case、Evidence、Action、Run、Skill 和 Eval 全部做成常驻一级导航。

### 7.2 渐进展开

- 默认：只看自然回答；
- 展开任务摘要：看 Subagent 数量、状态和结果；
- 点击单个任务：看 Context、Skill、Tool、Evidence 和 Stop Reason；
- 高级运行详情：看 Token、Latency、模型身份、Request ID 和版本；
- Skill Candidate / Eval 只在开发者入口或候选通知中出现。

### 7.3 游戏化协作空间

Chat 中提供轻量入口：

```text
3 个子智能体正在协作  [查看协作空间]
```

点击后，中央区域从 Chat 切换为协作空间；关闭后回到同一对话。协作空间不作为第三常驻栏，也不使用固定 War Room 泳道。

视觉原则：

- 原创游戏小人，不使用鹿或复制 Marvis 角色；
- 推荐明亮、克制的 2.5D 等距微缩工作室；
- 角色和工位数量由真实任务动态产生；
- 人物动作严格映射真实 Harness Event；
- 没有任务时不播放假忙碌；
- 点击人物展开真实任务详情；
- 场景资产在状态合同稳定后使用图像生成制作；
- 前端优先复用现有 PixiJS / Canvas 经验，避免引入重型 3D 引擎。

## 8. 现有成果处理

### 8.1 直接保留并接入新主线

- Data Intake / Profiler / Semantic Mapping；
- Capability / Metric / Window / Anomaly；
- Case / Evidence / Hypothesis / Run / Checkpoint / Event；
- Lease / Fencing / Resume / Reconciliation；
- Action / Approval / Connector / Read-back / Rollback；
- Follow-up；
- Gold Cases；
- Experiment / Eval / Skill Candidate / Shadow / Active Pointer / Rollback；
- DeepSeek V4 Preflight、Model Lifecycle 和审计证据。

### 8.2 重构后复用

- `FulfillmentPathAgent`、`SellerPeerPathAgent`、`ReviewExperiencePathAgent`：转换为 Skill、Tool 和 Gold Case 行为基准；
- Commerce Lead：转换为 Chat Parent 能力和持久化业务桥接；
- Fresh Verification：保留独立上下文合同，迁移到原生动态 Verifier；
- Evidence Barrier：保留为关键结论提交门禁，不再要求固定 Path fan-out；
- 已完成 Commerce 页面：作为 Chat 内 Drawer、详情页或高级开发者页面的素材和 View Model 来源。

### 8.3 停止作为默认主线

- Case-first 默认产品入口；
- 固定 0–3 Path Router / Coordinator / Fan-out 主链；
- 固定泳道 War Room；
- 大量常驻 Commerce Dashboard 导航；
- 为展示多 Agent 而播放的前端角色活动。

这些实现暂不删除。在新主线通过等价或更高 Release Gate 前，只标记为历史实现或兼容路径。

## 9. 实施阶段

所有功能改造默认采用 RED → GREEN → REFACTOR → VERIFY。

### Phase 0：方向、边界与基线

目标：让项目指令、ADR、计划和 README 不再要求继续 Case-first / 固定 War Room。

任务：

- 更新项目与前端 `AGENTS.md`；
- 新增架构 ADR；
- 将旧完整计划标记为历史实现计划；
- 在 README 区分“当前实现”与“目标主线”；
- 冻结当前回归结果和真实 DeepSeek V4 证据；
- 列出固定 Path / 页面迁移清单；
- 不删除用户现有代码和资产。

完成门禁：

- 文档无互相冲突的默认产品定义；
- `git diff --check` 通过；
- 没有功能代码修改。

### Phase 1：Durable Subagent Harness 合同（已完成，2026-07-24）

目标：先建立与业务无关的持久化任务和事件合同。

RED：

- SubagentTask 状态转换；
- Parent–Child lineage；
- 并发完成、取消、超时竞态；
- 服务重启恢复；
- ContextPacket 版本和权限边界；
- 事件乱序、重复和幂等；
- Token / Request ID 聚合；
- 失败路径和未知外部结果。

GREEN：

- 通用 Task Registry / Repository；
- 版本化状态机；
- Checkpoint / Lease / Fencing 接口；
- 结构化 Task Event；
- DeerFlow Executor Adapter。

完成门禁：

- 确定性单元、并发、持久化和 fault-injection 测试通过；
- Harness 不导入 `app.commerce`；
- 进程重启后能够查询并恢复非终态任务。

### Phase 2：Native Parent–Subagent Lifecycle（已完成，2026-07-26）

目标：让 Parent 真正通过 DeerFlow 原生任务能力动态委派，不再绕过 `task` Tool 走固定 Fan-out。

任务：

- 扩展任务操作合同；
- 支持 start / wait-any / wait-all / follow-up / cancel / resume；
- 支持 Parent 启动任务后继续调用工具或启动其他任务；
- 支持依赖、最大并发、时间和 Token 预算；
- 支持通用 `explore / analyst / verifier / operator` Profile；
- 保留禁止递归委派的默认安全策略；
- 将 Parent 和全部子调用纳入模型身份与用量审计。

Agent 门禁：

- 只能使用 fresh DeepSeek V4；
- 验证简单问题不派 Subagent；
- 验证复杂问题动态派 1–N 个任务；
- 验证并行、取消、恢复和失败重规划；
- 所有 Provider Request ID 唯一且实际模型身份为 DeepSeek V4；
- retry=0。

### Phase 3：Commerce Tool / Skill 迁移（动态主链已完成，2026-07-26）

目标：让电商能力成为开放 Chat 入口下的 Tool 和 Skill，而不是固定 Path 拓扑。

任务：

- 将 Capability、Metric、Evidence、Action 暴露为受控工具；
- 将三条 Path 能力迁移为可加载 Skill；
- Parent 根据用户问题、Schema 和 Capability 决定任务；
- Verifier 只接收 fresh ContextPacket；
- 复杂任务自动升级为 Case，简单问答不强制创建；
- 保持 Evidence、未知项和禁止结论门禁；
- 保持 Action Approval / Read-back / Rollback。

完成门禁：

- 现有四 Gold Case 在新动态主链上达到或超过原门禁；
- 至少增加开放式上传问答 Case，证明入口不是固定三条 Path；
- 原固定主链与新主链结果做 parity / 差异分析；
- 未通过前不删除旧主链。

实际完成记录：

- `(user_id, thread_id) → WorkspaceId → active DatasetId`；
- 11 个确定性 Commerce Tool 和 4 个 Commerce Skill；
- Parent 动态选择最小 Skill、Tool 白名单、`max_tool_rounds` 和 `max_tool_calls`；
- Verifier 强制 `task:<task_id>` source snapshot；
- Subagent 显式传播 `user_id`，修复跨背景执行边界的数据隔离；
- DeepSeek streaming Provider Request ID 与 Gateway checkpointer thread identity 修复；
- Tool Round / Call 双预算中间件同时限制循环轮次、单轮并行爆发和总调用数；
- `wait_task` 对 unknown ID 提供当前授权 Run 内的有界恢复清单，真实跨 Run Task ID 仍 fail closed；
- Verifier 裸 Task ID 只在精确匹配当前 Run 终态 Task 时正规化为 `task:<id>`；
- Tool 输出根据可用 reader 能力自动压缩，Compare 显式使用最小指标包，Evidence Fact ID 只做可分页预览；
- Response Guard 只在所有问题均属于最终回答时允许一次 fresh、无 Tool 改写，修复请求计入 Parent Request/Token 审计并重新执行完整门禁；
- Fulfillment、Review、Capability Ablation、Peer 四条统一 fresh Gate：`4 passed in 253.05s`，每条 15 个唯一请求、retry=0，服务端模型身份均为 `deepseek-v4-flash`；
- 完整调优记录见 `docs/progress/2026-07-26-commerce-dynamic-tool-skill-chain.md` 和 `docs/progress/2026-07-26-commerce-dynamic-release-hardening.md`。

迁移保留策略：四条新动态主链 parity 已完成；旧固定 Path 仍保留到 Chat-first、浏览器 E2E 和最终演示门禁完成，便于差异分析和回退。

### Phase 4：Chat-first 产品主入口

目标：复用 DeerFlow Chat，形成中文、持续、自然的电商 Agent 使用体验。

任务：

- Commerce Parent 接入 DeerFlow Thread；
- Composer 支持多文件上传和数据源选择；
- Parent 使用中文自然回答；
- Subagent 只显示紧凑折叠状态；
- Evidence 使用引用与详情弹层；
- Artifact 在对话中呈现；
- Action Approval 内嵌在聊天；
- 左侧只保留新建任务和历史任务；
- 现有 Commerce 页面降级为按需详情或高级入口；
- 固定 War Room 不再进入默认导航。

视觉门禁：

- 先生成并确认一张 Chat 主界面高保真视觉稿；
- 单元、TypeScript、Lint、构建通过；
- 真实浏览器桌面和移动 QA；
- Mock E2E 只证明 UI 机械行为；
- Agent E2E 必须连接真实后端和 fresh DeepSeek V4。

### Phase 5：游戏化 Subagent 协作空间

目标：将 Harness 真实任务可视化为可选游戏场景，不影响默认 Chat 的简洁性。

顺序：

1. 冻结 Task Event → Visual State 映射；
2. 使用图像生成制作三种原创视觉方向；
3. 用户选择视觉母版；
4. 生成完整场景、角色设定和透明资产；
5. 整理 Sprite Sheet / Animation Contract；
6. 实现 PixiJS / Canvas 场景和键盘/鼠标交互；
7. 接入真实 Task Event；
8. 点击人物查看真实 Context / Skill / Tool / Evidence / Telemetry；
9. 完成 reduced-motion 和移动降级列表。

严禁：

- 固定六 Agent Crew；
- 无真实事件的忙碌动画；
- 从聊天文本猜状态；
- 复制 Marvis 角色或品牌资产；
- 让游戏场景取代自然回答。

完成门禁：

- 每个可见动作能追溯到 Task Event；
- queued、running、waiting、approval、blocked、completed、failed、cancelled、timed_out 均有真实状态测试；
- 刷新或重连后场景与持久化任务一致；
- 真实浏览器视觉和交互 QA 通过。

### Phase 6：Skill Evolution 与调优闭环

目标：用真实运行 Trace 改进 Skill，并保留严格治理。

任务：

- 将低分、失败、补数和重复未知模式送入 Failure Taxonomy；
- 生成 Skill Candidate，不直接修改 Active Skill；
- 版本化 Prompt / Skill / Context / Router / Profile / Budget；
- 建立 Control / Candidate 实验；
- Regression、Holdout、Shadow 和 Human Review；
- Promotion 和 Rollback；
- Chat 中只显示轻量候选通知；
- 高级 Eval 页面复用现有 Skills & Evals 能力。

真实模型门禁：

- 所有 Semantic、Agent、Experiment 和 Shadow 测试使用 fresh DeepSeek V4；
- 模型身份、额度或鉴权不可确认时立即停止；
- 不用 Mock、Replay、缓存或其他模型作为 PASS 证据；
- 记录 Token、Latency、Request ID、Stop Reason 和版本信息。

### Phase 7：硬化、演示和求职材料

目标：证明系统真实可用，并把个人增量讲清楚。

任务：

- 真实 Gateway + 数据上传 + Parent + Subagent + Approval 浏览器 E2E；
- PostgreSQL 集成和重启恢复；
- 失败、超时、取消、恢复、权限和并发压力测试；
- 至少一条真实可逆 Connector 路径；
- 中文 Demo 数据和脚本；
- Chat 与协作空间录屏；
- 上游 DeerFlow / 个人新增边界图；
- 架构选型、Prompt/Skill/Context 调优报告；
- 简历项目描述和高频面试问答。

最终 Release Gate：

- 用户可上传真实数据并持续对话；
- Parent 能根据任务动态派遣 0–N Subagent；
- 所有结论可追溯到 Evidence 或明确标记 unknown；
- Action 受 Policy 和 Approval 约束；
- 服务重启后任务与场景可恢复；
- Chat 和协作空间共享真实事件；
- Skill Candidate 有完整治理链；
- Agent 验收使用 fresh DeepSeek V4；
- 真实浏览器 E2E 和最终录屏完成。

## 10. 验证矩阵

| 层次 | 是否调用模型 | 验证要求 |
|---|---:|---|
| Domain / State / Metric / Policy | 否 | 单元、性质、边界、故障注入 |
| Task Registry / Scheduler / Recovery | 否 | 并发、幂等、重启、乱序、取消 |
| View Model / Event Projection | 否 | 纯函数、未知状态、重放一致性 |
| Parent / Subagent / Router / Tool Selection | 是 | fresh DeepSeek V4 |
| Verification / Semantic Eval / Experiment | 是 | fresh DeepSeek V4 |
| UI 机械交互 | 否 | Mock API 可以使用，但不计 Agent Gate |
| Agent 浏览器 E2E | 是 | 真实 Gateway + fresh DeepSeek V4 |
| 游戏场景 | 否/是 | 状态投影确定性；完整 Agent 流程真实模型 |

## 11. 当前优先级

实施顺序不能颠倒：

```text
先 Harness 合同和动态运行时
→ 再 Commerce Skill / Tool 迁移
→ 再 Chat 主入口
→ 再生成并实现游戏协作空间
→ 最后完成 Skill Evolution 集成、硬化和求职材料
```

视觉资产不会先于真实任务状态合同开发。游戏场景是 Harness 的观察层，不是独立的演示系统。

## 12. 需要用户参与的关键节点

除以下节点外持续推进：

1. 三种游戏化协作空间视觉母版选择；
2. 真实外部 Connector 涉及账号、付费或外部写操作；
3. Skill Candidate 的 Human Promotion；
4. 最终 Demo 视觉和简历表述确认；
5. 模型不可用、额度不足或真实身份无法确认。

## 13. 简历目标表述

> 基于 DeerFlow 深度改造 Parent–Subagent Harness，支持动态委派、隔离上下文、异步并行、任务追问/取消/恢复、权限审批与全链路模型遥测；围绕异构电商数据构建 Chat-first 诊断与行动 Agent，并通过真实 DeepSeek V4 Gold Cases 完成 Prompt、Skill、Context、Profile 和预算选型。

> 构建受治理的 Skill Evolution 流程，根据真实运行失败 Trace 生成 Candidate，经 Regression、Holdout、Shadow 和 Human Review 晋级并支持回滚；实现由真实任务事件驱动的游戏化 Subagent 协作空间，使 Harness 生命周期、并行调度和恢复状态可交互检查。

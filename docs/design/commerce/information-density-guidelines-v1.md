# 电商经营诊断前端信息密度约束 v1

## 状态

- 形成日期：2026-07-20。
- 适用于 Commerce Case Agent 的全部正式页面，包括 Master Shell、Case Detail、Data Inbox、Capability Report、Case Queue、Evidence Explorer、Action Center、Agent Run、Skills & Evals、War Room、Follow-up 和 Overview。
- 本文件解决的是默认信息暴露层级，不删除产品能力，也不把 Case-first Workspace 改回纯 Chat 产品。
- 视觉方向继续采用中文、浅色、文档式、Codex-inspired 但完全原创的工作区语言。

## 问题判断

当前 Master Shell 的视觉装饰是克制的，但默认同时展示了导航、案例状态、完整调查记录、证据、子智能体、运行时和输入框，属于“全局高密度”。这种状态适合作品集能力展示，不适合作为经营用户的默认日常界面。

后续页面必须采用“局部高密度 + 渐进披露”：用户在任一时刻只有一个主要阅读或操作目标，其他能力在选择对象、切换视图或进入工程详情后出现。

## 两层产品视图

### 运营默认视图

默认视图只回答四个连续问题：

```text
发生了什么？
→ 为什么这样判断？
→ 证据是否足够？
→ 下一步最值得做什么？
```

默认允许展示：

- 一句话问题定义；
- 两到三个最关键指标或事实；
- 当前结论及因果边界；
- 证据充分度和未知项摘要；
- 一个候选行动及其审批或执行状态；
- 一个绑定当前案例的辅助输入入口。

### 工程详情视图

以下内容默认不占据经营主视图，通过“运行详情”或对象级检查入口展示：

- Lead 与 bounded Subagents；
- fan-out / fan-in 路径；
- Goal Loop、Budget 和 Stop Condition；
- Evidence Barrier；
- Fresh-context Verification；
- 模型身份、Provider Request ID、Token 和 Latency；
- Retry、Lease、Checkpoint 和 Resume；
- Run Graph、Case Sequence 修正和原始 Domain Event；
- Eval、Experiment、Shadow、Skill Candidate 和 Skill Evolution；
- Action Policy、审批、执行、回滚与审计字段。

工程信息必须可检查且来自真实状态，但不得为了展示 Agent 技术而默认覆盖经营任务。

## 全局信息预算

以下数值是第一版设计约束；页面确有必要突破时，必须在对应视觉决策记录中说明原因。

| 区域               | 默认预算         |
| ------------------ | ---------------- |
| 页面主要问题       | 1 个             |
| 首屏主要行动       | 不超过 1 个      |
| 首屏次要行动       | 不超过 2 个      |
| 顶部状态标签       | 不超过 2 个      |
| 左侧一级入口       | 不超过 4 个      |
| 中心强边框容器     | 不超过 3 个      |
| 默认时间线节点     | 3–5 个经营里程碑 |
| 桌面空闲输入区高度 | 建议不超过 96px  |
| 移动空闲输入区高度 | 建议不超过 64px  |
| 默认固定右侧面板   | 0 个             |
| 移动端固定底部层   | 最多 1 个        |

## Shell 约束

### 左侧导航

- 默认一级入口只保留“新建诊断”“数据接入”“案例队列”“行动中心”。
- “经营总览”“数据能力”“运行记录”“技能与评测”“作战室”等能力进入可折叠的“更多”或工程入口。
- 桌面侧栏必须支持折叠；折叠时保留图标和当前路由提示，不继续显示完整案例列表。
- 未实现或不可用的页面不长期以大量禁用入口占据默认导航。

### 中心工作区

- 始终只有一条主要叙事：概览、调查记录、证据、运行图或行动详情中的一个。
- 不在概览中重复完整 Timeline、Evidence Explorer、Run Graph 和 Action Center。
- 同一状态不得在 Header、正文、右侧和底部重复三次以上。
- 卡片只用于需要边界、选择或操作的对象；普通说明使用排版和分隔线。

### 右侧检查面板

- 桌面和移动端默认都关闭。
- 用户选择证据、行动、数据源、子智能体或运行节点后才打开。
- 面板内容必须与当前选中对象一致，不使用永久通用 Dashboard。
- 没有选中对象时不使用空面板占据中心宽度。

### 底部输入与运行状态

- Composer 空闲时保持单行或紧凑高度，聚焦后再扩展。
- Runtime 默认只显示一个简短健康状态入口，不同时暴露模型、Retry、Lease 等完整遥测。
- 移动端不固定展示 Runtime Strip；运行信息通过 Drawer 或独立运行视图查看。
- Composer 是 Case-bound 辅助控制面，不替代 Case、Evidence、Action 和 Follow-up。

## Timeline 约束

经营默认时间线只展示用户能理解的业务里程碑，例如：

```text
检测到异常
→ 创建案例
→ 完成证据收集
→ 形成当前结论
→ 生成候选行动
→ 等待审批或验证
→ 跟踪行动结果
```

以下事件下沉到运行详情：

- Path started / completed；
- Agent fan-out / fan-in；
- Lease acquired / released；
- Retry；
- Checkpoint；
- Context repair；
- Evidence Barrier 内部阶段；
- 模型选择和 Provider 遥测；
- Case Sequence 乱序修正。

如果某个工程事件改变了业务状态，例如能力不足导致调查路径跳过，则必须在经营时间线中以业务语言形成一个可理解的摘要，而不是直接显示内部事件代码。

## Case Detail 首屏约束

Case Detail 默认概览只展示：

1. 问题定义；
2. 最小周期对比；
3. 当前结论与因果限制；
4. 证据充分度与未知项摘要；
5. 一个候选行动。

完整调查记录、证据明细、数据血缘、调查路径和运行图通过页签或选择对象进入，不在概览首屏同时展开。

右侧检查面板默认关闭；点击证据、未知项、候选行动或运行状态后，才显示对应对象的详细属性。

## 移动端约束

- 默认只有中心单列内容。
- 左侧导航和右侧检查面板均使用 Drawer。
- Header 保持一行主要标题，面包屑和次要元数据按需隐藏。
- 状态标签最多两枚，更多状态进入详情。
- 空闲 Composer 控制在 56–64px，聚焦或添加文件后扩展。
- 不在 Composer 上方永久叠加 Runtime Strip。
- 固定区域不得遮挡当前行动、错误、审批或关键未知项。

## 面试展示策略

作品集演示不通过默认堆满页面证明技术深度，而采用可解释的演示路径：

```text
运营默认视图看见异常、证据和行动
→ 点击运行详情
→ 展示 bounded Subagents、Loop 和 Evidence Barrier
→ 进入运行图与评测
→ 展示真实模型身份、Fresh Verification 和 Skill Evolution Gate
```

这种分层同时证明产品判断和 Agent 工程能力。

## 视觉与实现门禁

- 每个正式页面继续执行 Image Generation → 用户确认 → React TDD → 浏览器交互 → 截图视觉 QA。
- 视觉稿必须同时给出默认状态和关键展开状态，避免 React 实现时重新把所有信息放回首屏。
- 视觉确认后，测试必须覆盖面板默认关闭、按对象打开、移动 Drawer、Composer 聚焦扩展、运行详情展开和失败状态。
- Agent 行为验收继续遵循真实 DeepSeek V4 红线；纯 UI 机械行为可使用确定性 View Model 和结构化 API Fixture。

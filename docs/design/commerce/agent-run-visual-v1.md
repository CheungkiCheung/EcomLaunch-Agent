# 电商经营诊断 Agent Run 视觉稿 v1

## 状态

- 2026-07-23 使用当前会话内置 Image Generation 生成桌面与移动高保真稿；
- 初始桌面稿标题混用了英文 `Agent`，定点编辑又违反不变量重绘成 Action Execution 页面，两者均不作为实现基准；
- 重新生成的全中文桌面稿与移动稿已保存并人工检查；
- 视觉稿已实现为 `/commerce` 顶层“运行记录”页面，并完成严格合同、RED→GREEN、浏览器交互和截图 QA；实现记录见 `docs/progress/2026-07-23-commerce-agent-run-react.md`。

## 用户任务

Agent Run 页面不是播放“智能体忙碌动画”，而是帮助运营和工程人员回答：

```text
这次运行的目标、类型、状态和停止原因是什么？
系统为什么启动这些路径，哪些路径是真正并行的？
Evidence Barrier 是否在全部路径持久化后才放行？
Lead 综合与 Fresh Verification 是否拥有独立的权威事件？
真实模型身份、Provider Request ID、Token、Latency、Retry 来自哪里？
预算用了多少，最新 Checkpoint 能否恢复？
没有事件或遥测时，哪些字段必须显示“未观察”？
```

## 关键视觉决定

- “运行记录”是顶层工程检查页，位于“更多”下，不挤入 Case 默认概览；
- 桌面使用“Run Queue + 运行图 + 运行详情”三段式工作区；
- 移动端使用 Run 选择卡、纵向运行图和正常文档流详情，不压缩桌面三栏；
- 运行图固定展示语义阶段，但每个阶段是否出现、状态和文案必须由真实 Run / Event / Checkpoint 决定；
- 并行 Path 使用同一 fan-out 组的同级卡片，不把它们画成顺序链；
- Evidence Barrier、Lead 综合、Fresh Verification 和 Stop 是独立阶段；
- 模型、Token、Latency、Retry 和 Checkpoint 只在本工程页面显示，运营默认页不暴露；
- 完成态不显示“重试/重新运行”按钮，避免把幂等、Replan 和故障恢复混成一个动作；
- 无 Chat Composer、头像、脉冲动画、隐藏推理正文或假实时活动。

## 视觉资产

```text
docs/design/commerce/mockups/agent-run-visual-v1-desktop.png
尺寸：1536 × 1024
SHA-256：e82821a2d9ad3b3657d85e3a2c0e235d0051105437f4d40c93cc09272ea4b3e0

docs/design/commerce/mockups/agent-run-visual-v1-mobile.png
尺寸：794 × 1981
SHA-256：53d70fd1f6655d46b837f82deb9722b2fb41274a94dc42bb833696e163c6b5a6
```

## 代表状态与实现纪律

视觉稿用一条三 Path 完成 Run 表达架构能力，但 React 不得写死：

- `CommerceRun` 决定 Run type、status、phase、goal、parent、Action subject、wait/stop reason 和时间；
- `DomainEvent.run_sequence` 决定事件顺序，乱序到达时必须重排并显式提示；
- `path.started / path.completed / path.blocked` 决定 Path 是否出现及其状态；
- 只有属于同一 fan-out 的 Path 事件才能显示为并行组；当前合同缺少显式 fan-out group 时，必须以 Run requested paths + 同一阶段事件的可审计规则投影，不能只按视觉稿断言并行；
- 后端当前没有独立的 `evidence.barrier_released` 领域事件；Evidence Barrier 只有在全部 requested Path 进入终态且真实 `lead.started` / `lead.completed` 事件存在时，才由 View Model 确定性派生完成；页面明确显示该派生边界，不伪造事件；
- `lead.started` / `lead.completed` 和 Verification 完成事件决定主智能体综合与新鲜上下文验证；
- `provider_request_id`、`actual_model_identity`、Token、Latency、Retry 和 stop reason 从真实事件 payload 聚合；缺字段显示“未观察”，不能显示零；
- `GoalLoopCheckpoint` 决定循环、Budget、Evidence、Hypothesis、Tool、Skill、Context SHA-256、Wait 和 Resume 边界；
- 页面不得展示 Chain-of-Thought，只展示结构化阶段、摘要与审计元数据。

## React 实现资产

```text
frontend/src/components/commerce/agent-run.tsx
frontend/src/core/commerce/agent-run-view-model.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/types.ts
frontend/tests/unit/components/commerce/agent-run.test.tsx
frontend/tests/unit/core/commerce/agent-run-view-model.test.ts
frontend/tests/unit/core/commerce/run-api.test.ts
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/implementation/agent-run-react-desktop-v1.png
docs/design/commerce/implementation/agent-run-react-mobile-v1.png
```

实现截图 SHA-256：

```text
045e84e1de9ff0b8a3e9af2debd4f75de6c6378d0cc3b0e2cdc2ccb87227f082  agent-run-react-desktop-v1.png
8fae6b36976e707aef0a8200f0cd8b836d729f119c336513caab1ca8bdaf15ec  agent-run-react-mobile-v1.png
```

## Image Generation Prompt 摘要

使用 `ui-mockup` 分别生成桌面与移动实现稿，要求 Run Queue、七阶段运行图、三 Path fan-out、工程遥测、Budget 和最新 Checkpoint；全部状态为完成态，禁止虚构直播动画。第一次中文定点编辑不满足“不改变其他像素”约束，因此丢弃；随后重新生成全中文“检查一次智能体运行”桌面稿。最终两张选中稿均使用内置 Image Generation，没有切换 CLI 或其他图像模型。

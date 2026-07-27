# ADR 0006：Commerce Agent 采用 Chat-first 与动态 Parent–Subagent Harness

- 状态：Accepted
- 日期：2026-07-24
- 决策者：项目用户与实现者
- 取代范围：默认 Case-first 产品入口、固定 Path Agent 主拓扑、固定 War Room 前端主线
- 保留范围：Commerce Domain、Case、Evidence、Action、Follow-up、Eval、Skill Evolution 和已验证 Gold Case

## 背景

项目已经完成以 Case 为核心的确定性数据、证据、行动和评测基础，也实现了三条固定业务 Path 的 Subagent 包装、Fan-out、Evidence Barrier 和 fresh Verification。

继续沿用该产品结构会产生三个问题：

1. 用户必须先理解 Case Workspace 和多个后台页面，日常提问不自然；
2. 固定业务 Path 使 Subagent 看起来是预先编排的工作流，而不是 Parent 根据任务临时委派；
3. 固定 War Room 信息密度高，容易让角色展示取代问题解决。

DeerFlow 已经具备成熟 Chat、Thread、Streaming、`task` Tool、SubagentExecutor、Skill、Tool 和 Artifact 基础。项目的差异化不应是重新实现聊天或只配置几个 Agent，而应是把原生 Subagent 扩展为可持久化、可恢复、可治理的 Harness，并将 Commerce 能力作为 Tool 和 Skill 接入。

## 决策

### 产品

- 默认入口改为 Codex / DeerFlow 风格的中文持续对话；
- 用户通过上传数据和自然问题开始任务；
- Case 保留为复杂任务的内部持久化对象，不作为所有交互的强制入口；
- Evidence、Artifact、Action Approval 和 Subagent 状态内嵌 Chat，并按需展开；
- 现有 Commerce 页面保留为详情、Drawer 或高级入口，不再全部常驻导航。

### Agent Runtime

- 使用一个 Parent Agent 接收开放式经营问题；
- Parent 通过 DeerFlow 原生任务能力动态派遣 0–N Subagent；
- 通用 Profile 为 `explore`、`analyst`、`verifier` 和 `operator`；
- 履约、卖家对标、评价体验等专业能力进入 Skill 和确定性 Tool；
- Fresh Verification 保留独立上下文；
- 固定 Coordinator / Fan-out 不再作为默认主链；
- Goal、Budget、Stop Condition、Checkpoint、Timeout、Cancel 和 Resume 归入 Harness，不单独包装 Loop Engineering。

### Harness 增量

- 新增 Durable Subagent Task Registry；
- 新增 Parent–Child lineage、版本化 ContextPacket、任务依赖和预算；
- 新增 start、wait、follow-up、cancel、resume、retry 和 reassign 生命周期；
- 新增权限、审批、恢复、事件与模型遥测；
- Chat、任务详情和协作空间读取同一真实 Task Event。

### 可视化

- 默认界面保持 Chat 简洁；
- 用户点击“查看协作空间”后切换到游戏化 Subagent 场景；
- 使用原创游戏小人和微缩工作室，不使用鹿或复制 Marvis 品牌资产；
- 所有角色、动作和屏幕内容由真实 Harness Event 驱动；
- 固定 War Room 终止作为默认产品方向。

### 自进化

- 自进化对象以 Skill Candidate 为主；
- 线上 Agent 不直接修改 Active Skill；
- Candidate 必须通过 Regression、Holdout、Shadow、Human Review 和可回滚晋级；
- 所有 Agent、Eval 和 Shadow 验收继续使用 fresh DeepSeek V4。

## 替代方案

### 继续 Case-first Workspace

拒绝作为默认入口。Case 仍有持久化价值，但不应成为用户开始使用产品的前置概念。

### 继续固定 Path Agent Fan-out

拒绝作为默认运行时。现有 Path 行为保留为 Skill、Tool、Gold Case 和迁移对照。

### 仅配置 DeerFlow Custom Agents

不足以形成个人核心贡献。配置用于 Profile 定义，项目增量集中在持久化生命周期、上下文、权限、恢复、事件、Eval 和 Skill Evolution。

### 重写 LangGraph / Pi / OpenCode Runtime

拒绝。DeerFlow 已提供稳定基础，重写会转移精力并削弱上游与个人增量边界。

### 默认展示游戏化多 Agent 页面

拒绝。游戏场景是按需观察层，Chat 才是默认产品入口。

## 后果

正向：

- 用户体验更自然，简单问题无需完整 Case 流程；
- Subagent 体现为 Parent 动态委派，而不是固定工作流；
- Harness 与 Skill Evolution 成为清晰的求职技术亮点；
- 已有 Commerce 确定性能力和评测成果能够继续复用；
- 游戏化场景提供差异化演示，但不污染默认界面。

成本：

- 需要重新设计 Commerce 主入口和 Agent 主链；
- 需要为 Subagent Task 增加持久化和跨进程恢复；
- 现有多页面前端需要降级重组；
- 游戏资产需要独立视觉与 Sprite 管线；
- 新主线必须重新通过真实 DeepSeek V4 和真实浏览器 E2E。

## 迁移原则

- 新主线达到等价门禁前不删除旧主链；
- 不把旧固定 Path 的通过证据直接当作新动态主链的通过证据；
- 不把 Mock UI E2E 当作 Agent Release Gate；
- 保留历史计划和进度文档，明确其时间和架构背景；
- 每个迁移阶段记录差异、验证、Token、费用和已知限制。

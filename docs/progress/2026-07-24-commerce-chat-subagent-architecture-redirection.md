# Commerce Agent Chat-first / Subagent Harness 架构重定向

> 日期：2026-07-24
> 类型：产品与架构规划
> 功能代码：未修改

## 完成内容

- 将默认产品入口从 Case-first Workspace 收敛为 Chat-first Workspace；
- 将 Case 调整为复杂、长期任务的内部持久化对象；
- 将默认 Agent 主线从固定 Path Router / Coordinator / Fan-out 调整为 Parent 原生动态委派 0–N Subagent；
- 将 Subagent 收敛为 `explore`、`analyst`、`verifier`、`operator` 通用 Profile；
- 将履约、卖家对标、评价体验等专业能力调整为 Commerce Skill、确定性 Tool 和 Gold Case；
- 将 Harness、受治理 Skill Evolution 和真实 DeepSeek V4 选型确认为三条技术主线；
- 将 Loop Engineering 降为 Harness 内部机制；
- 将固定 War Room 替换为按需打开、真实 Task Event 驱动的游戏化 Subagent 协作空间；
- 确认协作空间使用原创游戏小人和微缩场景，不使用鹿，不复制 Marvis 品牌资产；
- 明确现有数据、Evidence、Action、Eval、Skill Evolution 和前端页面的保留与迁移边界。

## 权威文件

- `docs/plans/2026-07-24-commerce-chat-subagent-harness-plan.md`
- `docs/adr/0006-commerce-agent-is-chat-first-with-dynamic-subagents.md`
- `AGENTS.md`
- `backend/AGENTS.md`
- `frontend/AGENTS.md`

旧计划 `docs/plans/2026-07-18-commerce-case-agent-complete-design-and-implementation-plan.md` 保留历史实现范围和验证证据，但不再指导后续默认产品与运行时主线。

## 验证

```text
命令：git diff --check
Exit Code：0
结果：PASS
```

一致性搜索未发现活跃项目指令或 README 继续把 Case-first、固定 0–3 Path 或固定 War Room 声明为目标主线。

本阶段只修改文档和开发约束，因此没有运行单元测试、真实模型测试、前端构建或浏览器测试。Agent 行为尚未按新架构验证；历史 DeepSeek V4 证据只证明旧固定 Path 主链。

## 下一阶段

进入 Phase 1：以 RED → GREEN → REFACTOR → VERIFY 实现与业务无关的 Durable Subagent Task Registry、状态机、Parent–Child lineage、ContextPacket、事件合同和重启恢复。

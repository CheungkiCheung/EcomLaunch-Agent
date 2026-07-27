# Commerce DeerFlow Agent 注册与执行边界

> 日期：2026-07-26  
> 范围：内置 Commerce Agent、Tool Registry 隔离、Gateway 开关、前端纯路由合同  
> 模型调用：无；本阶段只有确定性配置、路由和组装测试

## 完成内容

### 内置 Agent

新增：

- `agents/commerce-agent/config.yaml`；
- `agents/commerce-agent/SOUL.md`。

Agent 固定使用：

- 模型别名 `deepseek-reasoner`，实际模型由全局配置解析为 `deepseek-v4-flash`；
- `commerce` Tool Group；
- `fulfillment-investigation`、`seller-peer-analysis`、`review-experience-diagnosis`、`commerce-diagnostic-synthesis` 四个 Skill；
- `subagent_required=true`；
- 默认 `max_concurrent_subagents=3`。

`subagent_required` 是通用 `AgentConfig` 策略，不是 Commerce 分支硬编码。Lead Agent 会把最终有效的 Subagent 开关和并发预算同时写入 `configurable` 与 `context`，保证 Tool 组装和 Middleware 读取同一策略。客户端即使发送 `subagent_enabled=false`，也不能关闭要求 Durable Subagent Harness 的内置 Agent；Parent 仍然可以根据任务复杂度选择动态派遣 0–N 个任务。

### Tool 隔离

通用 `ToolConfig` 新增：

- `default_enabled`：当 Agent 没有显式选择 Tool Group 时，是否进入默认工具集合；
- `enabled_if_env`：加载 Tool Provider 前必须通过的环境变量开关。

11 个 `commerce_*` Tool 均配置为：

```yaml
default_enabled: false
enabled_if_env: COMMERCE_CASE_AGENT_ENABLED
```

因此：

- 普通 DeerFlow Agent 默认看不到 Commerce Tool；
- `commerce-agent` 只有显式选择 `commerce` 组后才可能加载；
- 环境开关关闭时，即使显式选择该组也不会导入 Commerce Tool Provider；
- Harness 不导入 `app.commerce`，保持 `app.* → deerflow.*` 单向依赖。

### Gateway 执行边界

`start_run` 在读取 Run Manager、创建 Run Record、写 Thread Metadata 或启动后台任务前调用 `ensure_assistant_feature_enabled`。当 `assistant_id` 归一化为 `commerce-agent` 且 `COMMERCE_CASE_AGENT_ENABLED` 未开启时，返回：

```text
404 Commerce Agent is disabled
```

该检查覆盖 Thread Run 和复用 `start_run` 的运行入口，防止只隐藏前端链接却仍可直接调用后端 Agent。

### 前端纯路由合同

新增 `frontend/src/core/commerce/agent-ui.ts`，冻结：

- 唯一 Agent 名：`commerce-agent`；
- 默认 Chat：`/workspace/agents/commerce-agent/chats/new`；
- 协作空间：`/workspace/agents/commerce-agent/war-room`；
- `threadId / runId / mock` 查询参数；
- 中文展示名“电商经营诊断”和“协作空间”。

该模块不包含 React 布局；视觉母版确认后，Sidebar、Agent Chat Header 和协作空间页面必须复用这一合同。

## TDD 证据

RED：

- Agent 配置缺少 Subagent Runtime Policy；
- 客户端可以关闭 Commerce Subagent Tool；
- Gateway 缺少 Commerce Assistant Run 开关；
- 前端 Commerce Agent 路由模块不存在。

GREEN / VERIFY：

```text
Backend focused regression: 139 passed
Backend Ruff check: PASS
Backend Ruff format check: PASS
Frontend agent-ui Vitest: 3 passed
Frontend targeted Prettier: PASS
```

后端测试额外证明：关闭开关时，`start_run` 在访问任何运行依赖前返回 404；内置 Agent 未收到客户端并发值时使用配置中的 3，并且 Durable Subagent Tools 处于启用状态。

## 未完成与下一步

- 高保真 Chat 与游戏化协作空间候选稿仍需用户确认；
- 确认后为 Sidebar、Agent Badge、中文 Welcome、当前 Run ID 和“查看协作空间”入口写 React 失败测试；
- Chat 必须使用 `onStart(threadId, runId)` 捕获真实 Run ID，并将其传入 `CommerceRunTaskActivityViewModel` 和协作空间 URL；
- Agent 行为与浏览器 E2E 尚未在本阶段执行，不能把本阶段确定性通过写成 DeepSeek V4 Agent Release Gate。

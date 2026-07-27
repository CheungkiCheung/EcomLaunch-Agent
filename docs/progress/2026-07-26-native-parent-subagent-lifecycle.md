# Native Parent–Subagent Lifecycle

> 日期：2026-07-26
> 阶段：Chat-first 重定向 Phase 2
> 模型：fresh DeepSeek V4；身份可确认；Provider retry=0；禁止 Mock/Replay/Fallback 作为 Agent PASS

## 完成内容

- 将同一个 `SubagentTaskManager` 和 `DurableSubagentTaskRuntime` 注入真实 Parent `RunContext` / `ToolRuntime.context`；
- Gateway 生命周期持有 Durable Runtime，避免工具返回后后台监控任务被回收；
- 新增非阻塞 `spawn_task`，持久化 Task 后立即返回 `task_id`；
- 新增 `wait_task`，支持 one / any / all 和单次最长 60 秒等待；
- 新增 `follow_up_task`，允许同一 Thread 跨 Run 创建 Child Task；
- Follow-up 只传递显式父结果快照和新目标，不复用隐式推理历史；
- 新增 cooperative `cancel_task`；
- 新增 `resume_task`，重新获取 fencing lease、增加 attempt，并在预算耗尽时 fail closed；
- 依赖未完成时任务进入 waiting，依赖成功后自动调度，依赖失败时进入 blocked；
- Gateway 运行期间周期回收过期 Lease，不再只在启动时恢复；
- Gateway 关闭时将未完成任务显式置为 blocked，要求 resume/reassign；
- terminal transition 原子清除 Lease；
- 旧 `_background_tasks` 降为进程内 Executor Adapter，Durable Task 成为权威状态；
- 新增通用 `explore / analyst / verifier / operator` Profile；
- 所有 Profile 默认禁止 `task / spawn_task / wait_task / follow_up_task / cancel_task / resume_task`，防止递归委派；
- Parent Prompt 切换到 `spawn → continue → wait-any/all → follow-up/cancel/resume` 生命周期；
- 保留旧 `task` Tool 作为 DeerFlow 阻塞兼容入口；
- Subagent 并发中间件统一限制旧 `task` 和新 Durable dispatch；
- Token Attribution 能识别 Durable dispatch；
- 新增 Task/Event 只读 API；
- 运行中只持久化用户可见消息预览和脱敏 Tool Event，不记录 reasoning_content 或原始敏感参数；
- Subagent 模型调用采集实际模型身份、Provider Request ID、Response ID、Stop Reason、System Fingerprint 和 Token；
- 新增 fresh DeepSeek V4 Durable Runtime 与 Parent 0–N 路由门禁；
- 将 DeerFlow 原有真实 Client 测试正式标记为 `real_model`，避免非模型回归意外调用 Provider。

## 生命周期工具

```text
spawn_task
wait_task(one | any | all)
follow_up_task
cancel_task
resume_task
```

旧兼容路径：

```text
task
→ 仍然阻塞到终态
→ 不作为新 Commerce Parent 默认选择
```

## Task/Event API

```text
GET /api/runs/{run_id}/subagent-tasks
GET /api/subagent-tasks/{task_id}
GET /api/subagent-tasks/{task_id}/events?after_seq=...
```

API 返回真实 ContextPacket、Profile、Skill、Tool、Budget、Dependency、Attempt、Checkpoint、Result、Error、Telemetry 和 append-only events，并通过所属 Parent Run 做用户访问校验。

## 真实 DeepSeek V4 门禁

### Provider Preflight

```text
fresh request：PASS
endpoint：https://api.deepseek.com/v1
alias：deepseek-reasoner
actual identity：deepseek-v4-*
provider request id：存在
max_retries：0
```

### Durable Subagent

```text
spawn
→ running
→ 后台真实 DeepSeek V4
→ wait(all)
→ completed
→ identity / request id / token / stop reason 持久化

结果：PASS
```

### Parent 动态路由

```text
简单算术问题
→ 0 Subagent

复杂电商双工作流问题
→ 同一模型响应 2 个 spawn_task
→ explore + analyst

两次请求身份均为 DeepSeek V4，Request ID 存在且唯一
结果：PASS
```

### DeerFlow Client Streaming

```text
真实 DeepSeek V4 messages-tuple 非空 AI content
结果：PASS
```

## 确定性回归

```text
通用后端非模型集合：4283 passed, 18 skipped, 21 real-model deselected
Commerce 非模型集合：433 passed, 23 real-model deselected
触达文件 Ruff：PASS
git diff --check：PASS
```

真实模型测试与确定性测试严格分层：状态机、SQL、API、权限和序列化测试不调用 LLM；所有 Agent/LLM 行为 PASS 必须来自 fresh DeepSeek V4，不接受 Fake/Replay/缓存作为替代。

## 已知边界

- 当前 Executor Adapter 仍复用 DeerFlow 进程内线程池和 `_background_tasks`，跨进程 Worker 队列留到生产硬化；
- Resume 已具备 Durable attempt/fencing 语义，但 Subagent 内部 LangGraph checkpoint 的细粒度恢复仍未接入，当前从显式 ContextPacket 重新执行；
- SQL 表当前由 Harness metadata 初始化，正式 PostgreSQL Alembic migration 留到硬化阶段；
- Task/Event API 当前为读取和增量轮询，前端 SSE/WebSocket 聚合在 Chat-first 接入阶段实现；
- 新 Parent 路由门禁验证了真实模型工具选择，完整 Commerce 数据上传到自然回答的真实端到端链路属于 Phase 3；
- 旧固定 Commerce Path 尚未删除，必须等新动态主链完成 parity 和 Gold Gate。

## 下一阶段

进入 Phase 3：将现有 Commerce Capability、Metric、Evidence、Action 暴露为确定性 Tool，将履约、卖家对标、评价体验和综合诊断迁移为可加载 Skill，并让通用 Profile 在 Chat 问题下动态组合。

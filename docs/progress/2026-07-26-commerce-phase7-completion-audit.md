# Commerce Agent Phase 7 完成审计

> 日期：2026-07-27  
> 状态：本轮面试交付完成  
> 原则：只以当前代码、测试、真实模型审计和渲染产物为证据，不以计划文字或历史记忆代替完成证明。

## 1. Durable Parent–Subagent Harness

| 要求 | 当前证据 | 结论 |
|---|---|---|
| 动态 `0–N` 委派 | `spawn_task`、Dynamic Gold Gate 拓扑审计 | 已证明 |
| Parent 启动任务后继续行动 | 后台 Durable Runtime、首轮 Explore/Analyst 并行 | 已证明 |
| wait-one / wait-any / wait-all | `test_durable_subagent_task_runtime.py`、`test_durable_task_tools.py` | 已证明 |
| follow-up | Durable follow-up Tool 与 ContextPacket 最小权限测试 | 已证明 |
| cancel | cooperative executor cancel + durable `task.cancelled` | 已证明 |
| timeout | Runtime timeout + durable `task.timed_out` | 已证明 |
| resume / controlled retry / reassign | 新 fencing lease、attempt 增加、预算耗尽 fail closed | 已证明 |
| dependency scheduling | waiting、依赖完成启动、失败依赖 blocked | 已证明 |
| optimistic concurrency | SQL 双 Manager 并发 transition 仅一个成功 | 已证明 |
| Lease / Fencing | stale Worker 拒绝、token 递增 | 已证明 |
| orphan reconciliation | 过期 Lease → recovery_blocked → cooperative cancel | 已证明 |
| restart recovery | SQL Repository 重建与 PostgreSQL 重启恢复 | 已证明 |
| Tool 权限和双预算 | ContextPacket allowlist、max_tool_rounds、max_tool_calls | 已证明 |
| 模型身份和用量聚合 | Provider Request ID、实际模型、Token、Stop Reason、retry | 已证明 |

本轮聚焦确定性回归：

```text
452 passed in 5.10s
```

仅有一个第三方 LangGraph serializer pending-deprecation warning，没有测试失败。

当前恢复边界：Task 级 Checkpoint、ContextPacket、attempt 和 fencing 已完成；Subagent 内部 LangGraph 的逐节点 checkpoint 细粒度续跑尚未接入，当前 resume 从显式 ContextPacket 和持久化 checkpoint 重新执行。未知外部模型结果不会自动重试。

## 2. Dynamic Commerce Tool / Skill

| 要求 | 当前证据 | 结论 |
|---|---|---|
| 异构上传与 Workspace/Thread 隔离 | 上传、Ingest、active Dataset Context | 已证明 |
| 确定性 Capability / Metric / Evidence | 11 个 Commerce Tool 和数据层回归 | 已证明 |
| 通用 Profile + Skill | explore / analyst / verifier / operator + 4 Commerce Skill | 已证明 |
| 简单问题可不派任务 | Dynamic Release 合同 | 已证明 |
| 复杂问题动态并行 | 四 Gold Gate 首轮 Explore/Analyst 并行 | 已证明 |
| fresh-context Verification | Verifier 只引用当前 Run 终态 `task:<id>` | 已证明 |
| Evidence、反证和 unknown | deterministic quality gate + Response Guard | 已证明 |
| Action Policy / Approval / Rollback | 内部 Artifact Connector 可逆门禁 | 已证明 |

四条统一 Dynamic Gold Gate：

```text
4 passed in 253.05s
每条 15 个唯一请求
actual_model_identity=deepseek-v4-flash
retry=0
Parent Tool Error=0
```

最新单 Case Chat Dynamic Gate v7：

```text
2 passed in 70.58s
run_id=2233f98a-4dc5-4e29-b810-a8b457ab668d
request_count=17
total_tokens=199,598
actual_model_identity=deepseek-v4-flash
retry_count=0
Parent Tool Error=0
issues=[]
```

该 Gate 使用真实 Explore / Analyst 并行 Durable Task，随后在首轮任务终态后创建 fresh Verifier。v7 的最终答案使用过一次受限、无 Tool 的 Response Guard，因此可以声称完整 Gate 通过，但不能声称首答零修复或 repair-free。

最新持久化 Chat 浏览器 Gate v7：

```text
thread_id=63c65e2a-9dd2-4a2e-8cf5-c7484c0d1c48
run_id=1c07e293-8f41-4213-b406-17c8c150f8d8
status=success
configured_alias=deepseek-reasoner
actual_model_identity=deepseek-v4-flash
run.llm_call_count=6
provider_request_ids_unique=13
total_input_tokens=161,301
total_output_tokens=9,093
total_tokens=170,394
lead_agent_tokens=124,966
subagent_tokens=45,428
retry_count=0
```

该 Gate 通过真实本地注册/登录、CSRF、六文件上传、持久化 Thread/Run 和同源 Task/Event API 完成。Explore 与 Analyst 真实并行，随后创建 fresh Verifier；三个 Durable Task 均为 `completed`。Gateway 重启后仍可恢复最终答案、三个 Task、104 条 Run Event、6 条 AI Response Event 和 15 条消息。浏览器续审模式只读取同一个既有 Run，不提交 Prompt、不创建新 Run，也不再次消耗模型 Token。证据入口：`docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/`。

## 3. Skill Evolution

| 要求 | 当前证据 | 结论 |
|---|---|---|
| Active Skill 不被在线改写 | Candidate/Active Pointer 隔离合同 | 已证明 |
| Control / Candidate | Experiment Report | 已证明 |
| Regression / Holdout | 四 Case × 两次 Candidate `8/8` | 已证明 |
| Shadow | 两个真实隔离 Shadow Run | 已证明 |
| Human Review / Promotion / Rollback API | 确定性合同和 API 测试 | 已证明 |
| 当前 Candidate 晋级 | 需要用户 Human Promotion | 未执行 |

## 4. 真实 DeepSeek V4

2026-07-26 fresh Preflight：

```text
configured_alias=deepseek-reasoner
configured_model=deepseek-v4-flash
actual_model_identity=deepseek-v4-flash
endpoint=https://api.deepseek.com/v1
provider_request_id=present
input_tokens=63
output_tokens=11
total_tokens=74
stop_reason=stop
request_attempt_count=1
retry_count=0
http_status_code=200
```

所有 Key 只从 Git 忽略的根 `.env` 读取，不进入本文、代码或模型审计正文。

## 5. Chat / Collaboration 前端

已证明：

- DeerFlow 原生中文 Chat 是唯一默认入口；
- authenticated Durable Task/Event API；
- 严格 Zod 合同；
- 每 Task 独立 cursor；
- 乱序、重复、未知 Event 显式处理；
- Run 切换、刷新和卸载 Abort；
- 九个持久化状态的 Visual State 投影；
- failed / cancelled / timed_out 独立终态；
- renderer-neutral Collaboration Scene ViewModel；
- 一个唯一 `task_id` 最多一个 Actor；
- 没有 Task 时没有固定 Crew 或假忙碌；
- Tool 道具、审批、阻塞和终态只来自真实 Event；
- 原创 ImageGen 空场景、四种 Profile 角色和四类工位已进入运行时；
- 一个 Durable Task 对应一个角色和一个工位；
- 四 Task 桌面 2×2 与窄屏缩放布局无重叠；
- failed / cancelled / timed_out 保留独立视觉终态；
- Drawer、390px 窄屏、横向溢出和 reduced-motion 合同已覆盖。

最新前端门禁：

```text
Vitest: 62 files / 334 tests passed
ESLint: PASS
TypeScript: PASS
Prettier: PASS
Commerce Chat/协作空间 Playwright: 6 passed
Persistent Chat browser Gate: fresh run PASS + same-run resumed audit PASS
Next.js 16.2.6 production build: PASS
Static pages: 79 / 79
```

为避免覆盖当前 dev server 使用的 `.next`，最新源码在 `/private/tmp` 隔离副本中使用完整 `node_modules` 目录结构完成 production build。Turbopack 编译、TypeScript、page data 和 79/79 静态页面生成全部通过；隔离副本没有 Git 元数据和现有 mock artifact route 的动态文件追踪提示为非失败警告。

持久化 Chat 浏览器证据已证明：

- 通过可见回形针选择冻结的六个公开 CSV，并在真实本地账号下创建持久化 Thread/Run；
- 同一 Run 完成 Parent、Explore/Analyst 并行、fresh Verifier 和最终中文回答；
- 同一 Run 的协作空间、任务 Drawer、桌面、390px 与 reduced-motion 截图通过；
- actual model identity、Provider Request ID、Token、retry 和任务拓扑完成端到端核对；
- SQLite Checkpointer、Store 与 DB Run Event 在 Gateway 重启后恢复完整 Run/Task/Event/Answer。

已知非阻塞 UX 债务：任务 Drawer 的 Dataset ID 与 ISO 时间仍偏工程化；桌面 Drawer 会遮住部分第三工位，但底部三任务状态仍完整可见。外部商家平台真实写入和生产多租户性能仍不在本轮证明范围内。

## 6. PostgreSQL / Connector

- PostgreSQL 16 真实迁移、写入、连接重建、Run/Checkpoint/Event 恢复、Lease 过期和 fencing takeover 已通过；
- 内部 Artifact Connector 已通过写入、SHA-256 读回、持久化、归档回滚和再次哈希验证；
- 这不代表生产多节点 HA、性能压测或真实商家平台写权限；
- 外部商家 Connector 继续 fail closed，等待用户提供真实账号和明确写授权。

## 7. 求职材料

- 中文 Markdown 求职包已完成；
- 20260726 单页 Commerce Agent DOCX 已完成；
- 原简历未覆盖，源 SHA-256 不变；
- 17/17 preserve-only DOCX parts 保持；
- macOS Quick Look 原生渲染中文、单页和布局通过；
- 20260727 DOCX/PDF 已补入 v7、中文 Chat、原创协作空间和最新前端证据；结构、Quick Look 原生中文和 Poppler PDF 视觉 Gate 已通过；
- Markdown 求职包、架构、Demo 与面试问答已同步持久化浏览器 Gate、调优过程和最新回归；
- 最终投递文案仍应针对具体 JD 做关键词裁剪，但这不影响项目本身的面试交付完成状态。

## 8. 真实调优与选型过程

本轮没有把失败隐藏成重试或模型回退，而是保留了以下可复述的工程链路：

1. `127.0.0.1` 下的前端 Hydration/来源不一致，统一真实浏览器入口为 `localhost`；
2. 上传返回 403 后，补齐一次性本地账号、Cookie 与 CSRF 预检；
3. 早期审计只记录本地 alias，修复为同时持久化 `deepseek-reasoner` 与服务端真实身份 `deepseek-v4-flash`；
4. Parent 曾只在文本中说“准备派工”，没有产生 `spawn_task` Tool Call，Subagent Token 为 0，最终被 Requirement Gate 拦截；
5. 直接对 DeepSeek thinking 请求设置 `tool_choice=required` 返回 400，因为 thinking 模式不支持该能力；
6. 最终采用同一个 `deepseek-v4-flash` 的 capability-aware dispatch control：业务分析轮保持 thinking，派工控制轮临时关闭 thinking 并要求正式 `spawn_task` Tool Call；
7. 同步修复禁用 thinking 时不回放历史 `reasoning_content`，并只在 terminal streaming chunk 写入模型身份、Request ID 和 retry，避免 Chunk 合并重复拼接遥测；
8. 将 Checkpointer、Store 和 Run Event 切到 SQLite/DB，完成 Gateway 重启后的 Thread/Run/Task/Event/Answer 恢复；
9. 浏览器 Gate 增加同一 Run 的只读续审模式，避免后置视觉断言失败后重复花费真实模型 Token。

## 9. 完成结论与保留边界

本轮目标——可演示、可写简历、可进行 AI Agent 岗位面试的 Commerce Agent——已完成。完成结论基于真实六文件持久化 Chat、fresh DeepSeek V4 Parent–Subagent Run、同源协作空间、重启恢复、完整机械回归、安全扫描和同步求职材料。

以下事项是主动保留的产品/发布边界，不属于本轮未完成 Bug：

- 外部商家 Connector 继续 fail closed，只有真实账号、权限和回滚验证齐备后才开放；
- Skill Candidate 继续保持 `shadow`，Promotion 必须由人审明确授权；
- 公开 Olist 数据证明系统行为、可复算性和工程可靠性，不证明企业业务 uplift；
- 未完成生产多节点 HA、容量压测、正式多租户 Workspace 权限和外部平台写入；
- Subagent 内部 LangGraph 仍是 Task 级恢复，不声称逐节点 exactly-once。

## 10. 最终机械与安全回归

2026-07-27 最终收口实跑：

```text
Backend Harness/Commerce targeted pytest: 452 passed
Frontend Vitest: 62 files / 334 tests passed
Frontend ESLint: PASS
Frontend TypeScript: PASS
Frontend Prettier: PASS
Commerce Chat/Collaboration Playwright: 6 passed
Next.js 16.2.6 production build: PASS
Static pages: 79 / 79
git diff --check: PASS
32+ hex-character sk-* repository scan: 0 files
Frontend health: HTTP 200
Gateway health: HTTP 200
```

对当前 Commerce/Harness 变更集的 Ruff 检查为 `All checks passed`。全 Backend Ruff 扫描额外发现 23 个旧 OpenSKU/last30days 的未使用 import、旧 Optional 注解和 import 排序问题；这些文件属于项目 `Legacy` 只读边界，本轮没有为追求全绿而改写历史代码。该结果是已知代码卫生债务，不影响 Commerce Release Gate。

最终只读恢复核对再次登录同一验收账号，得到：

```text
login_status=200
run.status=success
run.total_tokens=170394
run.llm_call_count=6
task_count=3
task_statuses=completed/completed/completed
task_profiles=analyst/explore/verifier
event_count=104
message_count=15
ai_message_count=6
final_answer_present=true
```

本轮没有重新运行真实 PostgreSQL Gate：当前环境未设置 `COMMERCE_TEST_POSTGRES_URL`，本地 5432 未启动。此前真实 PostgreSQL 16 全迁移、连接重建、Checkpoint 恢复和 fencing takeover 的通过证据仍保留在 `docs/progress/2026-07-26-commerce-postgres-skill-evolution-release.md`；SQLite 持久化与重启恢复则在本轮重新验证。

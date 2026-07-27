# Commerce Dynamic Release Hardening

> 日期：2026-07-26
> 分支：`feature/commerce-case-agent`
> 状态：完成
> 模型：本地 alias `deepseek-reasoner`，服务端身份 `deepseek-v4-flash`

## 1. 目标

把动态 Parent–Subagent 主链从“单条履约用例可以运行”硬化为四条 Gold Case 都可复现、可审计、可控成本的 Release Gate：

2026-07-26 继续运行了一次不复用历史 Trace 的 fresh Preflight，服务端实际身份仍为 `deepseek-v4-flash`，HTTP 200，Provider Request ID 存在，Total Tokens `74`，Stop Reason `stop`，retry `0`，因此当前 Agent 测试配置仍可用。

```text
Preflight
→ Parent ingest / capability
→ 并行 Explore + Analyst Durable Task
→ wait-all
→ fresh-context Verifier
→ 中文最终回答
→ deterministic quality / topology / identity / budget Gate
→ secret-free immutable audit
```

所有 Agent/LLM 验证都使用 fresh DeepSeek V4，`max_retries=0`。Mock、Replay、缓存和其他模型不作为通过证据。

## 2. 真实调优链

这轮硬化保留了从失败到修复的完整工程证据，而不是只记录最终绿灯。

### 2.1 Parent 拼错或混入 unknown Task ID

问题：一次 `wait_task` 中混入 unknown ID 会让已正确启动的 Task 结果一并丢失，Parent 难以恢复。

修复：不做 ID 模糊匹配；多 ID 等待允许正确 ID 部分成功，unknown 路径只返回当前 user/thread/run 内授权的 `known_task_ids` 和紧凑 Task 快照。显式访问其他 Run 的真实 Task ID 继续 fail closed。正常等待不重复附带恢复清单，避免输出膨胀。

### 2.2 Verifier 使用裸 Task ID

问题：模型可能把 `call_...` 直接放进 `source_refs`，无法满足 fresh Verifier 的显式 lineage 合同。

修复：只对 `verifier`、当前 Run、精确匹配、已终态 Task 做安全正规化：

```text
call_01... → task:call_01...
```

不存在、模糊、跨 Run 或非终态引用全部拒绝。

### 2.3 Tool 输出挤占上下文

问题：Subagent 没有 `read_file` 时仍请求完整 Profile，会生成 22k–29k 输出后再被截断；Compare 默认返回过多指标还导致低分率和晚到率混淆。

修复：Executor 注入 `available_tool_names`；Profile 在 reader 不可用时直接返回完整可消费的 compact 版本。履约 Compare 显式只请求 `order_count / late_delivery_rate / handling_time_hours / transit_time_hours`。Source Fact ID 预览压到 6 个并保留可分页查询语义。

### 2.4 只有 Tool Round，没有 Tool Call 总预算

问题：模型可在同一轮并行发出超过预期的 Tool Call，`max_tool_rounds` 无法约束单轮爆发。

修复：增加 `max_tool_calls` 并贯穿 Profile Config、Registry、ContextPacket、Durable Tool、Executor、中间件和 Release 审计。达到上限后下一次模型请求卸载 Tool 并强制综合；当前响应超过剩余额度时只保留允许数量。

Peer Analyst 实际从潜在的 5 次调用被稳定限制为 4 次：

```text
peer comparison
+ geography
+ evidence
+ evidence
```

### 2.5 中文事实与否定语义误报

问题：Unicode `\b` 会把“从141单增到202单”中的整数边界判断错误；“不涉及”“不能直接推断为”等限制语也会被误判为肯定结论。

修复：数字使用 `(?<!\d)...(?!\d)`；禁止结论检查同时理解局部前置和后置否定语义，并继续拒绝先肯定、后自我否定的双重表达。

### 2.6 有界 Response Guard

问题：Peer 的事实、拓扑和 Verifier 均正确时，模型仍可能在正文先写“显著高于”，后面再说明未做统计检验，导致确定性 Gate 正确拒绝。

修复：增加最多一次的 Response Guard：

- 只有全部 issue 都以“最终回答”开头时才允许触发；
- 使用 fresh `deepseek-v4-flash`，无 Tool，`max_retries=0`；
- 只能改写原答案，不得新增事实、数字、ID、外部事件或因果；
- 保留正确数值、`mobs_` 引用和数据限制；
- 请求计入 Parent Request / Token / Request ID 审计；
- 修复后重新执行完整 deterministic Gate；
- 任何拓扑、Task、Tool、身份、预算、并行生命周期或 Verifier 问题均不可修复；
- 审计不保存原始或修复后的明文答案，只保存最终 SHA-256、初始 issue 和安全错误类型。

独立真实模型 smoke 证据：

```text
actual_model_identity = deepseek-v4-flash
provider_request_id   = present
stop_reason           = stop
total_tokens          = 420
forbidden assertion   = removed
```

## 3. 四条统一 Gold Gate

统一命令：

```bash
cd backend
set -a
source ../.env
set +a
uv run pytest \
  tests/commerce/chat/test_chat_dynamic_diagnosis_live.py \
  tests/commerce/chat/test_chat_dynamic_gold_cases_live.py \
  -q -s
```

结果：

```text
4 passed in 253.05s
```

| Case | Passed | Requests | Parent Tokens | Subagent Tokens | Total Tokens | Tool Calls | Repair | Parent Tool Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GC-FULFILLMENT-001 | yes | 15 | 127,004 | 63,000 | 190,004 | 12 | 0 | 0 |
| GC-REVIEW-002 | yes | 15 | 127,309 | 55,125 | 182,434 | 12 | 0 | 0 |
| GC-CAPABILITY-003 | yes | 15 | 126,878 | 58,587 | 185,465 | 12 | 0 | 0 |
| GC-PEER-004 | yes | 15 | 124,568 | 54,862 | 179,430 | 15 | 0 | 0 |

四份审计共同满足：

- Preflight、Parent 和所有 Subagent 实际模型身份均为 `deepseek-v4-flash`；
- Provider Request ID 完整且全局唯一；
- Stop Reason 仅包含正常的 `tool_calls / stop`；
- `max_retries=0`；
- Parent Tool 错误为 0；
- Explore / Analyst 生命周期真实重叠；
- Verifier 在首轮 Task 终态后创建并显式引用全部 `task:<id>`；
- Request、Token 和 Tool Call 均未超过冻结预算；
- 审计目录 `.deer-flow/commerce/evaluation/chat-dynamic-release/` 不进入 Git。

## 4. 确定性回归

覆盖 Harness Budget、Tool Error/Output、Executor、Durable Task、Task API、Dynamic Release、Commerce Data Tool 和 Commerce Skill：

```text
315 passed in 3.08s
Ruff check passed
Ruff format check passed
```

Response Guard 专项合同为 `23 passed`，覆盖：只修最终回答、修复请求计费、审计字段、剩余禁句继续失败、错误只保留安全类型。

## 5. 结论与下一阶段

动态后端主链不再由单一演示 Case 证明，而是由四类不同数据能力、不同 Skill/Tool 最小包和不同答案安全边界共同证明。Phase 4 下一步是把这条已经可审计的真实运行时接入中文 Chat-first 页面；Chat 紧凑任务卡和后续游戏化协作空间必须消费同一 Durable Task Event 源，不能从自然语言或计时器伪造 Agent 状态。

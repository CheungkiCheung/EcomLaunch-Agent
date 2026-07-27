# Commerce Dynamic Tool / Skill Chain 与 Harness 预算调优

> 日期：2026-07-26  
> 阶段：Chat-first 重定向 Phase 3A–3D  
> 模型：fresh DeepSeek V4，实际身份 `deepseek-v4-flash`，Provider retry=0  
> 结论：动态上传诊断主链的功能、证据质量与成本门禁通过；前端 Phase 4 可以开始

## 1. 本阶段解决的问题

旧 Commerce 主链已经有可靠的 Data、Case、Evidence、Action 和 Gold Case，但默认 Agent 仍由固定 Path 组合驱动。这个阶段把履约诊断迁移为开放 Chat 下的动态 Parent–Subagent 链：

```text
用户上传真实数据并自然提问
→ Parent 接入 Dataset 并检查 Capability
→ 同一响应并行派遣 Explore + Analyst
→ wait(all)
→ 单独派遣 fresh-context Verifier
→ Parent 用中文综合 Evidence、反证、限制和下一步
```

通用 Profile 仍是 `explore / analyst / verifier / operator`；履约专业性由 `fulfillment-investigation` Skill 和确定性 Commerce Tool 提供，不新增固定 `fulfillment-agent` Crew。

## 2. Thread / Workspace / Dataset

新增 `CommerceThreadContextService`，把 Chat 身份映射为稳定、隔离的数据上下文：

```text
(user_id, thread_id)
→ deterministic WorkspaceId
→ active DatasetId
```

实现能力：

- 用户和 Thread 隔离；
- CSV、JSON、JSONL、XLSX、ZIP；
- 上传内容 SHA-256 幂等；
- 相同内容复用 Dataset，内容变化创建新 Dataset；
- 私有快照、no-follow、拒绝符号链接和路径型文件名；
- Context / Receipt 原子写入；
- 损坏 active Dataset 时 fail closed；
- `CommerceDataService.ingest_paths()` 从快照路径流式摄取。

## 3. 确定性 Commerce Tool

Parent 与 Subagent 共用以下 11 个 Tool：

```text
commerce_ingest_uploads
commerce_list_datasets
commerce_select_dataset
commerce_dataset_profile
commerce_capabilities
commerce_list_entities
commerce_metric_snapshot
commerce_compare_windows
commerce_peer_comparison
commerce_geographic_segments
commerce_evidence_query
```

关键纪律：

- Metric 由确定性引擎计算，模型不能心算；
- 缺失能力返回 `unknown / partial / unavailable`；
- 相关性不写成因果；
- MetricObservation 使用 `mobs_` ID；
- Fact 使用 `fact_` ID 并保留 SourceRef；
- Profile、Evidence、Entity 和 Source Fact 返回值做紧凑化，避免把完整 Dataset 内容塞回模型上下文；
- Metric 名称和 Fact ID 使用闭集/正则 Schema，模型不能创造不存在的指标或引用。

## 4. Dynamic Skill / Tool Envelope

新增并启用：

```text
fulfillment-investigation
seller-peer-analysis
review-experience-diagnosis
commerce-diagnostic-synthesis
```

`spawn_task` 与 `follow_up_task` 支持动态最小能力包：

```json
{
  "subagent_type": "analyst",
  "skills": ["fulfillment-investigation"],
  "tools": [
    "commerce_compare_windows",
    "commerce_evidence_query"
  ],
  "max_tool_rounds": 2
}
```

约束：

- Parent 请求只能收窄 Profile 的 Skill、Tool 和预算，不能扩权；
- 重复或越权 Skill / Tool 拒绝；
- `ContextPacket.available_skills`、`available_tools` 和 `budget` 记录实际委派合同；
- Follow-up 省略参数时继承父任务最小能力包；
- Resume 从持久化 ContextPacket 恢复同一 Skill / Tool / Budget，不回到宽权限默认值。

## 5. Fresh Verifier

Verifier 必须显式提供至少一个终态任务引用：

```text
source_refs = ["task:<task_id>"]
```

Harness 验证任务属于当前用户/Thread、已进入终态，并注入只读 source snapshot：

```json
{
  "source_snapshots": {
    "task:<id>": {
      "status": "completed",
      "result": {},
      "error": null,
      "evidence_refs": []
    }
  }
}
```

Verifier 不继承 Parent 的完整消息和隐式推理历史，必须重新调用确定性 Tool 验证关键 Claim。

## 6. 真实运行时缺口与修复

### 6.1 DeepSeek V4 模型名

Provider 明确拒绝旧请求模型名并返回支持列表。配置保留本地别名 `deepseek-reasoner`，实际请求改为：

```yaml
model: deepseek-v4-flash
api_base: https://api.deepseek.com/v1
max_retries: 0
```

### 6.2 Streaming Request ID

DeepSeek raw stream chunk 带稳定 UUID，但 `langchain-openai` 转换时丢弃顶层 `id`。`PatchedChatDeepSeek` 将 raw ID 写入 `response_metadata["id"]`，使 Parent/Subagent 每次请求都能审计 Provider Request ID。

### 6.3 Gateway Checkpointer Thread Identity

Gateway 使用新版 runtime `context`，LangGraph Checkpointer 仍读取 `configurable.thread_id`。`run_agent` 现在同时安装权威：

```text
configurable.thread_id
configurable.run_id
configurable.__pregel_runtime
```

### 6.4 Subagent User Identity

Commerce Workspace 依赖 `(user_id, thread_id)`。最初 `SubagentExecutor` 只传播 `thread_id` 和 `app_config`，背景执行边界丢失 ContextVar 后会落到 `default` 用户，导致 Subagent 看不到 Parent 已选择的 Dataset。

修复：

- Durable 与 Legacy builder 都调用 `resolve_runtime_user_id(runtime)`；
- `SubagentExecutor` 保存显式 `user_id`；
- `_aexecute()` 把 `user_id` 注入真实 `ToolRuntime.context`；
- 单元测试覆盖构造器传播与实际 `astream(..., context=...)` 参数。

## 7. Tool Round Budget Harness

仅在 Prompt 中写“最多调用 4 次 Tool”不足以约束真实模型。DeepSeek 会继续做重复 Entity、Snapshot、Evidence 和地域查询。

新增 `SubagentToolBudgetMiddleware`：

- 一个包含 1–N 个并行 Tool Call 的 AIMessage 消耗一轮；
- 达到 `max_tool_rounds` 后，在下一次模型调用前卸载全部 Tool；
- 注入隐藏的收敛指令，要求基于已有证据立即综合；
- 注入发生在 ToolMessage 完整配对之后，不破坏 OpenAI-compatible tool-call 协议；
- 证据不足时必须返回 `unknown / not_verified`，不能为了结束伪造结论。

这使 Loop Engineering 成为可执行 Harness 机制，而不是文案约定。

## 8. Fresh DeepSeek V4 调优轨迹

| 版本 | 请求数 | Token | 结果 | 主要问题 / 决策 |
|---|---:|---:|---|---|
| 首次可审计主链 | 34 | 589,256 | 功能通过、成本失败 | 所有 Skill 注入、Tool Schema/结果过大、重复查询、用户身份偶发丢失 |
| Dynamic Skill + 紧凑 Tool 输出 + user_id 修复 | 28 | 404,723 | 成本失败 | Explore 8 Tool、Analyst 9 Tool、Verifier 7 Tool；三个任务均 6 次模型调用 |
| 最小 Tool 包 + Tool Round Budget | 15 | 162,225 | 成本通过、质量拒绝 | Analyst/Verifier 用完预算前未做 Evidence 抽查；最终 stop reason 为 `length` |
| 最终质量/成本 Gate | 16 | 184,381 | **PASS** | Analyst/Verifier 固定为 `compare → evidence` 两轮；全部 Subagent 正常 `stop` |

最终 Gate：

```text
Parent tools:
ingest → capability → spawn(explore, analyst) → wait(all)
→ spawn(verifier) → wait → Chinese answer

Explore:
dataset_profile + capabilities
2 model calls
stop

Analyst:
compare_windows → evidence_query
3 model calls
stop

Verifier:
compare_windows → evidence_query
3 model calls
stop

Total:
16 unique fresh requests
184,381 tokens
retry=0
actual model identity=deepseek-v4-flash
```

成本阈值：

```text
request_count <= 24
total_tokens <= 350,000
```

最终结果相对首次基线：

- 请求数下降约 52.9%；
- Token 下降约 68.7%；
- 保留 Evidence 抽查、fresh verification、反证和数据限制；
- 未通过降低 Gate、Mock、Replay、Fallback 或提高重试获得 PASS。

本地 secret-free 审计写入 Git 忽略目录：

```text
.deer-flow/commerce/evaluation/chat-dynamic-release/
```

审计文件不提交到 Git，不包含 API Key 或原始模型推理。

## 9. 验证证据

本阶段最终执行：

```text
Phase 3D 触达非模型集合：178 passed
配置 / Tool Schema / Durable 集合：68 passed
其他迭代集合：153 passed、120 passed、74 passed、68 passed
触达文件 Ruff：PASS
fresh DeepSeek V4 dynamic release gate：1 passed in 79.10s
```

真实 Gate 强制验证：

- Parent、Explore、Analyst、Verifier 实际身份均为 `deepseek-v4-*`；
- Provider Request ID 存在且唯一；
- Token > 0；
- retry=0；
- Explore/Analyst 同一 AIMessage 并行派遣；
- Verifier 在第一波终态后创建；
- ContextPacket 只包含最小 Skill、Tool 和预算；
- Analyst 与 Verifier 均执行 `commerce_compare_windows` 和 `commerce_evidence_query`；
- 最终中文回答包含 `mobs_`、阶段定位、反证、数据限制和下一步；
- 不声称拥有库存、利润、曝光、点击或广告消耗；
- 不把相关性写成因果。

## 10. 仍未完成

- 另外三条 Gold Case 在新动态主链上的完整 parity / release gate；
- Chat-first React 主入口和真实 Task Event 流；
- Task Event → Visual State 合同与原创协作空间；
- 真实浏览器 Agent E2E；
- 正式 PostgreSQL 重启恢复；
- 外部真实可逆 Connector；
- Shadow Candidate 的 Human Review / Active Promotion；
- 最终录屏、简历和面试讲稿。

旧固定 Path 主链不得删除，直到跨 Case 动态主链门禁和浏览器门禁完成。

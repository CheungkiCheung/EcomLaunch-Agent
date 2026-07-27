# Commerce Case Agent 完整设计与实施计划

> 2026-07-24 架构重定向：本文件保留 2026-07-18 至 2026-07-23 的实现范围、验证证据和历史决策，不再作为后续默认产品与运行时主线。新的权威实施计划为 `docs/plans/2026-07-24-commerce-chat-subagent-harness-plan.md`，决策见 `docs/adr/0006-commerce-agent-is-chat-first-with-dynamic-subagents.md`。
> 状态：设计已收口；四 Gold Case 完整 Agent Investigation Gate 已通过；运行时路线为 DeerFlow Subagent Harness + Commerce Domain
> 日期：2026-07-18（2026-07-20 更新）
> 当前分支：`feature/commerce-case-agent`
> 保护快照：`archive/ecom-launch-pre-commerce-agent-20260718` / `9144237`
> 上游基础：DeerFlow
> 内部代号：Commerce Case Agent

## 1. 目标

将当前以 EcomLaunch、固定多 Agent Crew 和文件交付物为中心的 OpenSKU，改造为一个真实可用的电商经营异常诊断与行动 Agent：

```text
异构经营数据进入
→ 自动理解字段、实体和数据能力
→ 确定性扫描经营异常
→ 创建长期存在的 Case
→ Goal Loop 动态调查必要证据路径
→ 独立 Verification 检查结论
→ 生成结构化 Action
→ 人工审批和受控执行
→ 新数据到来后 Follow-up
→ 关闭、重开或重新规划 Case
```

最终产品应同时具备：

- 面向运营人员的真实产品价值；
- 面向 Agent 岗位的 Harness、Loop、Context、Memory、Eval 和受控进化亮点；
- 可复现的模型、Effort、Skill 和架构选型过程；
- 明确的 DeerFlow 上游能力与个人增量边界；
- Codex-inspired Commerce Agent Workspace；
- 由真实结构化事件驱动的 War Room。

## 2. 非目标

本轮不建设：

- 万能电商经营平台；
- 覆盖所有广告、库存、利润、定价和内容生成场景的全能 Agent；
- 模拟市场或虚构经营提升；
- 固定五 Agent / 六 Agent Crew；
- 只输出报告、方案或文案的系统；
- 运行时直接修改 Active Skill 的全自动自进化；
- 自动修改模型权重；
- 无审批的高风险业务执行；
- 依赖自然语言正则解析状态的 War Room；
- 将 DeerFlow 已有 Harness、Sandbox、MCP、Memory、RunManager 等能力包装成个人原创。

## 3. 已确认产品定位

### 3.1 一句话定位

> 面向电商运营的异构数据诊断与行动 Agent。

### 3.2 用户核心问题

```text
哪里出了问题？
为什么发生？
现在最值得做什么？
做完以后有没有改善？
```

### 3.3 核心产品对象

核心对象是 `Case`，不是 Chat，也不是 Artifact。

长期业务对象：

- Workspace
- Dataset / DataSource
- Entity
- Fact
- MetricObservation
- Capability
- Evidence
- Case
- Hypothesis
- Action
- Approval
- FollowUp
- Skill
- EvaluationCase
- Experiment
- EvaluationRun

语义状态：

- `observed`
- `derived`
- `estimated`
- `hypothesis`
- `unknown`
- `blocked`

## 4. 核心用户旅程

```text
用户上传 CSV / Excel / JSON / ZIP，或连接 API
→ Data Intake 识别文件、表和编码
→ Profiler 识别字段、类型、主键、时间和质量问题
→ Semantic Mapper 映射实体和标准字段
→ 用户确认低置信度映射
→ Capability Registry 声明当前能够分析什么
→ Metric Layer 计算确定性指标
→ Anomaly Detector 发现异常
→ 创建结构化 Case
→ Lead Agent 运行 Goal Loop
→ 按 Capability 动态启动 0–3 个 Path Agent
→ Evidence 和 Hypothesis 持续更新
→ Verification 使用 Fresh Context 黑盒验证
→ 用户批准、修改或拒绝 Action
→ Connector 执行动作或创建内部任务
→ 新数据到达后启动 FollowUp Run
→ Case resolved / reopened / inconclusive / blocked
```

## 5. 核心 Gold Cases

### 5.1 GC-FULFILLMENT-001

真实 Olist Seller `4869f7a5dfa277a7dca6462dcf3b52b2`：

- 延迟率从约 3.5% 升至 35.1%；
- 平均评分从约 4.23 降至 3.60；
- 延迟订单平均评分显著更低；
- 卖家处理时长没有恶化；
- 承运配送时长显著增长；
- 同期平台也有物流波动，但当前卖家更严重；
- 系统应反驳“卖家出库能力不足是主要原因”；
- 精确承运商与路线原因必须保持 `unknown`；
- 后续指标恢复，但 Action 因果效果为 `inconclusive`。

### 5.2 GC-REVIEW-002

真实 Olist Seller `0b90b6df587eb83608a64ea8b390cf07`：

- 延迟率降至 0%；
- 评分和低分率显著恶化；
- 评论集中出现疑似非原装、错发、少发和数量不完整；
- Router 应跳过完整 Fulfillment Path；
- 系统只能说“客户报告真实性不一致”，不能确认售假或欺诈；
- `delivered` 状态与“未收到商品”评论构成 Evidence Conflict；
- 后续评分恢复，但 Action 因果效果为 `inconclusive`。

### 5.3 GC-CAPABILITY-003

从 GC-FULFILLMENT-001 派生的真实数据能力删减版本：

- 仅提供订单、订单项、卖家和客户数据；
- 不提供 Reviews；
- 系统仍应完成履约异常诊断；
- 不得声称评分或客户满意度下降；
- ReviewExperiencePathAgent 必须被跳过；
- Goal 状态为 `partially_achieved`，而不是整条 Run 失败；
- 必须生成精确补数建议。

## 6. 目标架构

```text
Product Plane
├── Data Workspace
├── Capability Report
├── Case Queue / Case Detail
├── Evidence / Hypothesis
├── Action / Approval
├── Follow-up
├── Agent Run
└── Skills & Evals

Runtime Plane
├── GoalLoopController
├── DynamicPathRouter
├── ModelRouter
├── ContextBuilder
├── MemoryScopes
├── ToolGateway / Sandbox
├── BudgetManager
├── RetryPolicy
├── Checkpoint / Resume
├── VerificationEngine
└── StructuredEventPublisher

Improvement Plane
├── GoldCaseRegistry
├── EvaluationContracts
├── ExperimentRegistry
├── DeterministicEvaluators
├── SemanticEvaluator
├── TraceEvaluator
├── SkillCandidateRegistry
├── Holdout / Regression
├── Shadow
└── Promotion / Rollback
```

### 6.1 运行时选型决定（2026-07-19）

主架构固定为：

```text
DeerFlow Agent Harness
├── Commerce Lead Agent Loop
├── DeerFlow Subagent Executor
│   ├── Fulfillment Subagent
│   ├── SellerPeer Subagent
│   ├── ReviewExperience Subagent
│   └── Fresh Verification Subagent
├── Tool / Skill / Model / Streaming / Checkpointer
└── CommerceSubagentAdapter
    └── Commerce Case / Run / Event / Evidence / Policy
```

选型原则：

- DeerFlow 是主 Harness，复用现有 Subagent、Tool、Skill、Streaming、Sandbox、Model 和 LangGraph Runtime；
- LangGraph 作为 DeerFlow 底层执行引擎，不直接成为 Commerce 业务数据库或 Case 状态来源；
- Subagent 是 Path 的执行形态，不拥有 Case 状态写权限；
- Commerce Lead 是持续 Agent Loop，不是只调用一次的文本综合函数；
- Commerce Domain Event、Run、Checkpoint、Lease/Fencing 仍是业务权威状态；
- deterministic Metric/Capability/Policy 不交给模型计算；
- Verification 使用独立 fresh-context Subagent，不继承 Lead reasoning；
- Multica 是编码 Agent 管理平台，不作为 Commerce 内部推理运行时；
- 不迁移到 DeepAgents 或 Pi Agent，避免在已有 DeerFlow 基础上重复建设 Harness。

Agent 执行拓扑：

```text
用户消息 / Case Event
→ Commerce Lead Loop
→ Capability-first Router
→ 0–3 Path Subagent fan-out
→ 每条 Path 独立 ContextPacket / Tool / Budget / Checkpoint
→ Evidence Barrier（只接收已持久化 Evidence）
→ Lead 更新 Hypothesis
→ Fresh Verification Subagent
→ GoalLoop：answer / continue / replan / wait / action / stop
```

持续问答与完整调查分离：

- 读取已有 Evidence、解释结论和展示来源不启动完整多 Agent Loop；
- 请求新调查角度时只补跑缺失 Path；
- 新数据进入时创建新的 analysis/follow-up Run；
- 质疑结论时可以启动 fresh Verification；
- Action、Approval 和 Follow-up 使用独立 RunType 和状态门禁。

详细理由见 `docs/adr/0005-commerce-uses-deerflow-subagent-runtime.md`。

## 7. 代码边界

### 7.1 通用 Harness 层

目录：`backend/packages/harness/deerflow/`

只放可复用的 Agent Runtime 能力：

```text
runtime/
├── loops/
├── budgets/
├── context/
├── routing/
├── domain_events/
└── verification/
```

规则：

- 不出现 Olist、Seller、Review、Commerce Case 等业务概念；
- 不导入 `app.*`；
- 保留并继续执行 `tests/test_harness_boundary.py`；
- 通用组件通过 Protocol、TypedDict、Pydantic Model 或回调接口扩展。

### 7.2 Commerce 应用层

目录：`backend/app/commerce/`

```text
commerce/
├── domain/
├── data/
├── metrics/
├── anomalies/
├── cases/
├── agents/
├── actions/
├── followups/
├── evals/
├── persistence/
└── api/
```

规则：

- `app.commerce` 可以导入 `deerflow.*`；
- DeerFlow Harness 不反向导入 Commerce；
- 业务模型、业务事件和业务 API 全部留在应用层；
- 使用共享异步数据库 Engine，但 Commerce 维护独立迁移入口；
- Commerce ORM 模型不进入通用 Harness 的业务命名空间。

### 7.3 Eval 数据与报告

目录：`evals/commerce/`

```text
commerce/
├── cases/
├── contracts/
├── datasets/
├── fixtures/
├── experiments/
├── reports/
└── schemas/
```

规则：

- 评测代码可在 `backend/app/commerce/evals/`；
- Case、Fixture、Contract 和 Report 放根目录 `evals/commerce/`；
- 完整 Olist 原始 CSV 不提交 Git；
- 提交下载脚本、版本、License、SHA-256 和小型可连接 fixture；
- 历史 `evals/opensku/` 保留为旧系统证据，不直接改写成新系统结果。

## 8. Harness 关键设计

### 8.1 Case 与 Run 分离

Case 是长期业务对象；Run 是有界执行。

Run 类型：

- `data_intake`
- `case_investigation`
- `action_execution`
- `follow_up`
- `replan`
- `evaluation`

Run 状态：

- `queued`
- `running`
- `waiting`
- `completed`
- `failed`
- `timeout`
- `cancelled`
- `blocked`

Run Phase：

- `profiling`
- `mapping`
- `planning`
- `investigating`
- `synthesizing`
- `verifying`
- `validating_action`
- `awaiting_approval`
- `executing`
- `evaluating_follow_up`

### 8.2 Goal Loop

```text
Assess State
→ Select Evidence Gap
→ Plan Next Path / Tool
→ Execute
→ Normalize Evidence
→ Update Hypotheses
→ Verify Progress
→ Persist Checkpoint
→ Continue / Stop
```

停止原因：

- `goal_achieved`
- `goal_partially_achieved`
- `awaiting_user_input`
- `awaiting_approval`
- `capability_blocked`
- `budget_exceeded`
- `no_new_evidence`
- `policy_blocked`
- `tool_failure`
- `cancelled`

现有 LoopDetection 保留为重复 Tool Call 的安全熔断，不承担 Goal Loop 职责。

### 8.3 Budget

预算维度：

- 最大 Iteration；
- 最大 Tool Calls；
- 最大 Path Agents；
- 最大 Token；
- 最大 Wall Time；
- 最大模型升级次数；
- 最大 Verification Repair 次数；
- 最大重复动作次数；
- 连续无新 Evidence 阈值。

预算必须分层：

- Run 总预算；
- Lead 预算；
- 每个 Path Agent 预算；
- Verification 预算；
- Tool 结果预算。

### 8.4 Retry

错误分类：

- `transient_provider_error`
- `tool_timeout`
- `invalid_structured_output`
- `policy_denied`
- `capability_missing`
- `budget_exceeded`
- `verification_rejected`
- `permanent_tool_error`

规则：

- 网络和临时 Provider 错误允许有限退避重试；
- Schema 错误允许有限 Repair；
- Verification 失败触发 Replan，不原样重试；
- Policy Denied 不自动重试；
- Capability Missing 进入 Partial / Blocked；
- Budget Exceeded 立即终止。

### 8.5 Checkpoint

Checkpoint 保存：

- Goal；
- Loop Iteration；
- 已消耗预算；
- Case / Evidence / Hypothesis 引用；
- 活跃 Path Tasks；
- Model Assignment；
- Skill Versions；
- Context Hash；
- Tool State；
- Wait Reason；
- Resume Token。

不保存：

- API Key；
- 外部系统凭据；
- 模型私有 Chain of Thought；
- 未脱敏敏感数据副本。

## 9. Context Engineering

新增结构：

- `ContextPacket`
- `ContextManifest`
- `EvidenceDigest`
- `PathAssignment`
- `VerificationPacket`

Lead Context：

- Case Header；
- Capability Registry；
- 结构化 Facts；
- Hypothesis 状态；
- Evidence 索引；
- Path Results；
- Budget。

Path Context：

- 独立调查问题；
- 必要 Capability；
- 相关 Evidence；
- 允许工具；
- 输出 Schema；
- Forbidden Claims；
- 局部预算。

Verification Context：

- Final Claims；
- Evidence Bundle；
- Tool Results；
- Capability Boundary；
- Action Contract；
- Policy Contract。

Verifier 不继承 Lead 的完整对话或推理过程。

上下文超预算时按以下顺序裁剪：

1. 过滤不相关 Path；
2. 使用 Evidence ID 和数值摘要；
3. 压缩旧 Iteration 的自然语言；
4. 保留关键数值、公式和来源；
5. 原始行改为按需 Tool 查询；
6. 不压缩 `unknown`、反证和权限约束。

## 10. Memory 分层

- Run Working State；
- Case Ledger；
- Workspace Semantics；
- Outcome Memory；
- Skill Registry；
- User Preferences。

写入规则：

- Observed Fact 只能来自数据或 Tool；
- Derived Metric 只能来自版本化公式；
- Hypothesis 必须标记状态和 Evidence；
- User Confirmed Mapping 单独记录；
- Outcome Memory 只从关闭 Case 中提取；
- Evaluation 模式使用冻结 Memory；
- 跨 Case 检索返回结构化 Pattern，不泄漏隐藏答案；
- Commerce Agent 默认关闭当前通用 Memory 的全量自动注入。

## 11. Dynamic Path Agent

首批 Path Agent：

- `FulfillmentPathAgent`
- `SellerPeerPathAgent`
- `ReviewExperiencePathAgent`

未来只有在数据、评测和业务需求成立时再增加：

- FunnelDiagnosisAgent
- PricingAgent
- CampaignPerformanceAgent
- InventoryDemandAgent
- ProductContentAgent
- RiskComplianceAgent

每个 `PathAgentSpec` 必须声明：

- `path_type`
- `required_capabilities`
- `optional_capabilities`
- `supported_case_types`
- `allowed_tools`
- `skill_id`
- `output_schema`
- `default_model_profile`
- `default_budget`
- `forbidden_claims`

调度规则：

- 默认 0–3 个 Path Agent；
- 简单 Case 可以不启动子 Agent；
- 只有独立证据路径才并行；
- 连续且紧耦合阶段由 Lead / 确定性 Pipeline 处理；
- Verification 使用独立上下文；
- Path Result 必须结构化，不能只返回 Markdown。

## 12. Model Router

模型 Profile：

- `fast_structured`
- `balanced_tool_user`
- `strong_synthesizer`
- `strong_verifier`
- `offline_candidate_builder`

输入特征：

- Role；
- Case Risk；
- Capability 数量；
- Evidence Path 数量；
- Contradiction 数量；
- Output Schema 难度；
- 当前预算；
- Verification 历史；
- 是否需要 Vision；
- 是否需要 Tool Use。

输出：

- Model Profile；
- 实际 Model；
- Effort；
- Token Budget；
- Timeout；
- Reason Codes；
- Router Version。

升级规则：

- 跳步、少查证：提高 Effort / 修 Context / 修 Loop；
- 完整尝试后仍判断错误：升级模型；
- Tool 错误：修 Tool；
- 数据缺失：返回 Unknown；
- 高风险 Action：强 Verifier；
- 最多一次 Model Escalation，最终值由实验确定。

## 13. Domain Event

事件 Envelope：

```yaml
event_id: evt-...
schema_version: 1.0
seq: 1
occurred_at: ...
workspace_id: ...
case_id: ...
run_id: ...
agent_task_id: ...
type: evidence.added
actor: ...
trace_id: ...
parent_event_id: ...
payload: ...
```

事件族：

- `data.*`
- `capability.*`
- `case.*`
- `run.*`
- `loop.*`
- `agent.*`
- `model.*`
- `tool.*`
- `evidence.*`
- `hypothesis.*`
- `verification.*`
- `action.*`
- `approval.*`
- `followup.*`
- `policy.*`
- `skill.*`
- `eval.*`

RunJournal 继续保存底层 LLM / Tool Trace；Domain Event 负责产品状态。两者分开存储，通过 Trace ID 关联。

## 14. Action 与权限

权限等级：

- L0 解释和诊断；
- L1 生成草稿；
- L2 创建内部任务；
- L3 提交审批；
- L4 执行可逆动作；
- L5 高风险动作，必须明确人工确认。

Action 状态：

```text
draft
→ validating
→ policy_checked
→ awaiting_approval
→ approved / rejected
→ executing
→ succeeded / failed
→ monitoring
→ effective / ineffective / inconclusive
→ rolled_back
```

首个真实 Connector 只实现低风险内部任务，不实现自动处罚、自动下架、自动改价或自动投放。

## 15. Evaluation 与 Experiment

Evaluator：

- Deterministic Evaluator；
- Evidence Evaluator；
- Semantic Evaluator；
- Trace / Policy Evaluator；
- Human Calibration。

Hard Gates：

- Metric 错误；
- Unsupported Claim；
- Hidden Data Leakage；
- 权限越界；
- 高风险 Action 无审批；
- Unknown 被伪装为 Fact；
- Verifier False Pass；
- Evidence 引用不存在；
- Tool 越权；
- Checkpoint 不可恢复。

Soft Metrics：

- Evidence Coverage；
- Hypothesis Ranking；
- Action Usefulness；
- Routing Precision / Recall；
- Token；
- Latency；
- Stability；
- Iteration；
- Tool Efficiency。

必须完成的实验：

- 规则系统 vs 单 Agent；
- 单 Agent vs 固定多 Agent；
- 固定多 Agent vs 动态多 Agent；
- 无 Verifier vs 有 Verifier；
- 共享 Context vs Fresh Context；
- One-shot vs Goal Loop；
- 统一模型 vs 角色级模型；
- 低/中/高 Effort；
- Prompt-only vs Skill Contract。

模型选择使用 Hard Gate + Pareto Frontier，不使用单一总分。

### 15.1 真实模型测试红线

所有触达 LLM 或 Agent 行为的测试必须使用真实 DeepSeek V4，不允许使用 Mock、Fake、Stub、录制回放或其他模型作为通过依据。

适用范围：

- Lead Agent；
- Path Agent；
- Dynamic Path Routing 中的模型判断；
- Model / Effort Escalation；
- Tool Selection；
- Structured Output Repair；
- Verification；
- Semantic Evaluator；
- Skill Candidate Generation；
- Agent Integration Test；
- Gold Case End-to-End；
- Experiment Run；
- Release Gate。

纯确定性测试保持无模型：

- Domain Model；
- State Transition；
- Metric 计算；
- Capability 依赖；
- Repository；
- Event Serialization；
- Budget 原子消费；
- Policy 规则；
- 数据质量和 Join。

纯确定性测试不得为了形式要求无意义地调用模型，但也不得使用假模型代替真实 Agent 调用。只要被测路径会调用模型，该测试就必须发起新鲜的真实 DeepSeek V4 请求。

当前本地配置别名为：

```text
deepseek-reasoner
```

Provider：

```text
deerflow.models.patched_deepseek:PatchedChatDeepSeek
```

Endpoint：

```text
https://api.deepseek.com/v1
```

执行前必须增加 `real_model_preflight`：

1. 检查 `$DEEPSEEK_API_KEY` 是否可用，但不打印或记录密钥；
2. 发起最小真实请求；
3. 记录服务端返回的模型身份、请求 ID、时间、Token 和响应状态；
4. 确认实际服务模型为 DeepSeek V4；
5. 禁止自动回退到其他 DeepSeek 版本或其他厂商模型；
6. 无法确认模型版本时停止；
7. 额度不足、认证失败、限额不可恢复或服务不可用时停止。

2026-07-20 实施状态：

- [x] `backend/app/commerce/evaluation/real_model_preflight.py` 已实现；
- [x] 官方 `https://api.deepseek.com/v1` 新鲜请求已返回 `deepseek-v4-flash`；
- [x] Provider Request / Response ID、Token、Latency、Retry、Stop Reason、Fingerprint 与版本元数据已进入不可覆盖审计；
- [x] 每次请求注入唯一 nonce，LangChain 响应缓存与 SDK 自动重试显式关闭，只保存 nonce / 响应 SHA-256；
- [x] 缺密钥、鉴权、额度、服务、身份或遥测时失败关闭，真实模型测试不 Skip、不回退；
- [x] 门禁已接入 Semantic LLM Candidate 与首个 FulfillmentPathAgent；
- [x] SellerPeer / ReviewExperience / Lead / Verification 独立真实门禁已接入；
- [x] 多 Path Worker 已接入持续 Lead transaction；
- [x] 四条 Gold Case 的统一 fresh V4 synthesis/semantic Holdout 已通过；
- [x] 四条 Gold Case 的统一完整 Agent Investigation Run E2E 已通过：14 条唯一 fresh Agent Provider 请求、`71,478` Agent Tokens、全部 `deepseek-v4-flash`、retry `0`；Action/Approval/Follow-up 不属于该调查门禁。

阻塞状态：

- `blocked_real_model_unavailable`
- `blocked_real_model_identity_unverified`
- `blocked_real_model_quota_exhausted`
- `blocked_real_model_auth_failed`

相关测试不得被标记为 PASS、不得静默 Skip、不得用历史响应替代。历史 Trace 可以用于 Debug 和离线分析，但不能作为当前版本 Release Gate 的通过证据。

每个真实模型测试结果必须保存：

- 配置的模型别名；
- 服务端返回的实际模型标识；
- Provider Request ID；
- Prompt / Skill / Context / Router 版本；
- Input / Output Token；
- Latency；
- Retry；
- Stop Reason；
- Evaluation Result。

为控制费用，可以缩小测试集合、分层运行和设置预算，但不能把真实模型替换成 Mock。测试预算耗尽时停止执行并报告，不降低评测标准。

## 16. Skill Evolution

禁止 Active Agent 直接修改 Active Skill。

生命周期：

```text
candidate
→ offline_evaluated
→ shadow
→ active
→ deprecated / rolled_back
```

流程：

```text
Failure Cluster
→ Playbook Candidate
→ Skill Candidate
→ Security Scan
→ Development Eval
→ Regression
→ Holdout
→ Human Review
→ Shadow
→ Active / Reject / Rollback
```

当前 `skill_manage` 只保留为开发/管理员工具；Commerce Lead 使用 `propose_skill_candidate`，只能创建不可变 Candidate。

## 17. 前端目标

### 17.1 统一 Shell

Codex-inspired Commerce Agent Workspace：

```text
左：Case Inbox / Data / Runs / Skills
中：Case Investigation Timeline + Case-bound Composer
右：Evidence / Hypothesis / Action / Data / Run
底部：Runtime Drawer
```

### 17.2 页面

- Overview
- Data Inbox
- Capability / Data Quality Report
- Case Queue
- Case Detail
- Evidence Explorer
- Case-bound Chat
- Action Center
- Follow-up Timeline
- Agent Run
- Skills & Evals
- Settings / Connectors
- War Room

### 17.3 强制设计流程

每一页，包括 War Room：

```text
产品任务与状态矩阵
→ Image Generation 高保真稿
→ 用户评审
→ 组件与事件契约
→ TDD 实现
→ 浏览器截图
→ 与设计稿对比
→ 功能、视觉、响应式 QA
```

先生成统一 Codex 式母版，再逐页生成；不能每页独立随机生成。

### 17.4 War Room

War Room 是同一个 Run 的视图，不是独立产品：

- Timeline View；
- Graph View；
- War Room View。

三种视图读取同一个 Domain Event Stream。

无事件时不播放假忙碌；角色、工具台、证据板、审批区和警报都由真实事件驱动。

## 18. 实施阶段

所有功能与 Bug 修复遵守：

```text
RED：先写失败测试并确认失败
GREEN：最小实现通过测试
REFACTOR：清理结构并保持测试通过
VERIFY：运行相关测试和诊断
REVIEW：阶段评审
```

### Phase 0：保护与基线

已完成：

- [x] 审计脏工作区；
- [x] 排除完整原始数据、数据库、环境和密钥；
- [x] 创建归档分支；
- [x] 创建保护快照 `9144237`；
- [x] 创建 `feature/commerce-case-agent`。

待执行：

- [x] 记录 DeerFlow 上游 Remote、本地压平导入提交和审计日上游 HEAD；原始精确上游基线 SHA 因无父导入不可恢复，已如实记录；
- [x] 建立新系统 Backend / Frontend Feature Flag，默认关闭；
- [x] 记录当前 Backend / Frontend 确定性、静态和类型基线；
- [x] 将旧 OpenSKU 评测、知识和 Demo 标记为 Legacy，不删除。

退出条件：

- 可随时切回归档分支；
- 新分支基线测试结果已记录；
- 新旧系统命名空间不冲突。

### Phase 1：Domain Contract 与 Gold Case

完成状态：

- [x] Commerce 包骨架与 Harness / App 边界；
- [x] 基础枚举、强类型 ID 和 Case 状态转换；
- [x] Fact / MetricObservation / Evidence；
- [x] Case / Hypothesis / Action / Approval / Rollback；
- [x] Gold Case Input / ExpectedBehavior 隔离合同；
- [x] 三条基础 Olist Gold Case Fixture；
- [x] 一条独立多卖家 Peer Cohort Gold Case Fixture；
- [x] SHA、行数、列、Join、时间窗口和精确指标回归。

#### Task 1.1：Commerce 包骨架

RED：

- 新增测试验证 `app.commerce` 可导入；
- 验证 `deerflow.*` 不导入 `app.commerce`。

GREEN：

- 创建 `backend/app/commerce/` 子包；
- 创建 `domain`、`data`、`metrics`、`agents`、`persistence`、`api`。

VERIFY：

```bash
cd backend
PYTHONPATH=. uv run pytest tests/test_harness_boundary.py tests/commerce/test_package_boundary.py -v
```

#### Task 1.2：基础枚举和 ID

RED：测试非法状态、非法 ID 和不允许的状态转换。

GREEN：实现：

- SemanticStatus；
- CaseStatus；
- RunType；
- RunPhase；
- ActionStatus；
- ApprovalStatus；
- FollowUpOutcome；
- Typed IDs。

#### Task 1.3：Fact / Metric / Evidence

RED：

- Observed Fact 必须有 Source；
- Derived Metric 必须有 Formula Version；
- Evidence 必须引用 Fact / Metric；
- Unknown 不允许携带伪造值。

GREEN：最小 Pydantic Domain Model。

#### Task 1.4：Case / Hypothesis / Action

RED：

- Hypothesis 必须有状态；
- Action 必须有 Evidence、Risk、Approval 和 Rollback；
- 高风险 Action 不允许直接 executed；
- Case 状态转换必须合法。

GREEN：实现 Domain Model 和 Transition Service。

#### Task 1.5：Gold Case Contract Schema

RED：

- 缺 required facts 的 Contract 无效；
- Hidden Labels 不能进入 Input Bundle；
- Forbidden Claim 必须可机器读取；
- Capability Ablation 必须产生不同 Capability。

GREEN：实现 EvaluationCase / InputBundle / ExpectedBehavior。

#### Task 1.6：三条基础 Gold Case Fixture

RED：验证 Fixture 可连接、时间窗口正确、样本数正确。

GREEN：添加：

- GC-FULFILLMENT-001；
- GC-REVIEW-002；
- GC-CAPABILITY-003。

退出条件：

- 三条基础 Case 的确定性事实能够在无 LLM 条件下复算；
- Contract 和 Input 完全隔离；
- 所有 Domain Contract 测试通过。

### Phase 2：Data Intake 与 Capability

当前完成状态：

- [x] CSV / JSON / JSONL / Excel / ZIP 安全接入与只读原始文件；
- [x] Schema、质量、主键、时间、范围、重复、前导零和 Join 风险 Profiler；
- [x] 确定性 Semantic Mapper 与 Workspace 用户确认持久化；
- [x] Real DeepSeek V4 Preflight 与不可覆盖审计；
- [x] DeepSeek V4 低置信度语义候选层（只生成 Candidate，必须显式确认，不自动修改 Active Mapping）；
- [x] Capability Registry 与 GC-CAPABILITY-003 Ablation；
- [x] Olist Adapter 与 Entity-scoped Normalized Facts；
- [x] 首批 Metric Registry 与 Gold Case 时间窗复算；
- [x] 多卖家 Peer Baseline 和 Geographic Metric 执行；
- [x] Anomaly Detector、最小样本、严重度、置信度、去重和 Case Candidate Merge。

#### Task 2.1：Input Bundle

- 支持 CSV / JSON / Excel / ZIP Manifest；
- 文件名、大小、Hash、编码、表名可追踪；
- 原始文件只读保存；
- 禁止路径穿越。

#### Task 2.2：Profiler

测试并实现：

- 类型推断；
- 缺失率；
- 唯一率；
- 主键候选；
- 时间字段；
- 数值范围；
- 重复行；
- ZIP 前导零；
- 一对多风险。

#### Task 2.3：Semantic Mapper

测试并实现：

- 标准字段候选；
- 置信度；
- 确定性规则优先；
- LLM 只生成候选；
- 低置信度需要确认；
- 用户确认持久化为 Workspace Semantics。

#### Task 2.4：Capability Registry

测试并实现：

- Capability 的 required fields；
- available / unavailable / partial；
- reason code；
- Capability 依赖图；
- GC-CAPABILITY-003 跳过 Review。

#### Task 2.5：Normalized Facts

- 不创建万能宽表；
- 保留原始字段、标准字段、Source 和版本；
- Olist Adapter 只负责适配，不污染通用模型。

#### Task 2.6：Metric Registry

首批指标：

- order_count；
- late_delivery_rate；
- handling_time；
- transit_time；
- delivery_duration；
- review_score；
- low_rating_rate；
- peer baseline；
- geographic segment。

#### Task 2.7：Anomaly Detector

- 最小样本门槛；
- Baseline Window；
- Current Window；
- Peer Comparison；
- Severity；
- Confidence；
- 去重和 Case Merge。

退出条件：

- 完整 Olist 可通过下载脚本复现；
- 四条 Gold Case 的 Capability 和 Metric 全部确定性通过；
- 小样本不会产生高置信度严重异常。

### Phase 3：Case Persistence、API 与 Domain Events

2026-07-18 第一子阶段实施状态：

- [x] 应用层 `CommerceBase`、`commerce_*` ORM 表与共享异步 Session Factory 合同；
- [x] 独立 Alembic 入口与独立 `commerce_alembic_version`；
- [x] SQLite 实际迁移 / Repository 测试与 PostgreSQL DDL 编译；
- [x] Workspace-scoped Case Create / Get / List / Save；
- [x] Optimistic Concurrency 与失败事务回滚；
- [x] Case / Run 双 Sequence、Schema Version、Trace / Correlation / Causation；
- [x] Case 状态写入与 Domain Event 同事务 Unit of Work；
- [x] Event Replay 重建 Case Projection；
- [x] Append-only Evidence 与 versioned Hypothesis Repository（Supporting / Contradicting Evidence、Fact / MetricObservation 来源追踪）；
- [x] Action / Approval / Follow-up Repository；
- [ ] PostgreSQL 真实实例集成测试；
- [x] Commerce API 与 Feature Flag Router：Data Intake / Profile / Capability、Semantic Candidate、Anomaly-to-Case、Case/Evidence/Hypothesis/Event、Investigation/Run、Action/Approval/Execution/Rollback/Follow-up 与 Skill Candidate。

#### Task 3.1：Commerce Persistence

- 共享异步 Engine；
- Commerce ORM Model；
- 独立 Migration Entry；
- SQLite 和 PostgreSQL 兼容；
- Repository Protocol。

#### Task 3.2：Case Repository

- Create；
- Get；
- List / Filter；
- Status Transition；
- Reopen；
- Optimistic Concurrency。

#### Task 3.3：Evidence / Hypothesis Repository

- [x] Append-only Evidence；
- [x] Hypothesis Version；
- [x] Supporting / Contradicting；
- [x] Source Traceability；
- [x] Evidence / Hypothesis 与 Case、Domain Event 的同事务 Unit of Work；
- [x] Case Projection Replay 对记录事件的 `case_version` 支持。
- [x] Case → Dataset / Entity / Window / Analysis Artifact Lineage；

#### Task 3.4：Domain Event Store

- [x] Event Envelope；
- [x] Case Sequence；
- [x] Run Sequence；
- [x] Schema Version；
- [x] Trace Correlation；
- [x] Replay Projection。

#### Task 3.5：Commerce API

首批 API：

- [x] Data Upload / Profile；
- [x] Capability Report；
- [x] Semantic Mapping read / explicit Workspace confirmation API；
- [x] Real DeepSeek V4 semantic-candidate API with telemetry and fail-closed identity gate；
- [x] Deterministic Anomaly-to-Case analysis API with immutable derived snapshot and Case/Event Replay；
- [x] Explicit user Case API：无 temporal anomaly 时仍可用 requested Paths 创建真实 Case，不伪造异常；
- [x] Case List；
- [x] Case Detail；
- [x] Case Lineage Detail；
- [x] Evidence List / Detail；
- [x] Latest Hypothesis List；
- [x] Case Domain Event Stream；
- [x] Anomaly-to-Case analysis；
- [x] Idempotent Investigation Start；
- [x] Case Run List / Run Detail / Checkpoints / Events。

当前 API slice 通过 `COMMERCE_CASE_AGENT_ENABLED` fail-closed 挂载，并要求 `X-Commerce-Workspace-Id`。在 Workspace membership 合同完成前，不满足多租户生产发布退出条件。Investigation Start 只创建诚实的 `queued` Run；首条 fenced Fulfillment→Lead→Verification Worker Loop 已实现，但 API 调度入口、跨进程 continuation 和自动 reconciliation 仍未实现。

退出条件：

- 无 Agent 时也能完成 Upload → Capability → Anomaly → Case；
- Case 可以通过 API 和事件流完整展示；
- 事件 Replay 可重建 Case Projection。

### Phase 4：Agent Harness 与 Goal Loop

当前完成状态：

- [x] Lead / Path / Verification ContextPacket 与 ContextManifest；
- [x] Persisted Case → verified initial Lead ContextPacket Loader；
- [x] Canonical Context hash、token estimate 与初始零消耗 Checkpoint；
- [x] Dataset/Artifact/Capability/Case-reference fail-closed guards；
- [x] Hidden evaluation label leakage guard；
- [x] 三条 versioned PathAgentSpec；
- [x] Capability-first DynamicPathRouter（0–3 Path、Reason Codes）；
- [x] 并发安全多维 BudgetManager 与原子拒绝；
- [x] ModelRouter 与 Assignment Event；
- [x] GoalLoopController / Checkpoint Contract / Stop Condition；
- [x] Structured PathResult；
- [x] 真实 DeepSeek V4 FulfillmentPathAgent 行为测试；
- [x] Fenced Worker Fulfillment step：pre/post Checkpoint、Event、Budget、Evidence；
- [x] 真实 DeepSeek V4 LeadSynthesis：Path Evidence → traceable diagnostic claims；
- [x] Fresh-context Verification：supported claim pass + causal overclaim reject；
- [x] Worker Lead → Hypothesis → Verification persistence / GoalLoop terminal integration；
- [x] SellerPeer Path Agent 真实 Tool + DeepSeek V4 行为测试；
- [x] ReviewExperience Path Agent 真实 Tool + DeepSeek V4 行为测试。
- [x] Explicit Case Trigger / requested Paths / outcome-agnostic Peer Policy 合同与 API；
- [x] 413 个非 live Commerce 确定性回归通过，23 个真实模型测试明确 deselect；
- [x] DeerFlow CommerceSubagentAdapter / Committer / Supervisor Gate A-C；
- [x] 三条 Path 的 Subagent Runtime 迁移：Fulfillment、SellerPeer、ReviewExperience 均有 versioned Spec、fresh V4 gate 与 Case-scoped execution；
- [x] 多 Path fan-out / Evidence Barrier：0–3 独立 Task 并行、terminal join、partial success、unknown external outcome 与生产 Investigation 接线；
- [x] 持续 Commerce Lead Agent Loop；
- [x] Fresh Verification Subagent 接入新 Loop；
- [x] Verification Claim-to-Evidence 合同支持 Fact/VOC-backed Claim，服务器双向补全 Evidence / Fact / Metric lineage 并拒绝越界与跨 Claim 绑定；
- [x] ReviewExperience 使用 `review_metrics` / `late_delivery_metrics` / `voc_excerpts` 语义 scope，由服务器映射 opaque IDs；
- [x] Explicit-user Fulfillment 允许无伪造 Anomaly 的 baseline/current 快照对比，检测型 Case 仍要求 Anomaly；
- [x] Provider sync/async client lifecycle 显式关闭，完整 Gate 不再出现 event-loop teardown 错误；
- [x] Distinct idempotent Replan Run；
- [x] Fresh verified Action Planner 接入固定内部 Catalog。

#### Task 4.1：ContextPacket

- [x] Lead Packet；
- [x] Path Packet；
- [x] Verification Packet；
- [x] ContextManifest；
- [x] Token Budget；
- [x] Hidden Label Leakage Test。
- [x] CaseLineage / Artifact SHA-256 / Dataset Manifest Loader；
- [x] Workspace / Case / Dataset / Seller / Window identity validation；
- [x] Capability reload and exact consistency validation；
- [x] Evidence / Hypothesis / Fact / Metric membership validation；
- [x] Compact metric/anomaly digests without raw Dataset rows；
- [x] Canonical JSON context hash and deterministic token estimate；
- [x] Initial GoalLoopState and safe zero-usage Checkpoint。

#### Task 4.2：PathAgentSpec

- [x] Required Capability；
- [x] Allowed Tools；
- [x] Skill Version；
- [x] Output Schema；
- [x] Budget；
- [x] Model Profile。

#### Task 4.3：DynamicPathRouter

- [x] 规则优先；
- [x] 0–3 Path Agent；
- [x] 不满足 Capability 时 Skip；
- [x] 记录 Reason Codes；
- [x] GC-REVIEW-002 不启动 Fulfillment；
- [x] GC-CAPABILITY-003 不启动 Review。
- [x] 从持久化 explicit Case trigger 恢复 requested Paths；
- [x] SellerPeer 显式请求必须携带 outcome-agnostic PeerCohortPolicy。

#### Task 4.4：ModelRouter

- [x] Profile Binding；
- [x] Effort；
- [x] Upgrade Policy；
- [x] Assignment Event；
- [x] Budget Integration。

#### Task 4.5：BudgetManager

- [x] Run / Agent / Tool / Verification 可配置预算合同；
- [x] 原子消费；
- [x] 并发安全；
- [x] Budget Exceeded Event Contract。

#### Task 4.6：GoalLoopController

- [x] Iteration；
- [x] Progress Signal；
- [x] Stop Condition；
- [x] Partial Goal；
- [x] No New Evidence；
- [x] Safe Checkpoint Contract；
- [x] Durable Checkpoint Persistence；
- [x] WAIT / Resume / CANCEL（Task 4.10）。

#### Task 4.7：Structured PathResult

- [x] Observations；
- [x] Evidence；
- [x] Supported / Contradicted Hypotheses；
- [x] Unknowns；
- [x] Suggested Next Path；
- [x] Cost / Trace。

#### Task 4.8：首批 Path Agents

按照 TDD 分别实现：

- [x] FulfillmentPathAgent：verified minimal Path Context、real V4 structured output、traceable Evidence、model/config audit；
- [x] SellerPeerPathAgent：outcome-agnostic peer cohort、geography Tool traces、real V4 structured output；
- [x] ReviewExperiencePathAgent：review/low-rating/late-rate metrics、脱敏 VOC Tool traces、real V4 structured output 与非因果/非法结论门禁；

#### Task 4.9：VerificationEngine

- [x] Fresh Context without Lead reasoning；
- [x] Deterministic Metric digest context；
- [x] Claim-Evidence and MetricObservation membership；
- [x] Causal Language rejection；
- [x] Capability Boundary；
- [x] Policy constraints；
- [x] Reject / Repair / Pass contract；
- [x] Fresh real DeepSeek V4 behavior gate；
- [x] Worker persistence and explicit reject/repair → replan-required integration。

#### Task 4.9A：LeadSynthesisAgent

- [x] Fresh persisted Path Evidence context；
- [x] Structured claims / unknowns / suggested next Paths；
- [x] Claim Evidence membership validation；
- [x] System-derived stable Hypothesis IDs；
- [x] Critical Case `strong_synthesizer / high` escalation；
- [x] Fresh real DeepSeek V4 behavior gate；
- [x] Worker Hypothesis version persistence；
- [x] Fresh Verification hand-off without Lead reasoning；
- [x] Reject / repair / replan GoalLoop integration。

#### Task 4.10：Checkpoint / Resume

- [x] Append-only safe Checkpoint persistence and read API；
- [x] Fenced Worker lease / heartbeat / expired-lease takeover；
- [x] Latest Checkpoint returned on lease reacquisition；
- [x] Initial Checkpoint construction and fenced persistence contract；
- [x] Atomic model.assignment / path.started / pre-call Checkpoint；
- [x] Lease-guarded Agent Evidence persistence into Case and Run streams；
- [x] Actual token / wall-time / Path / iteration budget accounting；
- [x] Atomic path.completed / post-call Checkpoint；
- [x] Restart Resume classification：initial / unknown external outcome / partial Evidence / completed / invalid；
- [x] Existing Checkpoint blocks automatic external model retry；
- [x] User Clarification WAIT / Resume 基础合同；
- [x] Mapping Confirmation Resume：批量预校验、单次原子 Semantic Store 替换、Human Actor、幂等 Receipt、Capability refresh；
- [x] Approval Wait Resume：Wait Checkpoint 与 `lead.waiting` 对齐，只有持久化 `waiting -> running` 且更高 fencing token 后才继续；Action Approval 仍使用独立结构化生命周期；
- [x] Tool Failure Resume：旧失败 Run 不复活，只允许从明确 `tool_failure` Investigation 创建独立 Replan Run；
- [x] Process Restart state reconstruction and retry-risk classification；
- [x] Process Restart continuation for WAIT/Resume and terminal Path scope reconstruction；
- [x] General unknown-external-outcome reconciliation execution：验证部分 Evidence，持久化 `path.blocked / run.reconciled / post-checkpoint`，旧 Run 结束为 Blocked，重试必须进入独立 Replan；Checkpoint 与 Run projection 间再次崩溃可恢复且不重复 terminal Event。

#### Task 4.11：CommerceSubagentAdapter

- [x] Gate A - 纯边界合同：定义 `CommerceAgentTask`、`CommerceSubagentOutcome` 和状态映射；
- [x] Gate A - 任务只携带 Run/Case/Path/Context hash/Budget/Skill/Model/Fencing/Trace 引用，不携带 Lease secret；
- [x] Gate A - Adapter 只构造最小 Prompt、`SubagentConfig`、`SubagentExecutor` 并校验 `PathResult`，不得持有 Repository/UoW；
- [x] Gate A - Provider ID、实际模型身份、Token、Latency、Retry、Stop Reason 等受保护字段只能由 Harness runtime 组装，模型不得自证或覆盖；
- [x] Gate A - `task` 永久进入 disallowed tools，Path allowlist 之外的 Tool 不得注入 Subagent；
- [x] Gate A - task ID、PathType、Context hash、ModelAssignment、SkillVersion、SchemaVersion 任一不一致时 fail closed；
- [x] Gate A - PENDING/RUNNING/COMPLETED/FAILED/CANCELLED/TIMED_OUT 显式映射，非法 JSON/Schema 不得伪装为 completed；
- [x] Gate B - 异步生命周期：start/poll/cancel/timeout/cleanup，Commerce AgentTaskId 与 DeerFlow task ID 一一对应；
- [x] Gate B - Commerce Run 映射到 DeerFlow Thread/Run projection，但不改变 Domain Source of Truth；
- [x] Gate C - 独立 Committer 在 lease/fencing 与 optimistic concurrency 下提交 Evidence/Event/Checkpoint；Adapter 不直接写 Case/Evidence；
- [x] Gate C - 将 DeerFlow Task/Tool/Path 结构化状态映射为真实 Commerce Domain Event，禁止从文本猜状态；
- [x] Gate D - Provider middleware 接入 fresh DeepSeek V4 preflight、服务端身份、Provider ID、Token、Latency、Retry 和 Stop Reason 门禁；
- [x] Gate D - cancellation、timeout、heartbeat、stale fencing、process restart reconciliation 的确定性运行合同测试；Fulfillment Subagent 已通过 fresh DeepSeek V4、Gold Case、parity 与 fenced persistence live gate；
- [x] Harness boundary：`deerflow.*` 不导入 `app.commerce.*`。

#### Task 4.12：Path Subagent Fan-out

- [x] 先只将 Fulfillment 包装为 versioned DeerFlow SubagentSpec；
- [x] Fulfillment 通过 deterministic contract、fresh DeepSeek V4、Gold Case 和旧 Worker parity；迁移期间旧 Worker 仍保留为基准。
- [x] 将另外两条已验收 Path 行为包装为 versioned DeerFlow SubagentSpec，并通过 deterministic contracts 与 standalone fresh DeepSeek V4 Gold Case gates；
- [x] 每个 Path 使用独立最小 ContextPacket、Tool allowlist、Skill 和 Budget；
- [x] Router 只启动 Capability 可用或用户显式请求且合同完整的 Path；
- [x] 同一 Run 下 0–3 Path 并行执行并接入真实 Case-scoped Coordinator；
- [x] 每条 Path 独立 pre/post Checkpoint 与 AgentTaskId；
- [x] 一个 Path blocked/failed 不抹除其他 Path 已完成 Evidence；
- [x] Evidence 持久化基础能力通过 lease/fencing、optimistic concurrency 和 Path 级原子事务；
- [x] Evidence Barrier 等待所有 selected Path 进入 completed/blocked/failed；
- [x] 记录 fan-out wall time、单 Path latency、tokens 和 critical path。

#### Task 4.13：持续 Commerce Lead Agent Loop

- [x] Lead observe：只读取持久化 Case/Event/Evidence/Hypothesis/Checkpoint，并从 terminal Path Event 恢复 ID-only Evidence Scope；
- [x] Lead act：调用 deterministic Tool 或创建受约束 Subagent Task；
- [x] Lead 不直接生成或修改 Metric；
- [x] 读取已有结论的追问走 fresh V4 read-only answer，不重跑 Path、不新增 Hypothesis，并使用 answer/fast_structured 绑定；
- [x] 新调查角度创建独立、幂等 Replan Run，只补跑缺失 Path；
- [x] 用户澄清进入 WAITING/Resume，持久化 wait reason/Checkpoint、释放 Lease，并以更高 fencing token 恢复；
- [x] 每轮必须有 Goal、Budget、Progress Signal、Checkpoint 和 Stop Condition；
- [x] 连续无新 Evidence、预算耗尽、能力不足或用户取消时停止。

#### Task 4.14：Fresh Verification Subagent

- [x] 从持久化 Evidence 和 deterministic Metric 重建 fresh packet；
- [x] 不包含 Lead reasoning、隐藏 label 或未持久化中间消息；
- [x] 验证 Claim-Evidence、Metric membership、Capability 和 Policy；
- [x] pass/reject/repair 显式更新 Hypothesis 新版本；
- [x] reject/repair 进入 Replan，不允许静默转成 pass。

#### Task 4.15：渐进迁移与等价门禁

- [x] 现有 Fulfillment Worker Loop 保留为迁移基准；
- [x] 新 Subagent Loop 通过相同 Gold Case 和真实模型门禁；
- [x] 对比旧/新 Evidence coverage、tokens、latency、failure semantics；
- [x] 新链路通过前不删除旧链路；
- [ ] 新链路通过后移除角色专用 Worker 编排，保留通用 Adapter；
- [x] README/ADR 明确 DeerFlow 上游与 Commerce 新增能力。

退出条件：

- 四条 Gold Case 可以通过 Goal Loop 完成；
- Agent 路由与 Capability 一致；
- Verification 能拒绝故意注入的错误结论；
- Run 可以从 Checkpoint 恢复；
- Token、Latency 和 Tool Call 可追踪。

### Phase 5：Action、Approval 与 Follow-up

#### Task 5.1：Action Validator

- [x] Schema；
- [x] Preconditions；
- [x] Evidence；
- [x] Risk；
- [x] Permission；
- [x] Rollback；
- [x] Expected Signals。

#### Task 5.2：Policy Gate

- [x] L0–L5；
- [x] Tool Allowlist；
- [x] Connector Policy；
- [x] High-risk Approval；
- [x] Policy Denied 不重试。

#### Task 5.3：Approval API

- [x] Approve；
- [x] Modify；
- [x] Reject；
- [x] Audit Log；
- [x] Idempotency。

#### Task 5.4：Internal Task Connector

只实现可逆低风险动作：

- [x] 创建内部调查任务；
- [x] 创建监控规则；
- [x] 导出审计 Cohort 与请求缺失数据；
- [x] 记录真实 Artifact、哈希、执行结果和 fenced Run；
- [x] 支持取消、禁用、归档和可验证 Rollback；
- [x] 外部商家写操作 fail closed。

#### Task 5.5：FollowUp

- [x] 新数据触发；
- [x] 重新计算指标；
- [x] target met / not met / unknown 与 `inconclusive` Outcome；
- [x] Case Close / Reopen / 保持调查；
- [x] 不伪造因果归因。

退出条件：

- Action 从 Draft 到 Follow-up 有完整审计；
- 高风险 Action 无法绕过人工；
- Follow-up 能正确输出 `inconclusive`。

### Phase 6：Eval、Experiment 与 Skill Evolution

#### Task 6.1：Evaluation Runner

- [x] Frozen Input；
- [x] Frozen Config；
- [x] Real DeepSeek V4 Preflight；
- [x] Actual Model Identity；
- [x] Provider Request ID；
- [x] Multiple Repetitions；
- [x] Fresh Real-model Request；
- [x] Raw Output hash / audit boundary；
- [x] Trace；
- [x] Token；
- [x] Latency。

#### Task 6.2：Deterministic Evaluator

- [x] Metric；
- [x] Capability；
- [x] Routing；
- [x] Schema；
- [x] Budget；
- [x] Policy。

#### Task 6.3：Evidence / Semantic Evaluator

- [x] Required Fact；
- [x] Forbidden Claim；
- [x] Unknown；
- [x] Causal Language；
- [x] Action Usefulness；
- [x] Structured Reason。

#### Task 6.4：Trace Evaluator

- [x] Agent Path；
- [x] Tool Call；
- [x] Duplicate Call；
- [x] Checkpoint；
- [x] Model Assignment；
- [x] Verification Repair。

#### Task 6.5：Experiment Registry

- [x] Control / Candidate；
- [x] Hypothesis；
- [x] Controlled Variables；
- [x] Split；
- [x] Results；
- [x] Decision；
- [x] Reproduction Command。

#### Task 6.6：架构实验

按既定实验矩阵执行，禁止预填数字。

- [x] 单 Case 微实验暴露 Candidate Token Pareto 回归；
- [x] Semantic Judge 因果措辞漏检修复后重跑；
- [x] 三 Gold Case × Control/Candidate × 2 repetitions Holdout；
- [x] 四 Gold Case 统一 Synthesis / Semantic Eval Release Gate；
- [x] 四 Gold Case 统一完整 Agent Investigation Run Release Gate；
- [ ] 外部 Connector / PostgreSQL / 前端 E2E 架构实验。

#### Task 6.7：Skill Candidate Registry

- [x] Immutable Candidate；
- [x] Base Version；
- [x] Content Hash；
- [x] Security Scan；
- [x] Eval Status；
- [x] Shadow；
- [ ] Human Review；
- [ ] Promotion；
- [x] Active Pointer / Rollback release transaction、幂等 receipt 与 pointer-write failure recovery；真实 Candidate 的人工 Promotion 仍需用户授权。

#### Task 6.8：替换 Runtime Skill Manage

- [x] Commerce Lead 不允许直接 Skill Edit；
- [x] 新增 propose candidate；
- [x] Candidate API 不接受客户端伪造状态、内容哈希或 Active Pointer；
- [x] Active Pointer 只能由显式 Promotion 流程修改；
- [ ] Human reviewer 通过后执行首次 Promotion / Rollback 演练。

退出条件：

- 所有重要架构决定有 Experiment ID；
- Skill 无法绕过 Eval 直接 Active；
- 旧系统的 530/530 语义误判不会在新 Gate 中通过。

### Phase 7：前端设计与实现

每个页面单独执行：

1. 写用户任务和状态矩阵；
2. 使用统一母版调用 Image Generation；
3. 保存高保真稿；
4. 用户评审；
5. 写组件和事件契约；
6. 先写失败测试；
7. 最小实现；
8. 浏览器交互验证；
9. 截图对比；
10. 视觉和响应式 QA。

页面实现顺序：

1. [x] Master Shell：中文 View Model / strict API contract / React / desktop + mobile browser QA；
2. [x] Case Detail：v1 因默认层级偏多归档；v2 已完成 Image Generation、用户确认、确定性 Analysis/Action 读模型、React、真实 Olist 数据联调、桌面/移动浏览器与截图 QA；
3. [x] Data Inbox：已完成可恢复 Dataset List / Detail、完整性 fail-closed、Dataset-scoped Semantic Confirmation、中文 React 上传审核态、真实浏览器机械交互与截图 QA；
4. [x] Capability Report：已完成 Image Generation、Dataset/Capability/Semantic Mapping 纯投影、空态与错误态、中文 React、单一顶栏刷新、桌面/移动浏览器交互与截图 QA；
5. [x] Case Queue：已完成 Image Generation、Case List 分组/筛选/搜索、独立导航状态、Capability 预选路径、Explicit Case 创建侧栏、内容寻址幂等回放、无异常标题保护、桌面/移动浏览器交互与截图 QA；
6. [x] Evidence Explorer：已完成 Image Generation、支持/矛盾/未知同级筛选、Metric/Fact/Hypothesis 对象引用、证据边界、中文 React、Composer 页面边界和桌面/移动截图 QA；
7. [x] Action Center：已完成 Image Generation、跨 Case Action Queue、严格 Action/Approval/Artifact/Follow-up 合同、证据/参数/策略/回滚详情、批准/拒绝/执行/回滚主路径、中文 React 和桌面/移动截图 QA；Approval modify 通用编辑仍列入后续闭环交互；
8. [x] Agent Run：已完成 Image Generation、跨 Case Run Queue、Run Detail/Event/Checkpoint 严格合同、三 Path 同级 fan-out、Evidence Barrier 确定性派生、模型遥测/预算/Checkpoint/事件流工程详情、中文 React、桌面/移动浏览器交互与截图 QA；当前浏览器场景为 Mock API 机械验证，不计作真实 DeepSeek V4 Agent 前端 E2E；
9. [x] Skills & Evals：已完成 Image Generation、Candidate/Experiment/Active Pointer 严格合同、候选评测依据读 API、七阶段演进门禁、Control/Candidate Pareto、Shadow Run 边界、人工激活/回滚机械路径、中文 React 和桌面/移动截图 QA；真实 Candidate 仍保持 shadow，未执行真实 Human Review；
10. War Room；
11. Follow-up；
12. Overview。

前端退出条件：

- 所有活动来自 Domain Event；
- 无假 Agent 活动；
- Chat 绑定 Case；
- Evidence 可追溯；
- Action 可审批；
- Engineer View 可查看 Model、Skill、Tool、Token、Latency、Retry 和 Checkpoint；
- War Room 与 Timeline / Graph 状态一致。

### Phase 8：硬化、发布和面试材料

- [x] Backend Commerce 确定性全量测试；
- Blocking IO Gate；
- [x] Harness Boundary；
- Frontend Unit；
- Typecheck；
- E2E；
- Browser QA；
- [x] Security / Permission Tests；
- [x] Fault Injection；
- [x] Backend deterministic Performance audit；
- [x] README；
- [x] ADR；
- [x] Architecture Diagram；
- [x] Backend Demo Script；
- [x] Failure Analysis；
- [x] Experiment Report；
- [x] Upstream Attribution；
- [x] 面试 Q&A。

## 19. 每阶段统一验证命令

Backend 聚焦测试：

```bash
cd backend
PYTHONPATH=. uv run pytest tests/commerce -v
```

真实模型预检与 Agent 测试：

```bash
cd backend
PYTHONPATH=. uv run pytest -m real_model tests/commerce -v
```

`real_model` 测试必须通过 DeepSeek V4 身份预检。模型不可用、身份不可确认或额度不足时，执行状态必须为 Blocked 并停止后续 Agent / Eval / Release Gate，不能回退到 Mock、Replay 或其他模型。

Backend 全量：

```bash
cd backend
make test
make test-blocking-io
make lint
```

Frontend：

```bash
cd frontend
pnpm test
pnpm typecheck
pnpm test:e2e
```

仓库检查：

```bash
git diff --check
git status --short
```

每一阶段必须记录：

- 执行命令；
- Exit Code；
- Passed / Failed 数量；
- 已知限制；
- 未运行项及原因；
- 相关 Experiment / ADR。

## 20. 迁移原则

- 旧 EcomLaunch 暂不删除；
- 新系统在 Feature Flag 后独立进入；
- 新旧 API、状态和前端路由不混用；
- 新系统通过 Gold Case 和基础 E2E 后，再逐步替换入口；
- 历史评测报告只读保留；
- War Room 资产可以复用，但角色和状态来源重做；
- 旧固定 Agent Prompt 不迁移到新 Agent；
- 旧 Artifact Validator 只作为失败经验参考；
- 完整数据永不进入 Git；
- 每一批删除必须单独评审。

## 21. 关键风险

### 21.1 范围膨胀

缓解：只围绕履约、卖家对标、评价体验三条证据路径完成完整闭环。

### 21.2 把相关性说成因果

缓解：Causal Language Evaluator、Unknown、Follow-up `inconclusive`。

### 21.3 多 Agent 成本失控

缓解：0–3 动态 Path Agent、Budget、ModelRouter、Pareto 实验。

### 21.4 Context 污染

缓解：ContextPacket、Fresh Verification、冻结 Memory、Hidden Label 测试。

### 21.5 Skill 自进化失控

缓解：Candidate-only、Holdout、Shadow、Human Gate、Rollback。

### 21.6 前端假状态

缓解：Domain Event 单一来源，禁止消息文本推断核心状态。

### 21.7 上游归属不清

缓解：README 和面试材料明确 DeerFlow 基础与个人增量。

### 21.8 当前仓库历史复杂

缓解：保护快照、Feature Branch、Legacy 保留、分阶段迁移。

## 22. 最终完成定义

只有同时满足以下条件，项目才算完成：

- 用户可上传真实异构电商数据；
- 系统能生成可信 Capability Report；
- 确定性指标和异常可复算；
- 四条 Gold Case 端到端通过；
- Agent 按 Capability 动态路由；
- Goal Loop 有明确停止条件；
- Verification 能拒绝无依据结论；
- Action 经过权限和审批；
- Follow-up 能关闭或重开 Case；
- Skill 只能受控进化；
- 模型和架构选择有实验记录；
- Token、Latency、Retry、Checkpoint 和 Trace 可观察；
- 前端采用 Codex 式 Workspace；
- 所有页面先有生成视觉稿再实现；
- War Room 使用真实结构化事件；
- 全量测试、QA、Review 和发布文档完成；
- DeerFlow 上游与个人贡献边界清晰；
- 所有公开演示结论均不虚构业务效果。

## 23. 当前执行状态与后续顺序（2026-07-19）

迁移期间旧 Worker 只作为行为基准。新 DeerFlow Subagent Loop 已完成 Fulfillment parity、三 Path standalone gate、0–3 Path fan-out、Evidence Barrier、持续 Lead transaction、read-only answer、bounded repair、WAIT/Resume/CANCEL、Fresh Verification 与 distinct Replan Run；当前不再把旧 Worker 当作产品架构主线。

后端闭环当前已完成：

1. [x] Deterministic Data / Capability / Metric / Anomaly / Case；
2. [x] Case、Lineage、Evidence、Hypothesis、Run、Checkpoint、Lease/Fencing、Domain Event；
3. [x] DeerFlow Adapter / Supervisor / Committer 与三条 bounded Path Subagents；
4. [x] 0–3 Path 并行、Evidence Barrier、持续 Lead Goal Loop；
5. [x] Fresh Verification Subagent、versioned verdict、Replan Run；
6. [x] Action / Approval API、Policy、Internal Connector、Execution / Rollback；
7. [x] Follow-up 新数据重算、Close / Reopen / Inconclusive；
8. [x] Fresh Action Planner + fixed Action Catalog + idempotent free replay；
9. [x] Semantic Evaluator、Experiment、Pareto Comparator、Holdout、Skill Candidate、Security Scan、Shadow；
10. [x] Human Review、Promotion、Active Pointer 与 Rollback API、幂等与 pointer-write fault recovery；
11. [ ] 对当前真实 `1.3.0` Shadow Candidate 执行用户授权的人审与首次 Promotion / Rollback 发布演练。

真实调优与评测证据：

- `exp_4d14ee6a77a74c3eb7be5d5c278d6cd8`：Control/Candidate 均通过，但 Candidate Token 高约 `13.2%`，超过成本包络，Decision=`hold`；
- `exp_6b9fe42117b74d30997800495b8eca61`：三 Case Candidate `6/6`，形成 `1.2.0` 历史 Shadow；
- `exp_1ac1367cfb5445b597ef0d1c0ffdbab6`：首次四 Case 在旧 Evaluator 下技术通过，但人工审计发现 Candidate 自造 `15% / 2×` Action 阈值，因此不作为最终晋级证据；
- `commerce-semantic-evaluator@1.2.0` 新增确定性 `unsupported-action-threshold`，Candidate Skill 升级为 `1.3.0`；
- `exp_f566076c6af9487893e2a9eb40631dc9`：Peer 微实验 Candidate `2/2`，证明不再自造数值阈值；
- `exp_aca844e7ef134b7dba264e919eacdb38`：四 Case × 两次 repetition，Candidate `8/8`、零 hard-gate failure，Control `6/8`；Candidate 平均 Token 下降约 `12.1%`，Latency 下降约 `26.0%`，Decision=`promote_candidate`；
- Candidate `skillcand_e71dc9eeb63d5ee6bcfa73920931384c` 已通过 Security、Offline/Holdout 和 Fulfillment/Review 两个 fresh V4 Shadow Run，当前状态=`shadow`；旧 `1.2.0` Candidate 保持不可变但已 superseded；没有 Human Review，不修改 Active Pointer。

最新验证基线：

```text
Ruff Commerce: passed
Commerce deterministic: 427 passed, 23 real-model tests deselected
Security / fault focused gate: 215 passed
Harness sandbox / lazy-import regression: 204 passed
Fresh DeepSeek V4 preflight: 1 passed
Fresh Action Planner live gate: 1 passed
Four-Gold synthesis/semantic live gate: 1 passed
Four-Gold full Agent Investigation live gate: 1 passed in 94.19s
Four-Gold Agent requests: 14 unique Provider Request IDs, 71,478 Agent Tokens
Actual model identity: deepseek-v4-flash
Provider retry: 0
```

前端当前视觉资产状态：

```text
历史，不再采用：
- docs/design/commerce/mockups/overview-visual-master-v1.png
- docs/design/commerce/overview-visual-master-v1.md
- docs/design/commerce/mockups/master-shell-visual-v1.png
- docs/design/commerce/master-shell-visual-v1.md

当前已确认并实现：
- docs/design/commerce/mockups/master-shell-visual-v2.png
- docs/design/commerce/master-shell-visual-v2.md
- docs/design/commerce/implementation/master-shell-react-desktop-v1.png
- docs/design/commerce/implementation/master-shell-react-mobile-v1.png
```

用户已明确要求面向用户的内容使用中文，并选择浅色 Codex Desktop-inspired 工作区作为全局设计方向。Master Shell v2 已完成 Image Generation、用户确认、中文信息架构与 View Model TDD、严格 API Contract、React、类型和单元验证、真实 Chromium 交互与桌面/移动截图 QA。`/commerce` 在 Feature Flag 关闭时 fail closed，Workspace ID 缺失时不猜测；英文后端 Case/Evidence 不直接泄露到中文主界面；未知和乱序 Domain Event 有显式处理。2026-07-20 信息密度评审进一步确定“运营默认视图 + 工程详情视图”的渐进披露规则，Case Detail v1 因默认同时暴露层级过多归档。Case Detail v2 已完成视觉确认、确定性 Analysis/Action 读模型、严格前端合同、React、真实 Gateway + SQLite + `GC-FULFILLMENT-001` 数据联调、桌面/Inspector/390×844 移动浏览器 QA 和实现截图。

Case Detail v1 已生成并作为历史密集版本归档：

```text
docs/design/commerce/mockups/case-detail-visual-v1.png
docs/design/commerce/case-detail-visual-v1.md
```

Case Detail v2 已确认并实现：

```text
docs/design/commerce/information-density-guidelines-v1.md
docs/design/commerce/mockups/case-detail-visual-v2-default.png
docs/design/commerce/mockups/case-detail-visual-v2-evidence-inspector.png
docs/design/commerce/mockups/case-detail-visual-v2-mobile-default.png
docs/design/commerce/case-detail-visual-v2.md
docs/design/commerce/implementation/case-detail-react-desktop-v1.png
docs/design/commerce/implementation/case-detail-react-evidence-inspector-v1.png
docs/design/commerce/implementation/case-detail-react-mobile-v1.png
docs/progress/2026-07-20-commerce-case-detail-react-v2.md
```

当前已完成 Data Inbox、Capability Report、Case Queue、Evidence Explorer、Action Center、Agent Run 与 Skills & Evals 的视觉稿、数据合同、React 和浏览器 QA，下一页进入 War Room 的 Image-first 设计与真实事件活动检查门禁。

Data Inbox v1 当前视觉候选：

```text
docs/design/commerce/mockups/data-inbox-visual-v1-empty.png
docs/design/commerce/mockups/data-inbox-visual-v1-review.png
docs/design/commerce/mockups/data-inbox-visual-v1-mobile-review.png
docs/design/commerce/data-inbox-visual-v1.md
```

三张图已完成中文、空态、真实 Olist 行数、Semantic Confirmation、未观察字段、无 Chat Composer 和移动响应式人工检查。实现截图与测试记录见 `docs/progress/2026-07-21-commerce-data-inbox-contract-and-react.md`。

Capability Report v1 已确认并实现：

```text
docs/design/commerce/mockups/capability-report-visual-v1-desktop.png
docs/design/commerce/mockups/capability-report-visual-v1-mobile.png
docs/design/commerce/capability-report-visual-v1.md
docs/design/commerce/implementation/capability-report-react-desktop-v1.png
docs/design/commerce/implementation/capability-report-react-mobile-v1.png
docs/progress/2026-07-22-commerce-capability-report-react.md
```

页面读取真实 Dataset Detail、Capability Profile 与 Semantic Mapping Profile，不把代表数据状态写死；“未观察”不会投影为零；非 Case 页面没有 Chat Composer、Runtime 或假 Agent 活动。视觉终检后删除了正文重复刷新，并修复顶栏刷新误刷 Case、非 Case 页面仍高亮当前案例的问题。

Case Queue v1 已确认并实现：

```text
docs/design/commerce/mockups/case-queue-visual-v1-desktop.png
docs/design/commerce/mockups/case-queue-visual-v1-mobile.png
docs/design/commerce/case-queue-visual-v1.md
docs/design/commerce/implementation/case-queue-react-desktop-v1.png
docs/design/commerce/implementation/case-queue-react-mobile-v1.png
docs/design/commerce/implementation/case-queue-react-create-v1.png
docs/progress/2026-07-22-commerce-case-queue-react.md
```

队列读取真实 Case List 并按权威生命周期状态分组，不从聊天或计时器推断活动；Capability 创建入口会预选路径，用户必须补齐经营主体、基线窗口和当前窗口后才能持久化 Explicit Case。相同内容重复提交只保留一个内容寻址 Case。无异常信号的 Explicit Case 不再错误显示为“履约延迟异常”。

Evidence Explorer v1 已确认并实现：

```text
docs/design/commerce/mockups/evidence-explorer-visual-v1-desktop.png
docs/design/commerce/mockups/evidence-explorer-visual-v1-mobile-corrected.png
docs/design/commerce/evidence-explorer-visual-v1.md
docs/design/commerce/implementation/evidence-explorer-react-desktop-v1.png
docs/design/commerce/implementation/evidence-explorer-react-mobile-v1.png
docs/progress/2026-07-22-commerce-evidence-explorer-react.md
```

页面从真实 Case Detail 投影 Evidence、Metric Observation、可审计 Fact ID 和关联 Hypothesis，支持、矛盾与未知证据同级可见；Fact 正文尚未开放时不伪造详情。Case Composer 现在只在概览页挂载，不再遮挡调查记录、证据或运行检查视图。

Action Center v1 已确认并实现：

```text
docs/design/commerce/mockups/action-center-visual-v1-desktop.png
docs/design/commerce/mockups/action-center-visual-v1-mobile.png
docs/design/commerce/action-center-visual-v1.md
docs/design/commerce/implementation/action-center-react-desktop-v1.png
docs/design/commerce/implementation/action-center-react-mobile-v1.png
docs/progress/2026-07-23-commerce-action-center-react.md
```

页面读取跨 Case 的真实 Action Record 和选中 Action Detail，从严格参数合同恢复执行计划，并展示服务端风险、策略、审批、执行工具、回滚和 Artifact；批准、拒绝、稳定幂等执行与回滚主路径已接通。结构化 Mock 浏览器场景完成 `policy_checked → monitoring → rolled_back`，后端确定性 Router 同步回归通过。Approval modify 的不可变替换后端合同已存在，通用前端编辑表单仍保留在行动闭环后续项。

Agent Run v1 已确认并实现：

```text
docs/design/commerce/mockups/agent-run-visual-v1-desktop.png
docs/design/commerce/mockups/agent-run-visual-v1-mobile.png
docs/design/commerce/agent-run-visual-v1.md
docs/design/commerce/implementation/agent-run-react-desktop-v1.png
docs/design/commerce/implementation/agent-run-react-mobile-v1.png
docs/progress/2026-07-23-commerce-agent-run-react.md
```

页面读取跨 Case Run List、选中 Run Detail、严格 Domain Event 与 Goal Loop Checkpoint 合同，投影目标、能力路由、三 Path 同级 fan-out、证据屏障、主智能体综合、新鲜上下文验证和停止阶段。后端没有独立 `evidence.barrier_released` 事件，因此屏障完成只由“全部 requested Path 进入终态 + 真实 `lead.started` / `lead.completed` 事件存在”确定性派生，并在界面中显示派生边界。实际模型、提供方请求编号、令牌、延迟、重试和原始停止原因只从真实事件 payload 聚合；缺失时显示“未观察”。最新 Checkpoint、预算、事件重排和可展开事件流已接通，非 Case 页面没有 Chat Composer。前端全量回归为 46 files / 272 tests，Commerce Playwright 11 passed，Webpack production build 通过；后端 Run Router 6 passed。该 Playwright 场景仍是 Mock API 机械验证，真实 DeepSeek V4 Agent 前端 E2E 保留在发布门禁。

Skills & Evals v1 已确认并实现：

```text
docs/design/commerce/mockups/skills-evals-visual-v1-desktop.png
docs/design/commerce/mockups/skills-evals-visual-v1-mobile.png
docs/design/commerce/skills-evals-visual-v1.md
docs/design/commerce/implementation/skills-evals-react-desktop-v1.png
docs/design/commerce/implementation/skills-evals-react-mobile-v1.png
docs/progress/2026-07-23-commerce-skills-evals-react.md
```

页面读取 Workspace-scoped immutable Skill Candidate、绑定的 Experiment Definition/Report 和可选 Active Pointer，投影候选提出、安全扫描、离线评测、留出集、Shadow、人工审查和生效七阶段门禁。新增 `GET /skill-candidates/{candidate_id}/evidence` 只读合同，使前端可以从真实 Experiment Report 展示 Candidate/Control 通过率、hard gate、令牌、延迟和唯一 Provider Request ID；它不重跑模型。Shadow 区域只显示 Candidate 当前持久化的 `shadow_live_run_ids`，请求遥测未开放时明确显示边界，不从 Run 数量推断请求数量。Actor-scoped 激活和 reason-bound 回滚主路径已接通，操作后重新读取 Candidate 与 Pointer。结构化 Mock 浏览器场景完成 `shadow → active → rolled_back`，但真实 `1.3.0` Candidate 没有被人工批准，仍保持 `shadow`。前端全量回归为 49 files / 276 tests，Commerce Playwright 12 passed，Webpack production build 通过；后端 Skill Candidate Router 5 passed。

四 Gold 完整调查门禁的 v1–v11 Failure Analysis 与逐 Case 证据见 `docs/progress/2026-07-20-commerce-four-gold-agent-release.md`。

仍需完成：War Room、Follow-up、Overview；Commerce Case-bound 问答、Approval modify 通用编辑和剩余行动跟踪交互；真实 DeepSeek V4 Agent 前端 E2E；live PostgreSQL；外部商家 Connector；当前真实 Shadow Candidate 的 Human Review/Skill Promotion；带完整真实页面截图/录屏的最终 Demo 包。当前 mock API Playwright 只验证 UI 机械行为；真实 Gateway + Olist 浏览器验收验证确定性读取，但还没有由浏览器启动并读取一条新的真实 DeepSeek V4 Agent Run，因此仍不计作前端 Agent Release Gate。Goal 在这些门禁全部完成前保持 active。

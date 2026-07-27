# Commerce Case Agent Interview Guide

> 当前 Chat-first Dynamic Parent–Subagent 主线的中文权威求职材料见 `docs/portfolio/commerce-agent-job-package-2026-07-26.md`。本文后半部分保留旧固定 Path / Case-first 设计的历史问题与迁移对照，不再作为简历和面试开场的默认架构。

> Target role: AI Agent / Agent Platform / Applied LLM  
> Target companies: ByteDance and large ecommerce platforms  
> Purpose: explain product judgment, Harness architecture, evaluation discipline and engineering depth

## 1. Thirty-Second Introduction

> 我基于字节开源的 DeerFlow 做了一个 Chat-first Commerce Agent。用户上传真实电商报表后，系统先用确定性 Tool 完成字段、Capability、指标和 Evidence 计算，Parent 再根据问题动态派遣 `explore`、`analyst` 或 fresh `verifier`，而不是固定跑一套 Crew。我重点改造了 Durable Parent–Subagent Harness，包括异步并行、Context 隔离、Tool 权限、双预算、Lease/Fencing 恢复和模型身份审计；同时做了受治理 Skill Evolution。四条真实 DeepSeek V4 Gold Gate 已全部通过，Candidate 的四 Case Holdout 是 `8/8`。

## 2. Two-Minute Introduction

> 我一开始觉得旧项目定位比较混乱，主要产出文案和方案，不符合现在 Agent 岗位更关注的 loop、harness、闭环和可靠性。我重新定义了用户问题：运营人员已经感觉业务异常，他需要知道哪里变了、可能为什么、现在做什么、做完有没有改善。
>
> 数据层不用模型算指标。上传 CSV 或公开数据以后，服务端确定性做 Profile、Semantic Mapping、Capability、Fact、Metric、Anomaly 和 Peer Cohort。只有当前数据支持的 Path 才会启动。Fulfillment、SellerPeer、ReviewExperience 用独立最小 Context、Tool allowlist、Skill 和 Budget，可以并行；只有已经通过 fencing 持久化的 Evidence 才能进入 Lead。Lead 的 Claim 再交给 fresh-context Verification，避免同一个 Agent 自己证明自己。
>
> DeerFlow 负责通用 Harness，Commerce Run/Event/Checkpoint/Lease 是业务权威状态。这样进程崩溃后可以从持久化状态判断是继续、等待、重规划还是未知结果 reconciliation，不会从聊天文本猜。Action 的风险、审批和 Connector 都由服务端决定，Follow-up 没有可靠对照时只能 inconclusive。Skill 自进化只能生成 Candidate，要经过 Eval、Holdout、Shadow、Human Review 和 Rollback。
>
> 当前 Chat Dynamic 四条跨场景 fresh Gate 全部通过；真实六文件持久化浏览器 Gate 以 170,394 Token 完成 Parent–Subagent Run，Explore/Analyst 并行、fresh Verifier 后置、13 个 Provider Request ID 去重、retry 0，实际服务端身份为 `deepseek-v4-flash`。Gateway 重启后仍恢复三个 Task、104 条 Run Event、15 条消息和最终中文答案。Skill Evolution 的真实四 Case Holdout 为 Candidate `8/8`，并通过两个真实 Shadow Run；PostgreSQL 本地迁移、重启恢复和 fencing takeover 也已通过。当前保留边界是外部商家 Connector、真实 Skill Promotion、正式多租户权限与容量压测。

## 3. Resume-Ready Project Bullets

### Balanced version

- 基于 DeerFlow 深度改造 Durable Parent–Subagent Harness，实现动态委派、并行/后台任务、版本化 ContextPacket、Tool 权限双预算、Lease/Fencing 恢复及 Provider Request ID、模型身份、Token、Stop Reason 全链路审计。
- 构建 Chat-first 电商经营诊断主链，将异构数据接入、Capability、窗口指标、同类对标和 Evidence 抽查封装为确定性 Tool，以 `explore/analyst/verifier/operator + Commerce Skill` 代替固定业务 Crew；四条 fresh DeepSeek V4 Gold Gate 全部通过。
- 建立受治理 Skill Evolution：Control/Candidate、Regression、Holdout、Shadow、Human Promotion 与 Rollback；真实四 Case Holdout Candidate `8/8`，并完成 PostgreSQL 重启恢复、fencing takeover 和可逆内部 Action 门禁。
- 实现中文 DeerFlow Chat 与原创游戏化协作空间，共用同一 Durable Task/Event ViewModel；没有 Task 时不生成角色或假忙碌，62 个测试文件 / 334 个前端单测、6 条专项 Chromium 交互及真实持久化 DeepSeek V4 浏览器 Gate 通过。

### More infrastructure-oriented version

- Extended DeerFlow with a business-agnostic Commerce subagent adapter, lifecycle supervisor, Tool allowlists, trusted telemetry extraction, fenced committer and persisted Evidence Barrier.
- Separated Harness execution projection from Commerce business truth, using append-only events, optimistic concurrency, lease-token hashing and monotonically increasing fencing tokens for restart-safe execution.
- Converted ten retained real-model failures into versioned schema, lineage, token-budget, lifecycle and hallucination guards; accepted v11 four-Gold release gate on fresh `deepseek-v4-flash`.

### More product-oriented version

- Reframed an ecommerce copywriting workflow into a real operator product that answers: what changed, why, what Action is worth doing, and whether the signal improved.
- Supports uploaded heterogeneous data, human semantic confirmation, Capability Reports, fulfillment/peer/review investigations, evidence exploration, approval, reversible internal Actions and new-data Follow-up.
- Prevents unsupported GMV/CTR/ROI/profit claims, causal overclaiming and fake Agent activity through deterministic contracts and a structured Domain Event source of truth.

## 4. Architecture Questions

### Q1. Why not use one large Agent?

Answer:

- one Agent would receive excessive context and Tool permissions;
- irrelevant data increases cost and cross-domain hallucination;
- one reasoning history makes independent verification impossible;
- failure and timeout attribution becomes unclear;
- different Paths need different tools, budgets and output contracts.

The chosen design uses a continuous Lead plus zero to three bounded Path subagents and one fresh Verification subagent.

The important point is not the number of Agents. It is the isolation boundary:

```text
minimal Context
separate Tool allowlist
separate Skill/model assignment
bounded budget
structured result
no direct state mutation
```

### Q2. Why not always start all three Path Agents?

Answer:

- Capability may be unavailable because data fields are missing;
- the user may ask only about reviews or peers;
- fixed fan-out wastes model cost;
- a missing Capability must produce `unknown/blocked`, not a fabricated answer.

`DynamicPathRouter` is deterministic because Capability and explicit intent are stable business rules. Model routing is unnecessary for the first three Paths.

### Q3. Is this really a loop or just a workflow chain?

Answer:

It is a loop because every iteration reloads persisted state and can change the next action:

```text
observe persisted Case
→ route / answer / wait / stop
→ bounded work
→ checkpoint
→ evaluate new Evidence and gaps
→ continue / replan / resume / terminate
```

It supports read-only follow-up questions without rerunning Paths, explicit new-angle Replan Runs, WAIT/Resume, cancellation, verification rejection and no-new-Evidence stopping.

### Q4. What is the Harness layer?

Answer:

The Harness owns reusable execution concerns:

- model creation and telemetry;
- subagent task lifecycle;
- Tool and Skill injection;
- sandbox and permission middleware;
- streaming and LangGraph execution;
- cancellation and cleanup.

The Commerce application owns business concerns:

- Dataset, Capability and Case;
- Evidence and Hypothesis;
- Run phases and stop reasons;
- Action, Approval and Follow-up;
- evaluation and Skill promotion policy.

The adapter is the boundary between them.

### Q5. Why is Commerce Run separate from DeerFlow Run?

Answer:

The generic DeerFlow runtime is Thread/Chat-oriented. Commerce needs waiting, partial, approval, follow-up, business phases, Evidence references and long-lived Cases. Putting those concepts into `deerflow.*` would pollute the reusable Harness.

Therefore:

```text
DeerFlow Run = execution projection
Commerce Run/Event/Checkpoint = business source of truth
```

## 5. Framework Selection Questions

### Q6. Why DeerFlow rather than raw LangGraph?

Answer:

DeerFlow already uses LangGraph and provides Subagent, Tool, Skill, Sandbox, Streaming and model infrastructure. A second raw graph would duplicate infrastructure and still not solve the Commerce data/evidence/action domain.

LangGraph remains valuable as the underlying execution engine. It is not used as the Commerce business database.

### Q7. Why not DeepAgents?

Answer:

DeepAgents is a reasonable greenfield option for planning, filesystem work and subagents. In this repository it overlaps with capabilities already present in DeerFlow. Migration cost would be high, and the Commerce domain would still need to be built.

The decision is contextual rather than ideological.

### Q8. Why not Pi Agent?

Answer:

A minimal loop is attractive for control and simplicity, but the project would need to rebuild durable subagent execution, streaming, permission middleware, checkpoint integration and observability. That work does not differentiate the ecommerce product.

### Q9. Why not Multica?

Answer:

Multica is oriented toward coding-agent teammates, issues, squads and managed coding runtimes. It can coordinate coding work, but it is not the runtime for ecommerce Evidence, Metric, Case, Approval and Follow-up semantics.

## 6. Data and Evidence Questions

### Q10. You did not have private business data. Is the project real?

Answer:

The system uses real public ecommerce records and supports user-uploaded data. The four Gold Cases are versioned Olist-derived fixtures with frozen file hashes, rows, expected facts and forbidden conclusions.

What public data proves:

- ingestion and mapping work;
- metrics and joins are reproducible;
- Agent routing and evidence contracts work;
- failure and lifecycle semantics are real.

What it does not prove:

- private-company uplift;
- production traffic scale;
- causal business impact.

Those boundaries are stated explicitly.

### Q11. How do you handle arbitrary uploaded columns?

Answer:

1. profile tables, types, nulls and unique counts;
2. apply deterministic semantic rules;
3. optional LLM can only suggest an unconfirmed mapping candidate;
4. human mapping-resume validates the full batch and records the actor;
5. recompute the Capability Profile;
6. unavailable Paths return precise missing semantics rather than guessing.

### Q12. Why are Fact, Metric, Evidence and Hypothesis separate?

Answer:

- Fact is a normalized observed input;
- Metric is a deterministic aggregate or comparison;
- Evidence is a Case-scoped interpretation pointing to Facts/Metrics;
- Hypothesis is a versioned explanation under investigation;
- Claim is Lead output;
- Verification is an independent verdict over a Claim.

Separating them allows precise lineage and prevents a model-written sentence from becoming an authoritative metric.

### Q13. How do you prevent causality overclaiming?

Answer:

- Gold Cases contain forbidden causal conclusions;
- deterministic evaluators reject phrases such as `root cause`, `dominant driver` and `caused the recovery` when unsupported;
- Verification checks Claim-to-Evidence lineage;
- Follow-up returns `inconclusive` without a reliable counterfactual;
- peer selection never uses the outcome being compared.

## 7. Reliability Questions

### Q14. Can you guarantee exactly-once model execution?

Answer:

No. A remote provider boundary makes true exactly-once impossible if a process crashes after sending a request but before persisting the response.

The system provides:

- durable pre-call intent;
- stable Task IDs;
- lease and fencing for state writes;
- idempotent internal tools;
- explicit unknown-outcome reconciliation;
- no automatic model retry after a pre-call Checkpoint;
- a new Replan Run for an authorized retry.

This is risk management, not a false exactly-once claim.

### Q15. What does fencing solve?

Answer:

After a lease expires, Worker 2 acquires a higher monotonically increasing fencing token. Every write validates the active token. Worker 1 may still be alive, but its old token cannot append Evidence, Checkpoints or terminal Events.

### Q16. How do you recover a partial transaction?

Answer:

Two injected windows are covered:

- reconciliation Events/Checkpoint persisted but Run projection update failed;
- Skill state appended but Active/rollback Pointer write failed.

The retry validates the already persisted command identity and completes the missing projection or Pointer without adding a duplicate terminal event/state.

### Q17. Why not just retry three times?

Answer:

Retries can duplicate cost, side effects and telemetry. Retry count is not a substitute for identifying whether the previous external operation happened.

Provider retries are configured to `0` in release gates. Recovery requires persisted evidence and explicit authority.

## 8. Context Engineering Questions

### Q18. How do you control context size and contamination?

Answer:

- each role uses a different versioned ContextPacket;
- the router selects only relevant Paths;
- each Path receives only its Case slice, deterministic metrics and allowed source references;
- hidden evaluation-label keys are rejected recursively;
- Lead receives persisted Evidence scopes, not full Path reasoning histories;
- Verification receives Claims and original supporting Evidence, not Lead chain-of-thought;
- every Context has a canonical SHA-256 and token estimate.

### Q19. Why fresh Verification?

Answer:

If the same Agent sees its own full reasoning history, it is biased toward defending the conclusion. Fresh Verification receives a minimal independent context and produces structured verdicts.

It can:

- pass a supported Claim;
- reject a Claim;
- require repair/replan;
- preserve Fact/VOC-only support;
- reject invented IDs or causal certainty.

### Q20. Why semantic reference scopes for Review?

Answer:

The real v10 model copied an opaque Fact ID that did not exist in its Context. Expecting the model to reproduce internal IDs is brittle.

The model now chooses semantic scopes such as:

- `review_metrics`;
- `late_delivery_metrics`;
- `voc_excerpts`.

The server resolves those scopes to packet-owned IDs.

## 9. Evaluation and Tuning Questions

### Q21. How did you evaluate the Agent?

Answer:

Three layers:

1. deterministic tests for domain, metrics, state, lineage, budgets, policy and failure paths;
2. fresh identity-verified DeepSeek V4 tests for every Agent/model behavior;
3. Gold Case release gates with exact routing, semantic scorecard and trace requirements.

No Mock/Fake/Replay response is accepted as Commerce Agent evidence.

### Q22. What were the most important real failures?

Answer:

- verification wrongly required a Metric for every Claim;
- fixed output tokens truncated multi-Claim JSON;
- redundant lineage fields made valid results fail;
- explicit user investigation was forced to fabricate an anomaly;
- model copied an opaque ID outside Context;
- unclosed provider clients failed during event-loop teardown.

These failures resulted in contract changes, not prompt-only patches.

### Q23. How did you choose the Skill version?

Answer:

Experiments compare hard-gate pass rate first, then Token and Latency Pareto behavior. A Candidate is not promoted merely because it sounds better.

The current `1.3.0` Candidate achieved:

- four cases × two repetitions;
- `8/8` Candidate pass;
- zero hard-gate failures;
- lower average Token and Latency than Control;
- two fresh live Shadow Runs.

It is still Shadow pending human review.

### Q24. How do you know the model was really DeepSeek V4?

Answer:

The preflight does not trust only the local alias. It makes a fresh request with a unique nonce, disables cache and retry, checks the server-reported identity, and persists secret-free telemetry.

The persistent browser gate recorded the configured alias `deepseek-reasoner` separately from the actual identity `deepseek-v4-flash`, with 13 de-duplicated Provider Request IDs and retry `0`. Telemetry is attached only to terminal streaming chunks so LangChain chunk merging cannot duplicate identity or request strings.

### Q24A. Why does dispatch temporarily disable thinking?

Answer:

A real Run showed that Parent could narrate “I will dispatch” without emitting `spawn_task`, so the requirement gate correctly failed with zero Subagent tokens. Requiring a Tool Call directly on a DeepSeek V4 thinking request returned HTTP 400 because that capability combination is unsupported.

The final design keeps business analysis in thinking mode, then uses the same `deepseek-v4-flash` model for a narrow dispatch-control invocation with thinking disabled and `tool_choice=required`. The model still generates a real Tool Call against the formal schema; the system does not fabricate calls, switch models or retry. Historical `reasoning_content` is omitted for that non-thinking invocation, and the entire topology is checked from persisted Task events.

## 10. Self-Evolution Questions

### Q25. Does the Agent modify its own Skill?

Answer:

No. Online execution cannot edit Active Skill content.

It can only produce an immutable Candidate tied to failure codes and experiment evidence. Promotion requires:

```text
security
offline eval
regression
holdout
fresh shadow
human review
active pointer transaction
rollback availability
```

### Q26. What exactly evolves?

Answer:

Currently the versioned Skill contract and prompts can evolve. Model, prompt, Skill, Context and Router versions are recorded separately so experiment attribution is possible.

The system does not let a model arbitrarily rewrite business policy, metrics or permissions.

### Q27. Why is Human Review still necessary after `8/8`?

Answer:

The earlier experiment technically passed under an older evaluator, but manual review found invented `15% / 2×` Action thresholds. This proved that automated gates can have blind spots.

Human review is a defense-in-depth gate, not ceremony.

## 11. Performance Questions

### Q28. Will multiple Agents be slow?

Answer:

The design controls latency in four ways:

- deterministic router avoids irrelevant Paths;
- independent Paths execute concurrently;
- fast structured models can be used for narrow tasks, stronger models only for synthesis/verification;
- read-only questions reuse persisted Evidence without rerunning investigation.

The deterministic fan-out test runs simulated `0.08s` and `0.12s` Paths in about `0.12s`, below the `0.18s` gate and below serial `0.20s`.

The live four-Gold gate took 94.19 seconds for 14 Agent requests across four complete investigations; it is evaluation evidence, not an interactive latency target.

### Q29. How do you control cost?

Answer:

- maximum three Path Agents;
- per-role token, Tool, iteration and wall-time budgets;
- no irrelevant Path calls;
- no provider retry in release gates;
- claim-count-aware output budgets;
- Pareto evaluation of pass rate, Token and Latency;
- idempotent replays that do not call the model again.

## 12. Security and Permission Questions

### Q30. How do you prevent Tool abuse?

Answer:

- Path-specific Tool allowlists;
- task-management Tool permanently disallowed inside Commerce subagents;
- sandbox path validation and traversal protection;
- prompt security tests;
- Skill permission tests;
- model cannot override runtime telemetry, policy, risk or connector identity;
- external merchant execution disabled by default.

### Q31. How do you protect secrets?

Answer:

- credential remains in ignored `.env`;
- no Key enters code, docs or reports;
- only hashes of resume/lease/idempotency tokens are stored;
- telemetry records endpoint/model/request IDs but not credentials;
- secret-shaped Skill content fails security scan.

The credential was exposed in chat during development, so it should be rotated before public deployment.

## 13. Honest Boundary Questions

### Q32. What is not finished?

Answer:

- 中文 Chat、六文件真实上传、持久化 Parent–Subagent Thread/Run、Task/Event 协作空间和桌面/移动端浏览器 QA 已完成；
- external merchant Connectors;
- production-grade multi-tenant authentication and Workspace membership;
- actual promotion of the real Shadow Candidate;
- production multi-node CAS storage for file-backed governance receipts;
- production capacity testing and node-level high availability.

面试项目和本地可演示 Release 已完成，但不要把它描述成已经上线的生产电商平台；外部写权限、正式多租户、容量与 HA 仍是明确边界。

### Q33. Why did you not enable external merchant writes for the demo?

Answer:

Without a real merchant sandbox, credential governance and domain-specific rollback verification, enabling writes would be unsafe and mostly simulated. The project therefore implements real reversible internal Actions and keeps external mutation fail closed.

### Q34. What did the PostgreSQL integration prove?

Answer:

I installed the repository's optional PostgreSQL extra and ran a real local PostgreSQL 16 gate. It applied all Commerce migrations, persisted a leased Run and Goal Loop Checkpoint, disposed and recreated the SQLAlchemy connection, then recovered the Run and Checkpoint and took over the expired lease with fencing token `2`. This proves the application persistence contract across a connection/process boundary; it is not a claim that a production multi-node PostgreSQL deployment has been load-tested.

## 14. Upstream Attribution Questions

### Q35. What came from DeerFlow and what did you build?

Answer:

DeerFlow upstream provides the general Agent Harness, subagent runtime, Tool/Skill/Sandbox infrastructure, model factory, streaming and base full-stack workspace.

The project adds:

- Commerce Case product model;
- data/metric/capability pipeline;
- Evidence and Hypothesis domain;
- bounded Commerce subagent contracts and adapter;
- business Run/Event/Checkpoint/Lease/Fencing;
- fresh Verification and Gold evaluation;
- Action/Approval/Execution/Follow-up;
- Skill governance;
- 中文 Chat、紧凑 Task 状态和由真实 Task/Event 驱动的原创游戏化协作空间。

Be explicit: do not present upstream Harness code as personal invention.

## 15. Deep-Dive Code Map

| Interview question | Files to open |
| --- | --- |
| runtime choice | `docs/adr/0005-commerce-uses-deerflow-subagent-runtime.md` |
| business state ownership | `docs/adr/0004-commerce-run-is-domain-source-of-truth.md` |
| goal loop | `backend/app/commerce/agents/goal_loop.py`, `lead_loop.py`, `lead_execution.py` |
| subagent boundary | `subagent_adapter.py`, `subagent_supervisor.py`, `subagent_committer.py` |
| fan-out | `subagent_fanout.py`, `subagent_coordinator.py`, `evidence_barrier.py` |
| verification | `verification.py`, `verification_subagent.py`, `verification_execution.py` |
| restart safety | `resume.py`, `api/run_reconciliation_service.py`, `persistence/runs.py` |
| data mapping | `api/data_service.py`, `data/semantic_mapper.py`, `data/capabilities.py` |
| Action safety | `actions/policy.py`, `actions/execution.py`, `actions/follow_up.py` |
| Skill evolution | `evaluation/skill_evolution.py`, `api/skill_candidate_service.py` |
| real model gate | `evaluation/real_model_preflight.py`, `agents/verified_call.py` |
| v1–v11 evidence | `docs/progress/2026-07-20-commerce-four-gold-agent-release.md` |

## 16. Red-Flag Answers to Avoid

Do not say:

- “Multi-Agent is always better.”
- “LangGraph guarantees exactly-once.”
- “The model calculates all metrics.”
- “The four Gold Cases prove business uplift.”
- “Shadow passing means the Skill can auto-promote.”
- “DDL compilation means PostgreSQL passed.”
- “I built DeerFlow.”
- “External connectors work” when they remain disabled.
- “The latest v7 run was repair-free.”
- “The persistent browser Gate proves business uplift.”

## 17. Strong Closing Answer

> 我觉得这个项目最能体现 Agent 工程能力的地方，不是 Prompt 数量，也不是 Agent 数量，而是我把模型不确定性限制在适合它的语义判断里，把数据、权限、状态和恢复做成确定性合同；同时用真实模型失败推动 Context、Verification、预算、生命周期和自进化门禁迭代。这样系统才能从“能生成答案”走到“可以被运营人员长期使用和审计”。

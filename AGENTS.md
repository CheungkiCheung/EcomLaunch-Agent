# Commerce Case Agent — Project Instructions

本文件适用于整个 `deer-flow` 仓库。更深层的 `AGENTS.md` 可以增加目录专属约束，但不得降低这里的证据、测试和安全要求。

## 1. 项目身份

当前主线是 **Commerce Case Agent**（工作名）：面向电商运营的异构数据诊断与行动 Agent。

它解决四个连续问题：

```text
哪里出了问题？
为什么发生？
现在最值得做什么？
做完以后有没有改善？
```

核心产品对象是 `Case`，不是 Chat、文案、报告或一次性 Artifact。标准闭环：

```text
数据进入
→ Capability Profile
→ 异常检测
→ Case
→ Goal Loop 调查
→ Fresh-context Verification
→ Action 审批与执行
→ Follow-up
→ Close / Reopen / Inconclusive / Blocked
```

完整设计以 `docs/plans/2026-07-18-commerce-case-agent-complete-design-and-implementation-plan.md` 为准。

## 2. 首批范围

只完成三条可复现的证据路径：

- `FulfillmentPathAgent`：履约与承运链路；
- `SellerPeerPathAgent`：同类卖家或实体对标；
- `ReviewExperiencePathAgent`：评价与商品体验问题。

系统按 Capability 动态启动 0–3 个 Path Agent，不使用固定五 Agent Crew。

本轮不建设万能电商平台，不模拟市场，不虚构 GMV、CTR、CVR、ROI、利润、库存或经营提升，不把相关性写成因果，不以生成方案或文案作为核心价值。

## 3. 架构边界

- `backend/packages/harness/deerflow/` 是可复用 Harness；保持业务无关。
- `backend/app/commerce/` 是 Commerce 业务应用层。
- `app.*` 可以导入 `deerflow.*`；`deerflow.*` 禁止导入 `app.*`。
- Commerce Domain、Case、Evidence、Action、Follow-up 和 API 不进入 Harness。
- 通用 Run、Streaming、Sandbox、Tool、Checkpoint、Memory、Loop Detection 和 Token Tracking 优先复用 DeerFlow。
- 新系统只在 `COMMERCE_CASE_AGENT_ENABLED=true` 时挂载后端入口。
- 新前端只在 `NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED=true` 时展示入口。
- 新旧 API、状态、事件、评测和前端路由不得混用。

## 4. 数据与证据纪律

- 使用真实公开数据集或用户上传数据；完整原始数据不得提交到 Git。
- 确定性数据层先于 LLM：Schema、Join、Metric、窗口、异常和数据质量必须可复算。
- 事实、指标、证据、假设和结论必须是不同对象。
- 每个结论必须能追溯到 `Evidence`；缺数据时使用 `unknown`、`not_observed` 或精确补数建议。
- 评论文本可以支持“疑似非原装、错发、少发”等体验信号，但不得据此确认售假、欺诈或违法。
- Action 后的变化没有可靠对照时，结果必须是 `inconclusive`，不得声称因果提升。
- Gold Case 的输入、预期事实和禁止结论必须冻结并版本化。

## 5. 真实 DeepSeek V4 测试红线

测试分为两类：

1. 纯确定性测试：Domain、Metric、State Transition、Repository、Event、Budget、Policy、数据质量和 Join。它们保持无模型，不得为了形式调用 LLM。
2. LLM / Agent 测试：任何触达模型或验证 Agent 行为的路径，必须向真实 DeepSeek V4 发起当次新请求。

LLM / Agent 测试包括 Lead、Path Agent、模型路由判断、Tool Selection、Structured Output Repair、Verification、Semantic Evaluator、Skill Candidate、Agent Integration、Gold Case E2E、Experiment 和 Release Gate。

对这些测试：

- 禁止 Mock、Fake、Stub、Replay、缓存响应或其他模型作为 PASS 证据；
- 禁止自动回退到其他 DeepSeek 版本或其他厂商模型；
- 历史 Trace 只能用于 Debug，不能作为当前 Release Gate；
- 运行前必须通过 `real_model_preflight`；
- 必须确认服务端实际模型身份为 DeepSeek V4，而不是只相信本地别名 `deepseek-reasoner`；
- 必须记录 Provider Request ID、模型身份、Token、Latency、Retry、Stop Reason，以及 Prompt / Skill / Context / Router 版本；
- 模型不可用、身份不可确认、鉴权失败或额度不足时，立即停止相关测试并报告 `blocked`；不得 Skip 后伪装通过。

在 `real_model_preflight` 实现前，不运行 Commerce Agent 行为测试。

## 6. Agent 与 Loop 规则

- Lead 负责目标、预算、路由、综合与停止条件，不替代确定性数据计算。
- Path Agent 只接收最小 `ContextPacket`，返回结构化 Evidence 和未解决问题。
- Verification 使用新鲜上下文，不继承 Lead 的完整推理历史。
- 每次循环必须有明确 Goal、Budget、Stop Condition 和 Checkpoint。
- 无新证据、预算耗尽、能力不足、策略阻塞或目标已满足时必须停止。
- War Room 只能显示真实 Domain Event；无事件时不播放假忙碌。
- Action 必须经过权限策略；高风险写操作需要人工审批。

## 7. Skill Evolution

- 线上 Agent 不得直接修改 Active Skill。
- 只允许生成 `Skill Candidate`。
- Candidate 必须经过 Offline Eval、Regression、Holdout、Human Review、Shadow 和可回滚发布。
- 评测使用真实 DeepSeek V4；额度不足时停止，不降低门槛。
- Prompt、Skill、Context、Router 和模型配置必须独立版本化，便于实验归因。

## 8. 开发纪律

- 多步骤改造先更新实施计划或阶段清单。
- 功能和 Bug 修复默认采用 RED → GREEN → REFACTOR → VERIFY。
- 先确认失败测试确实因目标行为缺失而失败，再实现最小代码。
- 不用提高重试、吞异常、降低断言或更换模型掩盖失败。
- 修改优先使用 `apply_patch`；搜索优先使用 `rg`。
- 保留用户已有改动，不做无关重构。
- 不使用破坏性 Git 命令，不删除 Legacy，不提交密钥、环境文件、运行数据库、完整数据集或模型输出缓存。
- 每个阶段记录命令、Exit Code、Passed / Failed、未运行项、费用/Token 和已知限制。

## 9. 前端原则

- 前端是 Case-first Workspace，不是给旧聊天页换皮。
- Chat、Timeline、Graph、Evidence、Action、Follow-up 和 War Room 读取同一 Domain Event Stream。
- 核心状态不得从自然语言消息、CSS 动画计时器或前端猜测中推断。
- 视觉采用 Codex-inspired Workspace，但保留 Commerce 的信息结构和业务可读性。
- 每个正式页面（包括 War Room）必须先生成高保真视觉稿、记录选择，再写页面代码。
- 前端实现完成后必须做真实浏览器交互和视觉 QA；涉及 Agent 的 E2E 必须连接真实后端和真实 DeepSeek V4。

## 10. Legacy 边界

以下内容只读保留，作为历史成果或失败经验，不是新系统 Release Gate：

- `agents/ecom-launch/`；
- `skills/custom/ecom-launch/`；
- `evals/opensku/`；
- `scripts/opensku/`；
- `docs/ecom-launch/`；
- `docs/knowledge/opensku/`；
- `frontend/src/components/workspace/ecom-launch/`；
- 旧 OpenSKU 报告、Replay 和 War Room 资产。

允许复用视觉资产和通用基础设施，但角色、状态来源、评测结论和业务合同必须按 Commerce Case Agent 重新实现。

## 11. 完成与沟通

- 只有证据充分时才声称完成。
- 未运行真实模型测试时，必须明确说明“Agent 行为尚未验证”。
- 模型或额度阻塞时，报告已完成的确定性工作、阻塞状态和恢复所需条件，然后停下。
- 只有产品定位、范围、重大技术路线、外部付费、视觉母版选择、发布或数据安全等关键决定才暂停请求用户。

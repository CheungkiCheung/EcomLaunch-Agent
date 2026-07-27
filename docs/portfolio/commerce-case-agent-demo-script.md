# Commerce Agent 八分钟中文 Demo 脚本

> 面向岗位：AI Agent / Agent Platform / Applied LLM  
> 面向公司：字节跳动及具有电商业务的大型互联网公司  
> 当前主线：DeerFlow 中文 Chat + Dynamic Durable Parent–Subagent  
> 演示原则：现场优先复用已通过的持久化 Thread/Run，不在短面试中重复消耗大额模型 Token；不虚构业务提升，不声称 Skill 已自动 Promotion、外部平台写入或生产多节点能力。

## 1. 演示目标

八分钟内让面试官确认五件事：

1. 这是用户上传真实数据并自然追问的可用产品，不是生成一份运营文案；
2. 指标计算由确定性 Tool 完成，模型负责规划、调查、核验和表达；
3. Parent 按问题动态派遣通用 Subagent，独立任务可以并行；
4. Task、Evidence、模型请求、失败恢复和最终回答都可以审计；
5. Skill Evolution 受 Eval、Shadow 和人审治理，在线 Agent 不能直接修改 Active Skill。

## 2. 演示前检查

- 使用分支 `feature/commerce-case-agent`；
- Gateway 和 Frontend 均已启动；
- DeepSeek Key 只存在于 Git 忽略的根 `.env`，演示时不打开或打印；
- 服务端实际模型身份必须是 `deepseek-v4-flash`，Provider retry 必须为 `0`；
- 准备冻结的六个公开 Olist CSV 和冻结 Prompt；
- 准备 v7 通过审计、v7 首次失败审计、Skill Holdout/Shadow 审计作为稳定备份；
- 准备持久化浏览器 Gate v7 的同一 Thread/Run、审计 JSON 与四张桌面/移动端截图；
- 不在面试现场 Promotion `commerce-diagnostic-synthesis@1.3.0`；
- 不声称外部商家写入、业务 uplift、生产多节点 HA 或 repair-free。

核心证据入口：

```text
docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/README.md
docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/passed-dynamic-release-audit.json
docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/failed-before-negation-aware-guard.json
docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/passed-browser-audit.json
docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/02-final-chat-desktop.png
docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/03-collaboration-desktop.png
docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/04-collaboration-mobile-reduced-motion.png
docs/design/commerce-collaboration-imagegen-assets-v1.md
docs/progress/2026-07-26-commerce-postgres-skill-evolution-release.md
```

## 3. 八分钟演示顺序

### 0:00–0:40：中文 Chat、上传数据与真实用户问题

打开 DeerFlow 中文 Chat。拖入或通过回形针选择六个公开 CSV，输入冻结问题：分析店铺最近的履约异常，比较两个明确时间窗口，区分卖家处理与承运运输，要求支持证据、反证、未知项、限制和下一步，并由独立核验任务重算核心指标。

讲解：

> 用户不需要先理解 Case、Path 或 Metric Registry。他只需要把手里的报表放进对话并描述异常。系统会先判断这些文件能够回答什么，缺少曝光、点击、广告、库存、利润或 GMV 时就明确说不能回答，不会补数据。

推荐直接打开已经通过的持久化 Thread。若现场登录态或网络异常，展示同一 Run 的冻结截图和 `passed-browser-audit.json`，明确这是既有真实 Run 的证据，而不是 Mock 页面或缓存模型回复。

### 0:40–1:20：Capability 与确定性 Tool

展示数据能力识别和 Tool 调用摘要：

```text
上传文件
→ Profile / Semantic Mapping
→ Capability
→ 精确可用时间范围
→ 窗口指标与 Evidence
```

讲解：

> 模型不心算订单数、晚到率或处理时长。它只能选择允许的 Tool 和参数，数值由服务端全量关联后确定性计算。模型看不到的库存、利润、曝光或广告消耗不会进入结论。

### 1:20–2:40：Parent 动态并行派遣 Explore / Analyst

展示 Task 活动和不可变审计中的创建时间：

- Explore 调查数据覆盖与可用范围；
- Analyst 计算窗口对比和 Evidence；
- 两个 Task 创建时间相差约 1ms，生命周期真实重叠；
- 每个 Task 有独立 ContextPacket、Skill、Tool allowlist、轮次和调用预算。

讲解：

> Profile 只描述工作方式，业务知识放在 Commerce Skill，Tool 是当前任务的最小权限包。新增退款、流量或广告诊断时主要增加 Skill 和 Tool，不需要不断发明固定业务 Agent 类型。

### 2:40–3:30：wait-all 与 fresh Verifier

展示 Parent 等待首轮 Task 终态，然后创建 Verifier：

```text
Explore completed ┐
                  ├→ wait-all → fresh Verifier
Analyst completed ┘
```

Verifier 必须显式引用两个 `task:<id>`，重新调用确定性 Tool 复算核心指标。它不继承 Parent 的隐式推理历史。

讲解：

> fresh Verifier 不是再让同一个 Agent 检查自己的原答案。它只拿最小上下文和首轮任务的持久化结果，独立重算并检查证据、反证、数据限制和因果边界。

### 3:30–4:20：最终中文答案与 Evidence 边界

展示最终答案，重点指向：

- 基准窗口订单数 `141`，当前窗口订单数 `202`；
- 基准晚到率 `3.55%`，当前晚到率 `35.15%`；
- 处理时长和运输时长来自确定性 Tool；
- 至少一个可追溯 Evidence ID；
- 包含支持证据、反证或替代解释、未知项、数据限制和下一步；
- 不把相关性写成因果；
- 不推断数据中不存在的指标。

不要把上述数值表述为业务 uplift，也不要把公开数据说成企业私有数据。

### 4:20–5:10：游戏化协作空间不是第二套状态

从同一 Chat 按需打开协作空间：

- 空 Run 只显示空房间；
- 一个 Durable Task 对应一个角色和一个工位；
- Profile 决定角色外观，Task station 决定工位；
- Tool 标签来自真实 Tool Result；
- failed、cancelled、timed_out 是不同终态；
- 点击角色或任务打开 Drawer，查看 Task ID、状态和 Tool；
- 390px 窄屏使用同一 ViewModel 缩放，不创建第二份状态模型。

讲解：

> 协作空间只是 Task/Event 的观察层，不是为了好看而模拟几个 Agent 忙碌。没有真实 Task 就没有角色，Chat、紧凑任务条和游戏空间共享同一份 Durable 状态。

### 5:10–6:00：真实模型与 Harness 遥测

展示持久化浏览器 Gate v7 的 secret-free 审计：

```text
actual_model_identity=deepseek-v4-flash
run.llm_call_count=6
provider_request_ids_unique=13
total_tokens=170,394
lead_agent_tokens=124,966
subagent_tokens=45,428
retry_count=0
task_count=3
run_event_count=104
restart_recovery=true
```

讲解：

> 本地 alias 只是 `deepseek-reasoner`，Release Gate 不信任 alias。Preflight 会发 fresh 请求检查服务端身份、Provider Request ID、Token、Stop Reason 和 retry。所有 Agent/LLM 行为测试都使用真实模型，不接受 Mock、Replay 或缓存回复作为通过证据。

### 6:00–6:50：一次真实派工失败如何推动 Harness 调优

展示早期持久化 Run：Parent 在文字里说“准备派遣任务”，但没有产生正式 `spawn_task` Tool Call，最终被 Subagent Requirement Gate 拦截，Subagent Token 为 0。

展示 TDD 修复：

```text
Parent 只口头派工
→ Requirement Gate fail closed
→ 尝试 tool_choice=required
→ DeepSeek V4 thinking 模式返回 400
→ 业务分析轮保留 thinking
→ 派工控制轮使用同一 V4、临时关闭 thinking、required Tool Call
→ 不回放历史 reasoning_content
→ terminal chunk 单次写入模型身份与 Request ID
→ fresh 持久化浏览器 Gate PASS
```

讲解重点：没有伪造 Tool Call，没有更换模型，没有提高 retry；只是根据模型能力把“业务推理”和“结构化派工控制”分成同一 V4 的两个调用模式。此前 Response Guard 的否定句误判也保留在独立 Chat Dynamic v7 审计中，可作为第二个 TDD 失败案例。

### 6:50–7:30：受治理 Skill Evolution

展示：

```text
Failure
→ immutable Candidate
→ Security Scan
→ Control/Candidate Experiment
→ Regression / Holdout
→ fresh Shadow
→ Human Review
→ Promotion / Rollback
```

当前 Candidate `commerce-diagnostic-synthesis@1.3.0` 的真实证据：Holdout `8/8`、32 个唯一模型请求、两个真实 Shadow Run。它仍是 `shadow`，未获用户人审授权，因此没有修改 Active Pointer。

### 7:30–8:00：上游边界与诚实限制

最后主动说明：

- DeerFlow 上游提供 LangGraph 执行、Thread/Message/Streaming、基础 Subagent、Tool/Skill/Sandbox 和模型工厂；
- 个人新增是 Durable Task Harness 深化、Commerce 数据/证据/行动域、动态 Tool/Skill、fresh Verifier、可靠性 Gate、Skill Evolution 治理和 Task/Event 驱动的中文协作界面；
- 持久化 Chat 上传、真实 Parent–Subagent Run、同源协作空间和 Gateway 重启恢复已经完成；
- 尚未完成外部商家 Connector、真实 Candidate Promotion、生产多租户权限与容量压测；
- 公开数据证明系统行为和可复算性，不证明真实业务提升。

## 4. 面试现场失败预案

- 模型不可用或余额不足：停止真实调用，展示冻结审计，不切换模型、不回放缓存冒充 fresh Gate；
- 上传或文件选择器失败：打开已通过的同一持久化 Thread，并展示六文件截图、冻结输入 Hash 和浏览器审计；
- Gateway 临时异常：重启后读取 SQLite Checkpointer/Store 中的同一 Thread/Run，展示 3 个 Task、104 条 Run Event、15 条消息和最终答案恢复证据；
- 时间不足：优先保留动态 Subagent、fresh Verifier、真实失败调优和 Skill Evolution，省略 Action 细节；
- 面试官追问业务效果：只回答工程门禁和公开数据事实，不转换成 GMV、转化率、利润或因果提升。

## 5. 演示后可展示的证据

| 主题 | 证据 |
|---|---|
| v7 真实模型通过 | `docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/README.md` |
| v7 通过审计 | `docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/passed-dynamic-release-audit.json` |
| v7 失败与根因 | `docs/progress/runs/2026-07-27-commerce-chat-subagent-gate-v7/failed-before-negation-aware-guard.json` |
| 持久化浏览器 Gate | `docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/passed-browser-audit.json` |
| 最终 Chat 截图 | `docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/02-final-chat-desktop.png` |
| 协作空间桌面/移动端 | `docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7/03-collaboration-desktop.png`、`04-collaboration-mobile-reduced-motion.png` |
| 原创协作空间资产 | `docs/design/commerce-collaboration-imagegen-assets-v1.md` |
| 前端专项 E2E | `frontend/tests/e2e/commerce-agent-chat-collaboration.spec.ts` |
| Dynamic Release | `backend/app/commerce/evaluation/chat_dynamic_release.py` |
| 最终答案 Guard | `backend/packages/harness/deerflow/agents/middlewares/final_answer_policy_middleware.py` |
| Skill Evolution | `backend/app/commerce/evaluation/skill_evolution.py` |
| PostgreSQL Gate | `backend/tests/commerce/persistence/test_postgres_integration.py` |

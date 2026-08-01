# Commerce Chat 持久化浏览器 Gate v7

> 日期：2026-07-27  
> 结论：PASS  
> 证据类型：真实本地账号、真实六文件上传、fresh DeepSeek V4、持久化 Thread/Run、同源 Task/Event 协作空间

## 1. 验收对象

冻结输入为 `evals/commerce/cases/GC-FULFILLMENT-001/input` 下的六个公开 Olist CSV：

```text
orders.csv
order_items.csv
order_reviews.csv
customers.csv
products.csv
sellers.csv
```

浏览器通过真实本地注册/登录、Cookie、CSRF 和 Commerce Workspace 预检后，在 DeerFlow 中文 Chat 中选择六个文件并提交冻结问题。Gate 不使用 Mock、Replay、缓存回答或模型回退。

## 2. 持久化 Run

```text
thread_id=63c65e2a-9dd2-4a2e-8cf5-c7484c0d1c48
run_id=1c07e293-8f41-4213-b406-17c8c150f8d8
status=success
configured_alias=deepseek-reasoner
actual_model_identity=deepseek-v4-flash
retry_policy=0
retry_count=0
```

模型与用量：

```text
run.llm_call_count=6
provider_request_ids_unique=13
total_input_tokens=161,301
total_output_tokens=9,093
total_tokens=170,394
lead_agent_tokens=124,966
subagent_tokens=45,428
middleware_tokens=0
```

`run.llm_call_count` 是 Run 投影中的 LLM 调用计数；13 个 Provider Request ID 是从 Run、Message、Task 与 Event 的持久化遥测中收集并去重后的请求证据，两者不是同一统计口径。

## 3. 真实动态拓扑

三个 Durable Task 均为 `completed`：

```text
Explore  ─┐
          ├─ 首轮真实并行 ─→ fresh Verifier ─→ Parent 中文综合
Analyst  ─┘
```

- Explore 与 Analyst 在同一秒创建并真实重叠执行；
- Explore 先完成，Analyst 随后完成；
- Verifier 在首轮任务终态后创建，并引用持久化 lineage；
- Subagent Token 为 45,428，不是 Parent 文案模拟出来的“协作”；
- Chat 底部、协作空间角色与任务 Drawer 都读取同一 Task/Event 数据。

## 4. 最终答案事实

最终中文答案包含并正确使用以下确定性结果：

```text
卖家订单总数：554
精确可用范围：2017-12-02T06:32:02Z 至 2018-05-31T13:19:59Z

baseline：141 单，晚到率 3.55%（5/141）
current：202 单，晚到率 35.15%（71/202）

卖家处理时长：50.06h → 46.84h，下降 6.4%
承运运输时长：300.51h → 494.83h，上升 64.7%
总履约时长：360.78h → 550.16h，上升 52.5%
```

结论保持观察性边界：变化集中在承运运输阶段，卖家处理阶段未观察到恶化；当前数据不能断言具体承运商、路线或地域因果，也不推断曝光、点击、加购、广告、库存、利润或 GMV。

## 5. 重启恢复

Gateway 使用 SQLite Checkpointer、AsyncSqliteStore 和 DB Run Events。完整 Run 成功后重启 Gateway，仍恢复：

```text
Run status=success
Task count=3
Run Event count=104
AI Response Event count=6
Message count=15
最终答案仍存在
```

浏览器 Gate 支持“续审已有 Run”模式。续审只登录同一账号并读取同一 Thread/Run，不上传文件、不提交 Prompt、不创建新 Run，因此不会因为后置视觉断言失败再次消耗模型 Token。

## 6. 视觉证据

- `01-files-selected-desktop.png`：六文件选择与中文 Chat 首屏；
- `02-final-chat-desktop.png`：最终中文答案、3 个协作任务和按需协作空间入口；
- `03-collaboration-desktop.png`：真实 Analyst、Explore、Verifier 角色与任务 Drawer；
- `04-collaboration-mobile-reduced-motion.png`：390px 窄屏与 reduced-motion；
- `passed-browser-audit.json`：模型身份、Token、Request ID、retry、Task 拓扑、最终答案与截图清单。

自动续审结果为 `1 passed`，页面 Console Error 为空。已知非阻塞 UX 债务是 Drawer 中 Dataset ID/ISO 时间偏工程化，以及桌面 Drawer 会遮住部分第三工位；这些问题不改变任务数量、状态或证据来源。

## 7. 调优摘要

1. `127.0.0.1` 与 `localhost` 来源差异导致 Hydration 问题，统一浏览器入口；
2. 上传 403 推动真实本地账号、Cookie 与 CSRF 预检；
3. 只记录 alias 无法证明真实模型，补齐服务端 identity 与 terminal-chunk 遥测；
4. Parent 只口头派工、没有 `spawn_task`，被 Requirement Gate 拦截；
5. DeepSeek V4 thinking 不支持 `tool_choice=required`，直接请求返回 400；
6. 最终使用同一个 V4：业务轮保留 thinking，派工控制轮临时关闭 thinking 并要求正式 Tool Call；
7. 禁用 thinking 时不回放历史 `reasoning_content`；
8. Checkpointer/Store/Run Event 切到 SQLite/DB，完成重启恢复；
9. 增加 same-run 续审，避免重复花费模型 Token。

这条链路没有伪造 Tool Call、提高 retry、切换模型或把历史 Replay 冒充 fresh Gate。

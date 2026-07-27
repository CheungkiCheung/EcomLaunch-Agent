# Commerce Agent Run React 收口记录

日期：2026-07-23

## 结果

顶层“运行记录”页面已经完成 Image-first 设计、严格前端合同、View Model、React、主 Shell 导航接入、真实浏览器机械交互、桌面/移动截图和回归验证。

该页面用于检查一次已经持久化的智能体运行，不播放假忙碌动画，也不展示隐藏推理正文。它从权威 `Run`、`DomainEvent` 和 `GoalLoopCheckpoint` 读取并展示：

- 跨 Case Run Queue、状态筛选和中文搜索；
- 目标、能力路由、并行路径、证据屏障、主智能体综合、新鲜上下文验证和停止阶段；
- 0–3 条 requested Path 的同级 fan-out，不把并行路径画成串行链；
- Path 完成、阻塞、运行和未开始状态，以及持久化证据数量；
- 实际模型身份、唯一提供方请求编号、令牌用量、总延迟、重试和原始停止原因；
- 循环、工具、路径和令牌预算；
- 最新 Checkpoint 的序号、循环、Evidence、Hypothesis 和上下文摘要状态；
- 可展开的领域事件与 Checkpoint 审计列表；
- 乱序事件按 `run_sequence` 重排时的显式提示；
- 无遥测、无事件或无 Checkpoint 时的“未观察”，不会用零或完成态替代缺失值。

“运行记录”位于左侧“更多”下，是非 Case 工程检查页：没有 Chat Composer，Inspector 默认不打开，返回按钮只回到对应 Case，不自动启动新 Run。

## Image-first 资产

选中的高保真视觉稿：

```text
docs/design/commerce/mockups/agent-run-visual-v1-desktop.png
SHA-256: e82821a2d9ad3b3657d85e3a2c0e235d0051105437f4d40c93cc09272ea4b3e0

docs/design/commerce/mockups/agent-run-visual-v1-mobile.png
SHA-256: 53d70fd1f6655d46b837f82deb9722b2fb41274a94dc42bb833696e163c6b5a6
```

最终 React 截图：

```text
docs/design/commerce/implementation/agent-run-react-desktop-v1.png
尺寸: 1536 × 1024
SHA-256: 045e84e1de9ff0b8a3e9af2debd4f75de6c6378d0cc3b0e2cdc2ccb87227f082

docs/design/commerce/implementation/agent-run-react-mobile-v1.png
尺寸: 390 × 844
SHA-256: 8fae6b36976e707aef0a8200f0cd8b836d729f119c336513caab1ca8bdaf15ec
```

移动实现没有裁切桌面三栏：Run Queue 合并为一个可点击选择卡，运行图和工程详情进入正常纵向文档流；零计数筛选在窄屏隐藏，页面没有横向溢出。

## Evidence Barrier 边界

真实后端当前没有独立的：

```text
evidence.barrier_released
```

因此前端没有沿用旧机械 Mock 中的虚构事件。当前确定性投影规则是：

```text
全部 requested Path 已进入 completed / blocked 终态
AND
真实 lead.started 或 lead.completed 领域事件存在
→ Evidence Barrier 显示完成
```

页面同步显示：

```text
由全部路径终态与主智能体启动事件确认
```

如果 Path 阻塞且主智能体没有启动，Barrier 保持阻塞或未开始；如果缺少事件，页面不会通过计时器或 Run 完成状态补出一个不存在的领域事件。

## 关键实现文件

```text
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/agent-run-view-model.ts
frontend/src/core/commerce/index.ts
frontend/src/components/commerce/agent-run.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/run-api.test.ts
frontend/tests/unit/core/commerce/agent-run-view-model.test.ts
frontend/tests/unit/components/commerce/agent-run.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/agent-run-visual-v1.md
```

## 验证证据

前端：

```text
pnpm exec tsc --noEmit
PASS

pnpm exec eslint <Agent Run scoped files>
PASS

pnpm test -- --run
46 files / 272 tests passed

pnpm exec playwright test tests/e2e/commerce-master-shell.spec.ts
11 passed

pnpm exec next build --webpack
PASS
```

浏览器场景验证了：

- “更多 → 运行记录”导航拥有独立 `aria-current`；
- 三条 Path 同级展示；
- 证据屏障派生边界可见；
- `deepseek-v4-flash`、5 个唯一请求编号、18,420 令牌、12.6 秒延迟和零重试来自结构化事件 payload；
- 最新 Checkpoint sequence 7、loop 1、Evidence 4、Hypothesis 1 和上下文摘要状态可见；
- 事件流展开后展示 12 条持久化事件；
- Case Composer 不存在；
- 1536 × 1024 桌面三段式布局与 390 × 844 移动文档流均无页面级横向溢出。

后端确定性合同：

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/api/test_run_router.py
6 passed, 1 LangChainPendingDeprecationWarning

.venv/bin/ruff check app/commerce/api/run_service.py app/commerce/api/router.py app/commerce/api/schemas.py tests/commerce/api/test_run_router.py
All checks passed
```

仓库诊断：

```text
git diff --check
PASS
```

## 验收边界

本次 Playwright 使用结构化 Mock API，只证明前端机械行为、严格响应解析、交互和响应式布局；没有把它当作 Agent Release Gate，也没有调用模型。

真实 DeepSeek V4 前端 Agent E2E 仍未完成。后续必须通过真实后端启动新的 Case Investigation Run，确认实际身份 `deepseek-v4-flash`、提供方请求编号、令牌、延迟、重试、事件和 Checkpoint 真实持久化后，再由浏览器读取同一 Run。模型不可用、身份无法确认、鉴权失败或额度不足时必须停止，不能改用 Mock、Replay 或其他模型证明通过。

## 后续

按照完整实施计划，下一页进入 `Skills & Evals` 的 Image-first 设计与实现；其后继续 War Room、Follow-up、Overview、Case-bound 问答、Approval modify、PostgreSQL、公开数据/Connector、真实模型前端 E2E、部署和秋招材料。

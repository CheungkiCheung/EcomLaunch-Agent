# Commerce Action Center：证据、策略、审批、执行与回滚

日期：2026-07-23

## 本次完成

Action Center 已从 Image-first 视觉稿推进到可运行的顶层工作页：

- 左侧主导航“行动中心”已启用并拥有独立高亮，不再是禁用占位；
- 按 Workspace 下的 Case 并行读取真实 Action Record，再读取选中 Action Detail；
- 支持全部、待处理、执行中、跟踪中、已结束筛选和中文关键词搜索；
- 桌面使用行动队列 + 详情文档双栏，移动端使用行动选择器 + 单栏详情；
- Action 标题、Case 技术标题、状态、风险、审批和策略均投影为中文；
- 从 `ValidatedActionDraft.parameters` 恢复真实执行参数，不从标题反推行动类型；
- 展示 Evidence / Hypothesis 引用数量，并明确工作假设不能单独证明因果；
- 展示服务端 Policy level、disposition、execution tool 和 Approval progress；
- 展示 Rollback strategy、trigger 和 verification；
- 支持等待审批状态的批准与拒绝，未达到审批人数前保持不可执行；
- 支持内部 Action 执行与可验证回滚，操作后重新读取权威 Action Detail 和 Artifact；
- 请求携带 Workspace、Actor 和稳定幂等键；同一操作重放只读取既有结果；
- 没有可审计 Actor 时批准、拒绝、执行和回滚保持禁用；
- 顶层 Action 页面没有 Chat Composer、模型、Token、Retry、Lease 或假 Agent 活动。

## Image-first 设计

本页使用当前会话提供的 `imagegen` Skill 和内置 Image Generation。Skill 直接影响了两项实现判断：

1. 桌面使用“行动队列 + 选中行动详情”而不是 Dashboard 卡片；
2. 移动端不裁切桌面双栏，改为“切换行动 + 正常文档流详情”，操作区不固定在底部。

视觉记录：

```text
docs/design/commerce/mockups/action-center-visual-v1-desktop.png
1536 × 1024
SHA-256：25776f03633de4f3e4d8c2f37f73c2570c200d9e22b03a597afb252042427900

docs/design/commerce/mockups/action-center-visual-v1-mobile.png
864 × 1821
SHA-256：91c6ec03fc5ff53c296e37da331f0e18d7983c9707d4017dcaf1118662bc842f
```

代表状态选择当前真实内部 Catalog 的 `create_metric_monitor`：中风险、策略 L2、内部可逆、无需审批。没有为了展示审批而伪造一个当前不可执行的外部商家写操作。

## 严格前端合同

新增并严格校验：

```text
ActionParameters 六类判别联合
Action / RollbackPlan / ApprovalRequirement
ValidatedActionDraft / ActionPolicyDecision / ActionRecord
ApprovalRequest / ApprovalDecisionResponse
ActionExecutionArtifact 五类判别联合
FollowUpRecord
ActionDetail / ActionExecutionResponse
```

后端缺少策略、审批、回滚或执行字段时，前端返回 `invalid_response`，不会猜测默认值。Action Detail 中的 Follow-up 也不再使用 `unknown` 占位。

## RED → GREEN 与视觉 QA

先新增不存在函数和组件的失败测试，确认：

```text
buildCommerceActionCenterViewModel is not a function
loadCommerceActionCenterSnapshot is not a function
Cannot find package '@/components/commerce/action-center'
```

实现后，浏览器截图又暴露两个真实缺陷：

1. 后端英文技术 Case 标题直接泄露到运营卡片；
2. 移动端“待执行”状态标签在窄列中换行。

随后增加本地化回归并修复为结构化中文 Case 标题，同时让状态 Chip 保持单行。

React 实现截图：

```text
docs/design/commerce/implementation/action-center-react-desktop-v1.png
1280 × 720
SHA-256：7d276edcc108337fdde09f0d3a42c36221d5e417b76d2b884e0296502546fca2

docs/design/commerce/implementation/action-center-react-mobile-v1.png
390 × 844
SHA-256：97ecc5ff70082253d778232e69ebe72c3c1c0d360ab8ba7d915dfec4e202d740
```

两张截图均由真实 Chromium 页面生成并人工检查。桌面端没有固定 Chat 层；移动端没有固定底部操作层或横向页面溢出，筛选项保留为可横向滚动的紧凑控件。

## 验证证据

```text
Frontend Vitest：43 files / 267 tests passed
Frontend TypeScript：PASS
Frontend scoped ESLint：PASS
Frontend Prettier：PASS
Frontend Playwright：10 passed（单 Worker，Mock API 机械交互）
Production build：next build --webpack，PASS
Backend deterministic Action Router：4 passed
Backend scoped Ruff：PASS
git diff --check：PASS
```

浏览器场景实际完成：

```text
Action policy_checked
→ 执行
→ Action monitoring + active Metric Monitor Artifact
→ 回滚
→ Action rolled_back + disabled Artifact
```

另有 Unit 合同覆盖 L4 两人审批：未批准时 `canExecute=false`，批准/拒绝入口可用，审批进度为 `0 / 2`。

## 尚未宣称完成

- 本轮前端 Playwright 是结构化 Mock API 机械验收，后端 Router 测试是确定性测试；两者都没有调用模型，不能作为 fresh DeepSeek V4 Action Planner 或完整 Agent Release Gate；
- Approval `modify` 的后端不可变替换合同已存在，但本页尚未提供通用参数编辑表单；当前前端支持批准与拒绝；
- Follow-up 的启动与结果解释属于后续 Follow-up 页面；
- 外部商家 Connector 仍然 fail closed，Action Center 不会绕过服务端策略启用它；
- Workspace membership 和生产鉴权仍是最终部署门禁。

## 关键文件

```text
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/action-center-view-model.ts
frontend/src/components/commerce/action-center.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/action-api.test.ts
frontend/tests/unit/core/commerce/action-center-view-model.test.ts
frontend/tests/unit/components/commerce/action-center.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/action-center-visual-v1.md
```

Action Center 的页面门禁与批准 / 拒绝 / 执行 / 回滚主路径已完成。后续 Agent Run 页面继续遵循：

```text
Image Generation → 视觉选择记录 → API/View Model RED → React → 浏览器交互 → 截图 QA
```

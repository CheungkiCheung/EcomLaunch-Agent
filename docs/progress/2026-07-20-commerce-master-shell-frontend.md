# Commerce Master Shell Frontend

日期：2026-07-20

## Outcome

完成第一个正式 Commerce 前端页面 Master Shell：

```text
中文 Codex-inspired 视觉母版
→ 用户确认
→ Domain Event View Model RED
→ strict Commerce API Client
→ React Master Shell
→ 桌面 / 移动真实 Chromium QA
```

路由：

```text
/commerce
```

Feature Flag 关闭时路由 404；Workspace ID 缺失时显示 fail-closed 中文配置状态。

## TDD

RED：

```text
2 suites failed
Cannot find @/core/commerce
```

GREEN：

```text
31 test files passed
237 tests passed
```

覆盖：

- 英文后端 Case 到中文 Case-first View Model；
- Event 按 `case_sequence` 权威重排；
- 未知 Event 中文显式降级，不泄露未知英文类型；
- 空 Case 时不生成假 Agent 活动；
- DeepSeek V4、Retry、Lease 只由结构化事件投影；
- API 必须携带 `X-Commerce-Workspace-Id`；
- 非法响应 fail closed；
- 服务端渲染中文层级，不出现英文用户标签。

## Implemented

```text
frontend/src/app/commerce/layout.tsx
frontend/src/app/commerce/page.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/index.ts
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/view-model.ts
frontend/tests/unit/core/commerce/
frontend/tests/unit/components/commerce/
frontend/tests/e2e/commerce-master-shell.spec.ts
```

主要能力：

- strict Zod response contracts；
- 真实 Case List / Detail / Events / Runs GET；
- 中文 Case 标题、状态、Evidence、Hypothesis、Action 和 Runtime 投影；
- 乱序和未知事件；
- Case 切换；
- Timeline / Evidence / Run 三视图；
- 桌面浮动 Inspector；
- 移动 off-canvas Sidebar / Inspector；
- Runtime Drawer；
- 空、错误、503、404、配置缺失状态；
- Reduced Motion、焦点样式和语义区域；
- 未接线 Composer 不伪造发送或 Agent 运行。

## Browser QA

Playwright UI mechanics：

```text
3 passed in 23.0s
```

覆盖：

- 中文 Case 页面；
- Evidence tab；
- Runtime 展开；
- 未接线输入提示；
- Case 切换；
- 390 × 844 off-canvas；
- 无横向溢出。

真实浏览器截图：

```text
docs/design/commerce/implementation/master-shell-react-desktop-v1.png
docs/design/commerce/implementation/master-shell-react-mobile-v1.png
```

桌面 `1440 × 900`、移动 `390 × 844`，两者控制台 warning/error 都为 0。移动端：

```text
scrollWidth=390
clientWidth=390
```

## Verification

```text
Vitest: 31 files / 237 tests passed
TypeScript: passed
Scoped ESLint: passed
Playwright Commerce: 3 passed
Next production build: passed
git diff --check: passed
```

Production build 仍报告一个已有的 Turbopack NFT trace warning，导入链来自 Legacy mock artifact route 与 `next.config.js`，不是 Commerce 新页面。

仓库级 `pnpm check` 仍被 Legacy EcomLaunch 的既有 `5 errors / 2 warnings` 阻塞。本阶段遵循 Legacy 只读边界，没有借机修改旧 War Room；Commerce 新增目录的限定 ESLint 已通过。

## Honest Boundary

Playwright 使用结构化 mock Commerce Read API，只验证 UI 机械行为。它不调用模型，也不验证 Agent 输出，不能计入 DeepSeek V4、Agent Integration 或 Commerce Release Gate。

尚未接线：

- Case-bound 问答；
- Data Intake；
- Action 查看 / 审批 / 执行；
- 实际 Connector；
- Engineer audit view；
- 真实后端前端 E2E。

## Next

按照已确定顺序，进入 Case Detail：

```text
Image Generation
→ 用户确认
→ 组件 / 事件合同
→ TDD React
→ 浏览器 QA
```

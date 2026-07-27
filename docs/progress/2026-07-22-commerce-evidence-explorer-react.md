# Commerce Evidence Explorer：证据浏览与页面密度收口

日期：2026-07-22

## 本次完成

Evidence Explorer 已从 Image-first 视觉稿收口为 Case Detail 的真实证据浏览页签：

- 支持、矛盾、未知三种证据关系同级展示、筛选和关键词搜索；
- Evidence、Metric Observation、Fact ID、Hypothesis 和 Evidence boundary 分层投影；
- 英文后端摘要在有结构化指标引用时恢复为中文指标变化，不能恢复时保留诚实的未完成提示；
- Metric 引用展示中文指标名、值、单位、窗口及基线/当前语义；
- Fact 详情尚未开放时只显示可审计编号和“原始事实详情尚未开放”，不编造事实内容；
- supporting / contradicting evidence IDs 反向关联到工作假设；
- 桌面使用证据列表 + 详情双栏，移动端使用选中证据内联详情；
- 概览页保留 Case-bound Composer，调查记录、证据和运行页不再显示固定 Composer，避免遮挡检查内容；
- 没有证据时显示空态，不从聊天、CSS 动画或计时器生成证据或 Agent 活动。

## Image-first 设计与 QA

视觉选择记录在 [`docs/design/commerce/evidence-explorer-visual-v1.md`](../design/commerce/evidence-explorer-visual-v1.md)。初始移动视觉稿的第三条证据误显示为 `35%`，人工 QA 发现后只修正该数字为 `93%`，修正版作为实现基准；没有借此改动业务数据合同。

实现截图由真实 Chromium 页面生成：

```text
docs/design/commerce/implementation/evidence-explorer-react-desktop-v1.png
1280 × 720
SHA-256：79a59d4e920fecffddeccd8c6ef05e194e6560837fc72edab756a4eb00968658

docs/design/commerce/implementation/evidence-explorer-react-mobile-v1.png
390 × 844
SHA-256：3a3576e088f277805a4fe99447f31fe7f550a307317ef3c6869ab997244470d8
```

桌面截图确认详情栏下方没有被固定输入层覆盖；移动截图确认展开详情仍在正常文档流中，没有横向溢出。结构化 Mock API 的示例值为 `4.8% → 36.4%`，不是视觉稿示例 `3.5% → 35.1%`；页面读取的是测试 API 返回的真实合同值，没有为了匹配图片写死数字。

## RED → GREEN 证据

先新增 Playwright 失败断言，要求 Composer 只在概览页可见。旧实现无条件渲染 Dock，切到“调查记录”时断言失败：

```text
Expected: not visible
Received: visible
```

最小修复是让 `CommerceBottomDock` 仅在 `centerView === "overview"` 时挂载，并同步将原有案例详情测试的问答操作移到概览页、在运行页断言隐藏。未改变 Composer 的发送语义：当前仍诚实提示内容没有发送，也没有启动新的调查。

## 验证证据

```text
Frontend Vitest：40 files / 260 tests passed
Frontend TypeScript：PASS
Frontend scoped ESLint：PASS
Frontend Prettier：PASS
Frontend Playwright：9 passed（单 Worker，Mock API 机械交互）
Production E2E build：next build --webpack，PASS
git diff --check：PASS
```

本轮 Playwright 使用结构化 Mock API，只验证前端页面合同、交互和响应式布局，不调用模型；它不是 DeepSeek V4 Agent Release Gate。真实 Agent 行为仍必须通过服务端 `real_model_preflight`，确认 fresh `deepseek-v4-flash` 身份、请求 ID、Token、Latency、Retry 和 Stop Reason 后才能验收。

## 关键文件

```text
frontend/src/core/commerce/evidence-explorer-view-model.ts
frontend/src/components/commerce/evidence-explorer.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/evidence-explorer-view-model.test.ts
frontend/tests/unit/components/commerce/evidence-explorer.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/evidence-explorer-visual-v1.md
```

Evidence Explorer 的页面门禁已完成。下一阶段进入 Action Center，仍按：

```text
Image Generation → 视觉选择记录 → API/View Model RED → React → 浏览器交互 → 截图 QA
```

# Commerce Case Queue：任务队列与 Explicit Case 创建闭环

日期：2026-07-22

## 本次完成

Case Queue 已从 Image-first 候选推进为可运行页面：

- “案例队列”是独立页面状态，不再等价于打开列表第一条 Case；
- 读取真实 `GET /api/commerce/cases`，按严重度和更新时间排序；
- 根据权威 `CaseStatus` 分成“需要你处理 / 持续跟踪 / 已结束”；
- 支持全部、待调查、等待数据、等待审批、执行中、跟踪中筛选；
- 支持中文标题、后端原始标题和摘要关键字搜索；
- 无中文摘要时显示诚实降级，不泄露英文后端文案，也不编造业务判断；
- 从队列打开真实 Case Detail；
- 从 Capability Report 点击可用路径后，进入队列并预选对应分析路径；
- 创建侧栏要求数据批次、经营主体、基线窗口、当前窗口与 1–3 条路径；
- 卖家对标额外要求商品类目、最小订单数和是否匹配卖家所在州；
- 调用 `POST /api/commerce/datasets/{dataset_id}/cases` 后进入真实新 Case；
- 相同 Dataset、卖家、窗口和路径重复提交返回同一个内容寻址 Case，数据库只保留一条记录；
- Explicit Case 没有异常信号时使用“用户发起的履约诊断”等标题，不再伪装为已检测异常；
- 队列和创建侧栏均无 Chat Composer、模型、Token、Retry、Lease 或假 Agent 活动。

## RED → GREEN 发现

### 1. Case Queue 原来只是 Case Detail 的别名

浏览器 RED 点击“案例队列”后找不到“需要处理的经营问题”。实现独立 `queue` section 后，页面导航、标题、刷新和当前 Case 高亮各自归属清晰。

### 2. Explicit Case 被错误命名为异常

创建合同返回 `signals=[] / anomalies=[]`，但旧 View Model 会根据上下文中的履约指标显示“履约延迟异常”。新增无异常回归后，显式请求改为“用户发起的履约诊断 / 评价诊断 / 卖家对标”。

### 3. Dataset 加载态被误判为空态

Capability 切换到 Queue 时，创建侧栏会重新恢复 Dataset。旧实现短暂显示“没有数据批次”；现在显式区分“正在读取创建案例所需的数据能力”和真实空态。

### 4. 原生日期控件泄露英文占位

Chromium 的 `datetime-local` 根据浏览器区域显示 `mm/dd/yyyy`。当前改为明确的数字时间文本格式，并在提交前统一规范化为 `YYYY-MM-DDTHH:mm:ss`。

### 5. TSX 组件测试没有被 Vitest 收集

原 `vitest.config.ts` 只包含 `.test.ts`，三个已有 Commerce `.test.tsx` 文件没有真正进入 247 测试统计。现在收集规则为 `tests/unit/**/*.test.{ts,tsx}`，组件层级测试实际执行，当前全量为 38 files / 257 tests。

## 关键文件

```text
frontend/vitest.config.ts
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/case-queue-view-model.ts
frontend/src/core/commerce/view-model.ts
frontend/src/components/commerce/case-queue.tsx
frontend/src/components/commerce/capability-report.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/case-queue-view-model.test.ts
frontend/tests/unit/core/commerce/api.test.ts
frontend/tests/unit/core/commerce/view-model.test.ts
frontend/tests/unit/components/commerce/case-queue.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
backend/tests/commerce/api/test_explicit_case_service.py
```

## 验证证据

```text
Frontend Vitest：38 files / 257 tests passed
Frontend TypeScript：PASS
Frontend scoped ESLint：PASS
Frontend Prettier：PASS
Frontend Playwright：7 passed
Production E2E build：next build --webpack + next start，PASS
Backend Explicit Case：5 passed
```

Playwright 仍固定为单 Worker，原因与前一阶段一致：当前 Next production server 在 5 Worker 下出现过偶发加载态，尚未独立定位并发根因。

## 视觉资产

Image Generation 选中稿：

```text
docs/design/commerce/mockups/case-queue-visual-v1-desktop.png
SHA-256：3971d088d043ff8c49f7c9b51bd5fb98e15192a185c8d17dc2dd95f14cc3d467

docs/design/commerce/mockups/case-queue-visual-v1-mobile.png
SHA-256：52926d7189f711fcbecfcfd619adbdafd41b49cc4333971733833bece9a80010
```

React 实现截图：

```text
docs/design/commerce/implementation/case-queue-react-desktop-v1.png
SHA-256：630c76b55fef7a5e6d335f579b1e1cc3d22aaeb0ab1a2bc7f6413316e26fb2eb

docs/design/commerce/implementation/case-queue-react-mobile-v1.png
SHA-256：15e5bf9e274dda8d4a84db528f473cba019be44d4ca8a7502f4369cc91af4b22

docs/design/commerce/implementation/case-queue-react-create-v1.png
SHA-256：f103982c07036978ba8ba43606884ba6744293d793aeebaa1b675d8038d79045
```

## 尚未宣称完成

- 当前 7 个 Playwright 场景使用结构化 Mock API，只证明机械 UI 合同；
- Backend Explicit Case 测试证明真实服务合同、无异常保护和内容寻址幂等，但完整 Gateway + 登录 + Olist + 浏览器跨栈创建仍需纳入最终确定性产品 E2E；
- 创建 Case 不会自动启动 Agent Run；调查启动与 Case-bound 问答仍是后续闭环；
- 本阶段没有触达模型，不能作为 DeepSeek V4 Agent Release Gate。

下一步进入 Evidence Explorer 的 Image Generation 与证据列表/详情合同。

# Commerce Capability Report：能力边界与案例入口

日期：2026-07-22

## 本次完成

Capability Report 已从 Image-first 视觉稿推进到可运行 React 页面：

- 读取 Workspace 最新 Dataset Detail，不创建独立的前端真相源；
- 读取 `CapabilityProfile` 与 `SemanticMappingProfile`，纯函数投影三条首批分析路径；
- 显示“可直接分析 / 部分可分析 / 当前不可分析”及其确定性原因；
- 分开显示已观察与未观察字段，缺失的曝光、点击、加购、广告消耗、库存和利润不推断为零；
- 显示待确认字段并返回 Data Inbox；
- 可用或部分可用路径显示“创建案例”，不可用路径没有伪动作；
- 当前创建入口只提示需要补充分析窗口和经营主体，尚未伪造 Explicit Case；
- 非 Case 页面不显示 Chat Composer、模型、Token、Retry、Lease 或 Agent 活动；
- 顶栏刷新会重新读取 Dataset，而不是误刷 Case 列表；
- 桌面和移动端均保持单一操作层与无横向溢出。

## RED → GREEN 证据

视觉终检发现两个真实缺口：

1. 正文和工作区顶栏存在重复刷新；
2. 打开数据能力页后，当前 Case 仍占用 `aria-current="page"`，且顶栏刷新没有触发 Dataset 重载。

先扩展 Playwright 断言并确认失败：

```text
Expected current Case not to have aria-current="page"
Received aria-current="page"
1 failed
```

随后实施最小修复：删除正文刷新、让数据与能力页共享 `dataRefreshKey`、仅在 Case section 投影当前案例高亮。目标场景及全量 E2E 均恢复通过。

## 关键文件

```text
frontend/src/core/commerce/capability-report-view-model.ts
frontend/src/components/commerce/capability-report.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/capability-report-view-model.test.ts
frontend/tests/unit/components/commerce/capability-report.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/capability-report-visual-v1.md
```

## 验证证据

```text
Frontend Vitest：34 files / 247 tests passed
Frontend TypeScript：PASS
Frontend scoped ESLint：PASS
Frontend Prettier：PASS
Frontend Playwright：6 passed
Production E2E build：next build --webpack + next start，PASS
```

Playwright 当前固定为单 Worker。原因不是放宽断言，而是当前 Next production server 在 5 Worker 下出现过偶发加载态；后续应单独定位并发根因。

## 实现截图

```text
docs/design/commerce/implementation/capability-report-react-desktop-v1.png
1280 × 720
SHA-256：b3f8c3604f6be0d2116f7c4171f496d8ed2f2cb80146e58e0c5dbb79990860a3

docs/design/commerce/implementation/capability-report-react-mobile-v1.png
390 × 844
SHA-256：fe31b3fc5af11ba0553a9e44d5c87518f08219905607dfcd412b89e009cddacf
```

两张截图均由真实 Chromium 页面生成并人工检查。桌面端保持数据能力页唯一导航高亮；移动端没有重复刷新、固定 Chat 层或横向溢出。

## 尚未宣称完成

- 本轮 E2E 是确定性 UI 机械验证，没有触达模型，不能作为 DeepSeek V4 Agent Release Gate；
- 真实 Gateway + Olist 的 Capability → Explicit Case 跨栈浏览器联调仍需在最终确定性产品 E2E 中覆盖。

2026-07-22 后续进展：Case Queue、筛选、等待状态、Capability 预选路径和 Explicit Case 表单已经接入，详见 `docs/progress/2026-07-22-commerce-case-queue-react.md`。

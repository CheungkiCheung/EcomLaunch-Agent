# Commerce Data Inbox：可恢复数据合同与中文 React 交互

日期：2026-07-21

## 本次完成

Data Inbox 已从视觉候选推进到可运行实现，覆盖：

- Workspace 范围的 Dataset 列表：`GET /api/commerce/datasets`；
- Dataset 详情恢复：`GET /api/commerce/datasets/{dataset_id}`；
- 真实 Manifest、文件来源、Profile、Semantic Mapping、Capability 与确认状态；
- Manifest 身份、存储路径、文件存在性、只读属性、文件大小和 SHA-256 校验；
- 损坏批次 fail closed，列表/详情返回明确的 409，而不是猜测可分析结果；
- Dataset 列表稳定按持久化 `created_at` 倒序分页，不使用目录 mtime 冒充业务时间；
- 语义确认按 Dataset 隔离保存，避免同一 Workspace 中多个批次的同名字段互相污染；
- 中文 Data Inbox 空态、上传审核态、文件选择/拖放、批次恢复、语义确认与移动响应式布局；
- 上传使用 `multipart/form-data`，语义恢复带 `X-Commerce-Actor-Id` 和幂等键；
- 未观察的曝光、点击、加购、广告消耗、库存、利润保持“未观察”，不推断为零；
- Data Inbox 不显示 Chat Composer、模型名、Agent 活动或伪造进度。

## 关键文件

```text
backend/app/commerce/data/intake.py
backend/app/commerce/data/semantic_mapper.py
backend/app/commerce/api/data_service.py
backend/app/commerce/api/schemas.py
backend/app/commerce/api/router.py
backend/tests/commerce/api/test_data_intake_router.py
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/data-inbox-view-model.ts
frontend/src/components/commerce/data-inbox.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
```

## 验证证据

```text
Backend Data / API tests：43 passed
Backend semantic isolation + intake API：11 passed
Frontend Vitest：34 files / 247 tests passed
Frontend TypeScript：PASS
Frontend scoped ESLint：PASS
Frontend Prettier：PASS
Frontend Playwright：6 passed（Webpack production build，单 Worker）
```

浏览器机械流程覆盖：

```text
导航到数据接入
→ 空态显示
→ multipart 上传 orders.csv
→ Dataset 列表/详情恢复
→ 显示字段语义待确认
→ 带操作人确认
→ 刷新后进入已确认状态
```

实现截图：

```text
docs/design/commerce/implementation/data-inbox-react-empty-v1.png
docs/design/commerce/implementation/data-inbox-react-review-v1.png
```

截图由真实 Chromium 页面生成；视觉系统沿用已确认的浅色、克制、文档式 Commerce Shell。Next 构建仍会报告 Legacy mock artifact route 的既有 Turbopack NFT tracing warning，但不影响构建或测试通过。

```text
data-inbox-react-empty-v1.png
SHA-256：b3251dda076d9719e0e6855be2efc905f5e80f2c0ff12ec9b9345ce8a1b14130

data-inbox-react-review-v1.png
SHA-256：50771c8998ab1c3c63c2df4eb5d09f133b5affc2db012cb55cfbd0b8085b65a5
```

Next 16.2.6 默认 Turbopack 构建在当前仓库没有生成 `BUILD_ID`，无法直接交给 `next start`；机械 E2E 因此使用 `next build --webpack && next start`。本地生产服务器在 5 个并行 Worker 下曾偶发停留在加载态，当前固定为 1 个 Worker，等待独立定位并发根因后再提高并行度。

## 尚未宣称完成的部分

Data Inbox 已可进入 Capability Report；后续 Case Queue 和 Explicit Case 创建仍未接入。真实 Gateway + Olist 浏览器验证仍需重新覆盖 Dataset 列表/详情和实际文件上传；本次 Playwright 6 个场景是机械 UI 合同验证，不是 DeepSeek V4 Agent Release Gate。

# Commerce Case Detail v2 React 与真实数据验收

日期：2026-07-20

## 结论

Case Detail v2 已完成从确认视觉稿到 React、确定性后端读模型、结构化合同、真实 Olist 数据联调、桌面/移动浏览器交互和截图 QA 的完整闭环。

本阶段没有调用模型，也没有把 Mock 结果当作 Agent 验收。页面既通过结构化 Mock API 的机械交互测试，也通过本地真实 Gateway、真实 SQLite Commerce 表和冻结的 `GC-FULFILLMENT-001` 公开数据切片完成读取验收。

## 后端读模型

`GET /api/commerce/cases/{case_id}` 现在返回：

```text
Case
+ Lineage
+ Evidence
+ latest Hypothesis
+ verified deterministic Analysis
+ Action summaries
```

关键实现：

- `ContextPacketLoader.load_case_analysis()` 复用 Artifact 路径、SHA-256、身份、Capability、Metric 与 Anomaly 引用校验；
- 该读路径不构造 Agent Prompt，也不受 Agent Token Budget 影响；
- `CommerceReadService` 读取经过校验的 Analysis Artifact 和 Workspace/Case-scoped Action；
- Analysis 无法读取时返回明确的 `unavailable_reason`，不由前端猜测；
- Decimal 以字符串跨 API 边界，避免指标精度损失。

## 前端实现

默认概览收敛为：

```text
发生了什么
→ 当前判断
→ 证据边界
→ 下一步
```

已实现：

- 中文 Case-first 页面与四个页签；
- 真实 Anomaly / MetricObservation 的周期对比；
- 相关性与因果限制；
- 对象级 Evidence Inspector / Drawer；
- 默认关闭 Inspector，工程遥测进入“运行”；
- 单层紧凑 Composer；
- 桌面可折叠侧栏与移动抽屉；
- 当前 Case 在尚未启动 Path 时，按首要确定性指标命名为“履约延迟异常”或“评价体验异常”；
- `critical` Case 使用红色风险标记；
- 未接通的 Action、问答和上传入口保持禁用或明确说明没有发送、执行或启动调查。

## 真实数据联调

真实浏览器验收使用：

```text
数据：evals/commerce/cases/GC-FULFILLMENT-001/input/*.csv
Workspace：wsp_0123456789abcdef0123456789abcdef
数据库：本地运行时 SQLite，已执行 Commerce 独立 Alembic upgrade head
认证：通过本地注册/登录 UI 创建隔离 QA 账户
```

实际链路：

```text
POST /api/commerce/datasets/intake → 201
POST /api/commerce/datasets/{dataset_id}/analyze → 200
GET /api/commerce/cases → 200
GET /api/commerce/cases/{case_id} → 200
GET /api/commerce/cases/{case_id}/events → 200
GET /api/commerce/cases/{case_id}/runs → 200
```

真实结果：

- 1 个 Case；
- 5 个确定性 Anomaly Signal；
- 5 条 append-only Evidence；
- 首要指标为 `late_delivery_rate`；
- 上一周期 `3.5%`；
- 当前周期 `35.1%`；
- 变化 `+31.6 个百分点`；
- 当前没有 Investigation Run、Verification 或 Action，因此界面诚实显示“待调查”“尚未完成独立验证”“尚无候选行动”。

## 真数据发现并修复的问题

### 1. 数据源本地时间被前端合同拒绝

Olist Metric Window 使用不带时区的源数据本地时间，例如：

```text
2018-01-31T00:00:00
```

原前端只接受带 offset 的审计时间，导致整个 Case Detail fail closed。现在仅 Metric Window 接受严格格式的 source-local datetime；Case、Event、Run 和审计时间仍要求带 offset。

### 2. 桌面折叠后移动抽屉丢失内容

原实现用 React 条件渲染隐藏“更多”和“当前案例”。在桌面折叠后切到移动断点，这两个区块不会恢复。现在区块始终存在，只在桌面折叠断点通过 CSS 隐藏，移动 Drawer 始终完整。

### 3. 未运行 Path 的 Case 标题过于泛化

确定性异常创建后尚无 `path.*` Event，原页面只能显示“系统检测到的经营异常”。现在活动 Case 可以根据首要确定性 Metric 映射为“履约延迟异常”“评价体验异常”或“卖家对标异常”，不需要伪造 Agent 路由。

## 验证证据

### 后端

```text
Ruff check：PASS
Ruff format --check：PASS
pytest：17 passed, 1 LangGraph PendingDeprecationWarning
```

### 前端

```text
Vitest full suite：32 files, 240 tests passed
TypeScript：PASS
Scoped ESLint：PASS
Scoped Prettier：PASS
Next production build：PASS
Playwright Commerce E2E：4 passed
git diff --check：PASS
```

Next build 仍报告 Legacy mock artifact route 的 Turbopack NFT tracing warning；该 warning 不由本次 Commerce 文件引入，构建本身成功。

### 浏览器与视觉

- 真实本地注册、登录、Data Intake、Analyze 和 Case Read 全部成功；
- 桌面默认、Evidence Inspector、390×844 移动概览、移动导航抽屉均完成交互检查；
- 390×844：`scrollWidth = clientWidth = 390`；
- 浏览器 Console error/warn：0；
- 右侧 Inspector 关闭时中心恢复双栏，打开时对象内容完整；
- 移动端只有 Composer 一个固定底部层。

实现截图：

```text
docs/design/commerce/implementation/case-detail-react-desktop-v1.png
SHA-256 85b8f16f327c57c169ea6bfb37c516770c4e1ac366f08d4f0331ef1563954f0c

docs/design/commerce/implementation/case-detail-react-evidence-inspector-v1.png
SHA-256 79a50cbb21ca230c26667b52cee860db1bb90b07c59fc895a0c04ea034d126c5

docs/design/commerce/implementation/case-detail-react-mobile-v1.png
SHA-256 0dadc43d87eafa08c161c4dc1162285bcfe9addc8e44b049d852867dd2c7d0ca
```

## 未声称完成的能力

- Case-bound 问答尚未发送到 Lead Loop；
- Data Inbox 尚未提供真实上传 UI；
- Action Center 尚未接审批、执行、回滚和 Follow-up 页面；
- 本次没有 Investigation Run，因此没有运行新的 DeepSeek V4 Agent 行为测试；
- Mock API Playwright 只证明 UI 机械行为，不能替代后续真实 DeepSeek V4 Agent E2E。

下一阶段进入 Data Inbox 的视觉稿与数据接入产品合同。

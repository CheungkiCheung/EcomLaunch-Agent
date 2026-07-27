# 电商经营诊断 Case Queue 视觉稿 v1

## 状态

- 使用内置 Image Generation 于 2026-07-22 生成桌面与移动高保真候选；
- 两版均已人工检查并选中；
- 视觉系统延续已确认的浅色、克制、Codex-inspired 文档式 Commerce Workspace，不复制 Codex 品牌资产；
- 下一步进入 API、View Model 与交互合同的 RED 阶段。
- React、Explicit Case 交互、真实 Chromium 机械 E2E 与桌面/移动截图 QA 已完成。

## 用户任务

案例队列不是一个“异常数量 Dashboard”，而是运营人员的工作入口。它优先回答：

```text
我现在有哪些经营问题需要处理？
哪个最紧急？
哪些在等待数据、审批、执行或跟踪？
我能否创建一个范围明确、可追溯的 Case？
```

## 关键视觉决定

- 左侧只有“案例队列”拥有当前页高亮；已有 Case 仍作为上下文可见，但不占用当前页状态；
- 主内容采用“筛选 → 需要你处理 → 持续跟踪”的任务流，不做 KPI 仪表盘；
- 列表行直接使用真实 `CaseStatus`：待调查、调查中、等待数据、等待审批、行动执行中、跟踪中；
- 风险、摘要、经营主体、分析窗口、路径和更新时间在同一行渐进披露；
- 桌面端用紧凑文档列表，移动端用纵向卡片，不把桌面表格压进窄屏；
- 顶部保留一个“创建案例”入口；创建表单必须要求 Dataset、经营主体、基线窗口、当前窗口和分析路径；
- 从 Capability Report 进入时，预选用户点击的可用路径，但不绕过其余必填范围；
- 无 Chat Composer、模型名、Agent 活动、Token、Retry、Lease、Inspector 或假进度；
- 移动端正常滚动，不设置第二个固定底部层。

## 视觉资产

```text
docs/design/commerce/mockups/case-queue-visual-v1-desktop.png
尺寸：1672 × 941
SHA-256：3971d088d043ff8c49f7c9b51bd5fb98e15192a185c8d17dc2dd95f14cc3d467

docs/design/commerce/mockups/case-queue-visual-v1-mobile.png
尺寸：853 × 1844
SHA-256：52926d7189f711fcbecfcfd619adbdafd41b49cc4333971733833bece9a80010
```

## 代表状态

视觉稿使用四种代表任务状态：

- 履约延迟异常：调查中、高风险；
- 评价体验异常：等待数据、中风险；
- 卖家对标检查：待调查、中风险；
- 履约行动跟踪：跟踪中。

React 不得把这些代表行写死。列表必须读取 `GET /api/commerce/cases`，排序、筛选和分组由纯 View Model 根据真实 Case 字段完成。没有 Case 时显示空态，不从 Capability、聊天文案或计时器伪造案例。

## Image Generation Prompt 摘要

使用 `ui-mockup` 模式，要求：中文生产 UI、同一 Commerce Shell、桌面 260px 导航与移动抽屉、单一顶栏、“需要你处理 / 持续跟踪”分组、真实 Case 生命周期筛选、桌面列表与移动卡片、无 Dashboard/Chat/Agent 活动、无第二个固定底部层。内置 Image Generation 为最终使用路径，没有切换到 CLI 或其他图像模型。

## 实现边界

本页首轮接通：

```text
Case List
→ 状态 / 风险 / 关键字筛选
→ 打开 Case Detail
→ Capability 预选路径
→ Explicit Case 表单
→ POST /datasets/{dataset_id}/cases
→ 创建成功后进入真实 Case Detail
```

首轮不在队列页启动 Agent，不显示运行中动画。创建 Explicit Case 只持久化真实 Case 与触发合同；调查运行需要后续显式启动。

## React 实现与视觉终检

实现截图：

```text
docs/design/commerce/implementation/case-queue-react-desktop-v1.png
1280 × 720
SHA-256：630c76b55fef7a5e6d335f579b1e1cc3d22aaeb0ab1a2bc7f6413316e26fb2eb

docs/design/commerce/implementation/case-queue-react-mobile-v1.png
390 × 844
SHA-256：15e5bf9e274dda8d4a84db528f473cba019be44d4ca8a7502f4369cc91af4b22

docs/design/commerce/implementation/case-queue-react-create-v1.png
1280 × 720
SHA-256：f103982c07036978ba8ba43606884ba6744293d793aeebaa1b675d8038d79045
```

实现相对生成稿更克制：真实测试数据只有两个 Case 时不补假行，也不为 Case List 合同没有提供的窗口或路径编造内容。桌面使用紧凑列表；移动端保持卡片式扫描和独立横向筛选，不产生页面级横向溢出。创建侧栏区分真实加载态与空数据态，统一使用中文或中性数字格式，不依赖浏览器英文日期占位。

# 电商经营诊断 Capability Report 视觉稿 v1

## 状态

- 使用内置 Image Generation 于 2026-07-21 生成桌面与移动高保真候选；
- 视觉系统继承 Master Shell、Case Detail v2 与 Data Inbox 的浅色、克制、文档式工作区；
- React、真实 Chromium 机械交互与桌面/移动截图 QA 已完成。

## 用户任务

用户刚完成数据接入和字段确认，真正想知道的是：

```text
这批数据现在能分析什么？
哪些路径证据完整？
哪些路径只能部分判断？
还缺什么，下一步是否值得创建 Case？
```

Capability Report 只解释数据能力边界，不替用户创建 Case，不调用模型给出经营建议。可用路径进入 Case Queue 后，才开始 Case-first 的异常诊断闭环。

## 关键视觉决定

- 左侧“数据能力”高亮；已有 Case 仍可见，保持 Dataset → Capability → Case 的产品顺序；
- 主内容采用“能力结论 → 可用分析路径 → 数据边界 → 需要补充或确认”的连续文档结构，不做指标 Dashboard；
- 三种能力状态明确分开：绿色“可直接分析”、琥珀“部分可分析”、灰色“当前不可分析”；
- 每条分析路径展示状态、已确认语义和可用操作；不可用路径不出现可点击的创建按钮；
- “未观察”字段保持显式边界：曝光、点击、加购、广告消耗、库存、利润不会被推断为零；
- 语义待确认时只显示具体字段和返回 Data Inbox 的动作，不在本页自动确认；
- 无 Chat Composer、模型名、Agent 活动、Token、Retry、Lease、Runtime 或伪造进度；
- 移动端使用堆叠卡片和可横向阅读的路径行，不设置固定底部层，所有动作在正常滚动流中完成。

## 视觉资产

```text
docs/design/commerce/mockups/capability-report-visual-v1-desktop.png
尺寸：1586 × 992
SHA-256：756931563d5b21bc3a6926cfe0e99a7633c209f3aafeed18a42d619c9dfdcaaa

docs/design/commerce/mockups/capability-report-visual-v1-mobile.png
尺寸：852 × 1846
SHA-256：1ca177c2e0093f157da38b3d27d0aec60343c2771b603ec5776d456d6f2d63e5
```

## 代表数据与状态

视觉稿使用 Olist `GC-FULFILLMENT-001` 代表数据的能力投影：

- 可直接分析：履约诊断；
- 部分可分析：评价体验（只使用评分，缺少评价文本）；
- 当前不可分析：卖家对标（卖家实体数量不足）；
- 已观察：订单、履约、商品、卖家、客户、评价；
- 未观察：曝光、点击、加购、广告消耗、库存、利润；
- 待确认示例：`orders.order_approved_at → 订单审核时间`。

实际 React 必须完全读取后端 Capability Profile，不得把这组代表状态写死；缺少字段、样本不足和依赖不可用都要使用明确原因码投影。

## Prompt 记录

生成 Prompt 要求：中文生产 UI、同一 Commerce Shell、无 Dashboard/Chat/Agent 活动、Capability precedes Case、缺失字段不推断，并分别生成桌面与 390×844 逻辑像素移动版。实现前需完成 Capability API 读合同和路径操作合同的 RED 测试。

## React 实现与视觉终检

实现文件：

```text
frontend/src/core/commerce/capability-report-view-model.ts
frontend/src/components/commerce/capability-report.tsx
frontend/src/components/commerce/master-shell.tsx
```

实现截图：

```text
docs/design/commerce/implementation/capability-report-react-desktop-v1.png
尺寸：1280 × 720
SHA-256：b3f8c3604f6be0d2116f7c4171f496d8ed2f2cb80146e58e0c5dbb79990860a3

docs/design/commerce/implementation/capability-report-react-mobile-v1.png
尺寸：390 × 844
SHA-256：fe31b3fc5af11ba0553a9e44d5c87518f08219905607dfcd412b89e009cddacf
```

视觉终检确认：

- 页面保持“结论 → 路径 → 边界 → 待确认”的文档流，不退化为 Dashboard；
- 正文重复刷新已删除，刷新统一由工作区顶栏负责；
- 左侧只有“数据能力”拥有当前页状态，已有 Case 保留上下文但不再占用页面高亮；
- 390 × 844 下无横向溢出、无 Chat Composer、无第二个固定底部层；
- “创建案例”已接入 Case Queue；可用路径会预选，但仍必须补齐经营主体、基线窗口和当前窗口。

# 电商经营诊断 Action Center 视觉稿 v1

## 状态

- 2026-07-23 使用当前会话内置 Image Generation 生成桌面与移动高保真稿；
- 两张稿件均已保存到项目并人工检查；
- 选中状态基于当前真实内部 Action Catalog 的 `create_metric_monitor`，不是不可执行的外部商家写操作；
- Action Record / Detail / Approval / Execution 严格合同、View Model、React、浏览器交互和截图 QA 已完成；
- Approval modify 的通用参数编辑表单仍保留为行动闭环后续项。

## 用户任务

Action Center 帮助运营人员回答：

```text
现在有哪些行动需要处理？
这条行动为什么值得做，引用了哪些证据和判断？
服务端策略是否允许执行，是否需要人工审批？
系统具体会做什么，怎样验证，出错后怎样回滚？
执行、重放、回滚和跟踪分别处于什么权威状态？
```

它不是建议文案列表，也不从聊天文本推断执行状态。所有状态必须来自 Action、Approval、Run、Artifact、Follow-up 和 Domain Event 合同。

## 关键视觉决定

- Action Center 是顶层工作页，左侧导航直接高亮“行动中心”；
- 桌面使用“行动队列 + 选中行动详情”双栏，避免把详情塞入全局 Inspector；
- 移动端只展示当前行动摘要与“切换行动”入口，详情进入正常纵向文档流，不缩放桌面双栏；
- 页面先展示证据与判断，再展示执行参数、策略权限、回滚方案和操作按钮；
- 当前代表状态为“创建延迟履约率跟踪”：`create_metric_monitor`、中风险、策略 L2、内部可逆、无需审批；
- 不把 Action Planner 的自然语言当作执行权限。风险、策略、审批、工具、阈值和回滚仍由服务端合同决定；
- 操作区处于正常文档流，不使用固定底栏，不与移动导航或 Chat Composer 叠加；
- 没有模型、Token、Retry、Lease 或假 Agent 活动；这些工程信息属于 Agent Run 页面；
- 不声称行动已执行或造成经营改善。

## 视觉资产

```text
docs/design/commerce/mockups/action-center-visual-v1-desktop.png
尺寸：1536 × 1024
SHA-256：25776f03633de4f3e4d8c2f37f73c2570c200d9e22b03a597afb252042427900

docs/design/commerce/mockups/action-center-visual-v1-mobile.png
尺寸：864 × 1821
SHA-256：91c6ec03fc5ff53c296e37da331f0e18d7983c9707d4017dcaf1118662bc842f
```

## 代表状态与数据纪律

视觉稿中的 `4.8%` 是代表状态。React 必须读取服务端 Action Record：

- `Action.status` 决定待执行、等待审批、执行中、跟踪中、失败、回滚中或终态；
- `Action.risk_level`、`ActionPolicyDecision.level/disposition/reason_codes` 决定风险与策略；
- `ApprovalRequest` 决定是否显示批准、拒绝或修改入口；
- `ValidatedActionDraft.parameters` 决定行动类型和参数，不能从标题反推；
- `RollbackPlan` 决定回滚策略、触发条件和验证方式；
- `ActionExecutionArtifact` 与 Action Run 决定执行结果，按钮点击后必须重新读取权威详情；
- `FollowUpRecord` 决定跟踪结果；没有可靠对照时必须显示 `inconclusive`；
- 未观察的曝光、点击、加购、广告消耗、库存和利润不得显示为零。

## Image Generation Prompt 摘要

使用 `ui-mockup` 生成桌面与移动稿。桌面要求 260px Commerce 左栏、紧凑顶栏、行动队列和选中行动文档；移动要求真正响应式的单栏长页面。两张稿件均使用简体中文、浅色克制文档式工作区，代表内容为证据支持但不证明因果的履约指标跟踪、L2 内部可逆策略、无需审批和可验证回滚；明确禁止 Dashboard KPI、Chat、Runtime 遥测、假执行和经营改善声明。使用内置 Image Generation，没有切换 CLI 或其他图像模型。

## React 实现结果

```text
docs/design/commerce/implementation/action-center-react-desktop-v1.png
尺寸：1280 × 720
SHA-256：7d276edcc108337fdde09f0d3a42c36221d5e417b76d2b884e0296502546fca2

docs/design/commerce/implementation/action-center-react-mobile-v1.png
尺寸：390 × 844
SHA-256：97ecc5ff70082253d778232e69ebe72c3c1c0d360ab8ba7d915dfec4e202d740
```

React 读取真实 Action Record，不使用视觉稿数字作为前端常量。视觉终检后修复了后端英文 Case 技术标题泄露和移动状态标签换行。完整实现与验证记录见 `docs/progress/2026-07-23-commerce-action-center-react.md`。

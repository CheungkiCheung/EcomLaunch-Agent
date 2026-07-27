# 电商经营诊断 Evidence Explorer 视觉稿 v1

## 状态

- 使用内置 Image Generation 于 2026-07-22 生成桌面与移动高保真候选；
- 移动候选人工检查时发现第三条矛盾证据的置信度被错误绘制为 `35%`，随后只编辑该数字为 `93%`；
- 桌面稿与修正后的移动稿已选中；
- 证据 View Model、对象引用、React、桌面/移动浏览器交互和截图 QA 已完成；
- Case Composer 已收窄为只在概览页显示，证据页没有固定输入层遮挡。

## 用户任务

Evidence Explorer 不是把 Evidence ID 排成表格，而是帮助用户回答：

```text
当前结论由哪些证据支持？
有没有矛盾证据被隐藏？
每条证据引用了哪些事实或指标？
哪些内容已观察，哪些仍是未知或数据边界？
这条证据能证明什么，又不能证明什么？
```

## 关键视觉决定

- Evidence Explorer 位于 Case Detail 的“证据”页签，不增加顶层导航；
- 保留紧凑 Case Header 和同一组页签，让用户知道证据属于哪个 Case；
- 桌面使用“证据列表 + 选中对象详情”的最小双栏；右栏不是默认打开的全局 Inspector；
- 移动端不压缩桌面双栏，而是在选中证据卡内展开详情，正常文档流滚动；
- 支持、矛盾、未知三类关系同级可筛选，矛盾证据不能折叠到不可见区域；
- 每条证据明确区分关系、类型、语义状态、置信度和引用对象数量；
- 详情按“证据说明 → 引用对象 → 支持的判断 → 证据边界”组织；
- 当前后端合同只暴露 Evidence、Fact ID、MetricObservation ID、Hypothesis 和 Case Analysis；React 不得伪造尚未开放的原始 Fact 内容；
- 无 Chat Composer、模型、Token、Retry、Lease 或假 Agent 活动。

## 视觉资产

```text
docs/design/commerce/mockups/evidence-explorer-visual-v1-desktop.png
尺寸：1672 × 941
SHA-256：b88448f8684ad2dd648ad9ba32caf40e5cd235a92e3ff5a7a5cab959e09129a3

docs/design/commerce/mockups/evidence-explorer-visual-v1-mobile.png
尺寸：853 × 1844
SHA-256：d50537349656637b0e1e83c3719bc0f6247faeae41c9bc177b06ffe0483434ea
状态：保留为生成原稿，第三条置信度文字有误，不作为实现基准。

docs/design/commerce/mockups/evidence-explorer-visual-v1-mobile-corrected.png
尺寸：853 × 1844
SHA-256：68f51071110933de6d60a6a43e2f4499d1dbe3d4dbf76cb223852b09057c4b91
状态：选中的移动实现基准。
```

## 代表状态与实现纪律

视觉稿用 `3.5% → 35.1%` 代表一条支持证据，并显示一条矛盾证据和一条未知数据边界。React 必须读取真实 Case Detail：

- `Evidence.relation` 决定支持、矛盾或未知；
- `semantic_status` 决定已观察、推导、假设、未知或阻塞；
- `confidence` 原样格式化，不使用视觉稿中的示例数字；
- `fact_ids` 与 `metric_observation_ids` 决定证据类型与引用数量；
- Metric 引用可以从 Case Analysis 中恢复名称、值、单位和窗口；
- Fact 详情尚未开放时只显示可审计 ID 和“原始事实详情尚未开放”，不能编造文本；
- Hypothesis 关系从 `supporting_evidence_ids / contradicting_evidence_ids` 反向投影；
- 没有 Evidence 时显示空态，不从消息或 Event 文案生成证据。

## Image Generation Prompt 摘要

使用 `ui-mockup` 生成桌面与移动候选，要求 Case-bound 证据浏览、支持/矛盾/未知同级、Evidence/Fact/Metric/Hypothesis 分层、桌面最小双栏、移动内联展开、无 Dashboard/Chat/Runtime。移动稿随后使用 `precise-object-edit`，只将错误的 `35%` 修正为 `93%`，其他视觉保持不变。全部使用内置 Image Generation，没有切换 CLI 或其他图像模型。

## React 实现结果

```text
docs/design/commerce/implementation/evidence-explorer-react-desktop-v1.png
尺寸：1280 × 720
SHA-256：79a59d4e920fecffddeccd8c6ef05e194e6560837fc72edab756a4eb00968658

docs/design/commerce/implementation/evidence-explorer-react-mobile-v1.png
尺寸：390 × 844
SHA-256：3a3576e088f277805a4fe99447f31fe7f550a307317ef3c6869ab997244470d8
```

实现读取结构化 Mock API 中的 `4.8% → 36.4%` 代表数据，因此与视觉稿的示例数字不同；这属于有意的数据合同差异，不是视觉偏差。完整实现与验证记录见 `docs/progress/2026-07-22-commerce-evidence-explorer-react.md`。

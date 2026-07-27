# 电商经营诊断 Data Inbox 视觉稿 v1

## 状态

- 使用内置 Image Generation 于 2026-07-20 生成；
- 视觉系统继承已实现并通过真实浏览器 QA 的 Case Detail v2；
- 当前视觉候选已用于 React 实现，并通过中文 Chromium 机械交互和截图检查；
- 后续视觉调整仍以本稿和实现截图的差异评审为准。

## 用户任务

真实用户不是为了“上传文件”本身而来，而是已经感觉到经营异常，希望系统判断：

```text
我手头有哪些数据？
→ 系统是否安全、完整地接收？
→ 哪些表和字段可以稳定识别？
→ 哪些语义需要我确认？
→ 当前能分析什么、不能分析什么？
```

Data Inbox 只负责 `Intake → Profile → Semantic Confirmation`，不在本页创建 Case、启动 Agent 或给经营建议。下一页 Capability Report 才解释完整可分析边界。

## 状态矩阵

### 空态

- 用户拖入文件、文件夹或 ZIP；
- 明确支持 CSV、XLSX、JSON、ZIP；
- 显示只读存储、文件 Hash 和来源记录；
- 未上传时不播放扫描动画，不显示假历史批次；
- “继续检查数据能力”禁用。

### 已接收、需确认

- 展示真实文件名、识别角色、行数和状态；
- 展示确定性完整性、表结构、Join 与字段语义检查；
- 歧义字段进入单个可理解的人审问题；
- 明确“未观察”字段，而不是把缺失解释成零；
- 确认后进入 Capability Report。

### 后续实现必须覆盖但本轮未单独生成的状态

- 文件格式、大小或重复冲突；
- 部分文件成功、部分失败；
- 没有可连接表；
- 多个字段语义待确认；
- 幂等重放同一批次；
- 删除待上传文件，但不删除已经入库的不可变来源；
- 上传中断和恢复。

## 关键视觉决定

- 保留 Case-first 全局 Shell，但本页没有 Chat Composer；
- 左侧“数据接入”高亮，已有 Case 仍可见，强调 Dataset 与 Case 属于同一工作区；
- 桌面使用连续文档和紧凑列表，不做 Dashboard；
- 上传区克制，不使用彩色云朵或营销插画；
- 绿色只表示已验证检查，琥珀色只表示人审确认；
- 文件名和字段名允许保留原始拉丁字符，其余面向用户内容使用中文；
- 缺失的曝光、点击、加购、广告消耗、库存、利润显示为“未观察”；
- 页面不展示模型、Agent、Retry、Lease、Token 或伪造进度。

## 视觉资产

### 桌面空态

- 图片：`docs/design/commerce/mockups/data-inbox-visual-v1-empty.png`
- 尺寸：1586 × 992 PNG
- SHA-256：`992225a26cb91da2f0abddf79583737c2d4f06169824de4c2c48800008108a56`

### 桌面已接收、需确认

- 图片：`docs/design/commerce/mockups/data-inbox-visual-v1-review.png`
- 尺寸：1586 × 992 PNG
- SHA-256：`6d4d5e6ab80e7b38e08a967daab9d6cdd8646d3ed20679e970a0ebcab36f2646`

### 移动已接收、需确认

- 图片：`docs/design/commerce/mockups/data-inbox-visual-v1-mobile-review.png`
- 尺寸：852 × 1846 PNG，用于表达约 390 × 844 逻辑像素布局
- SHA-256：`220ec6899a2769e0217ef6f8dd91275d30acc61097b972ca1e3a3c7141c8d603`

## 代表数据

视觉稿使用冻结的 `GC-FULFILLMENT-001` Olist 切片：

```text
orders.csv：554 行
order_items.csv：563 行
order_reviews.csv：549 行
products.csv：47 行
customers.csv：554 行
sellers.csv：1 行
合计：2,268 行
```

当前可识别：订单、履约、商品、卖家、客户、评价。

当前未观察：曝光、点击、加购、广告消耗、库存、利润。

映射问题 `orders.order_approved_at → 订单审核时间` 用于表达 Semantic Confirmation，不代表生产系统只能处理这一种歧义。

## Prompt 1：桌面空态

```text
Use case: ui-mockup
Asset type: high-fidelity Chinese desktop web application page, Commerce Data Inbox empty/default state
Input images: Image 1 is the visible implemented Commerce Case Detail screenshot. Use it only as the strict visual-system reference: preserve the same original light warm-gray shell, 260px sidebar, 56px top bar, thin-line icon language, typography scale, white main canvas, subtle 1px borders, restrained radii and Codex-inspired document hierarchy. Do not copy Codex branding or assets.

Primary request: Generate a new original page for the same product “电商经营诊断”, page “数据接入”. This is the real first-use entry where an ecommerce operator uploads heterogeneous business data before any Case exists. The screen must clearly explain that the system first checks structure, semantics and data capability, then decides what can actually be analyzed. It is not a marketing landing page, not a dashboard and not a chat screen.

Language invariant: every visible label, heading, sentence, button, status and helper text must be Simplified Chinese. File-format abbreviations such as CSV、XLSX、JSON are allowed. No English UI copy, no Agent/model/provider names, no Retry, Lease, Token, raw IDs, fake activity or unsupported business claims.

Canvas and composition: wide 16:10 desktop product screenshot, approximately 1440×900; preserve the 260px pale warm-gray left sidebar and compact top bar from Image 1; white main workspace; no right inspector; no bottom chat composer; centered document column about 820–900px wide.

Left sidebar: product title “电商经营诊断”; entries “新建诊断”, “数据接入”, “案例队列”, “行动中心”; highlight “数据接入”; entry “更多”; section “当前案例” with “履约延迟异常 / 待调查 · 紧急”; bottom “设置”.

Top bar: breadcrumb “数据接入 / 新数据批次”; refresh, overflow and outlined button “导入说明”.

Center header: eyebrow “数据接入”; heading “接入经营数据”; subtitle “上传文件后，系统会先检查结构、字段语义和数据能力，再决定能够分析什么。”; helper “原始文件只读保存，指标与异常由确定性数据层计算。”

Section “添加数据”: dashed upload zone; “拖入文件或文件夹”; “支持 CSV、XLSX、JSON 和 ZIP；单批次最多 20 个文件”; button “选择文件”; notes “只读存储 · 计算文件哈希 · 保留来源记录”.

Section “系统会检查”: compact rows “文件完整性 / 检查格式、大小和重复文件”, “表结构 / 识别订单、商品、卖家、评价等数据表”, “字段语义 / 自动映射，歧义字段需要人工确认”, “数据能力 / 明确能分析、部分可分析和无法判断的范围”.

Section “最近的数据批次”: honest empty row “还没有导入记录”; “完成首次上传后，可在这里查看处理状态和来源。”

Lower-right disabled action “继续检查数据能力”; helper “添加数据后可继续”.

Style: shippable original Chinese productivity UI; calm light Codex-inspired hierarchy; warm white and very light gray; charcoal text; fine dividers; nearly no shadows.

Invariants: Dataset and Capability precede Case; missing fields are not inferred; deterministic checks precede model reasoning; no fake Agent activity; no Chat because there is no active Case.

Avoid: colorful upload illustration, dashboards, charts, agent avatars, fake progress, visible inspector, chat composer, English text, raw IDs, model names, unsupported GMV/CTR/ROI/ad spend/inventory/profit claims, logos, trademarks, watermark, copied branding, gradients, dark UI or glassmorphism.
```

## Prompt 2：桌面已接收、需确认

```text
Use case: ui-mockup edit
Asset type: high-fidelity Chinese desktop web application page, Commerce Data Inbox post-upload review state
Input images: Image 1 is the immediately preceding “数据接入” empty/default page and is the edit target. Preserve its shell, sidebar, top bar, typography, colors, spacing, column width and overall product identity with high fidelity. Change only the main document content needed to show a completed upload that requires one semantic confirmation.

Primary request: Create the paired real workflow state after the operator uploads the frozen Olist-style ecommerce data bundle. The page must show safe intake, deterministic profiling and one bounded mapping question. It must not jump ahead to a Case, Agent investigation or business recommendation.

Keep the shell and “数据接入” highlight. Breadcrumb “数据接入 / 订单履约数据”. Heading “订单履约数据”. Subtitle “已接收 6 个文件，正在确认数据语义和可分析范围。” Metadata “共 2,268 行 · 6 个文件 · 完整性检查通过”. Status “已安全接收”.

Section “本次数据批次”: six compact rows: orders.csv / 订单 / 554 行; order_items.csv / 订单明细 / 563 行; order_reviews.csv / 评价 / 549 行; products.csv / 商品 / 47 行; customers.csv / 客户 / 554 行; sellers.csv / 卖家 / 1 行; all status “已识别”; text action “查看来源记录”.

Section “自动检查”: “文件完整性 / 通过”, “表结构 / 6 张表”, “关联关系 / 5 组可连接”, “字段语义 / 1 项需确认”.

Section “需要你确认”: amber review block; title “确认订单审核时间字段”; description “字段 order_approved_at 可能表示订单审核时间。确认后，系统才能稳定计算处理时长。”; mapping “orders.order_approved_at → 订单审核时间”; actions “暂不确认” and “确认字段含义”; helper “确认只影响当前工作区的数据语义，不会修改原始文件。”

Section “当前可识别范围”: “已识别：订单、履约、商品、卖家、客户、评价”; “未观察：曝光、点击、加购、广告消耗、库存、利润”; note “未观察字段不会被推断为零，也不会生成对应经营结论。”

Bottom actions “返回添加文件” and “继续检查数据能力”. No fixed bottom bar.

Use Simplified Chinese except filenames/field names. Green only for verified checks, amber only for confirmation. No Agent/model activity, Case creation, business recommendation, dashboard, chart, inspector, composer, fake percentage, dark UI, gradients, logos or watermark.
```

## Prompt 3：移动已接收、需确认

```text
Use case: ui-mockup
Asset type: high-fidelity Chinese mobile web application screen, Commerce Data Inbox post-upload review state
Input images: Image 1 is the immediately preceding desktop “订单履约数据” post-upload page. Use it as the strict content, visual-system and interaction reference. Generate a true responsive mobile layout, not a crop.

Primary request: Design the 390×844 logical-pixel mobile page for “电商经营诊断”, route “数据接入 / 订单履约数据”. Six Olist-style files are uploaded and one semantic field needs confirmation before Capability evaluation.

Top bar: hamburger, “数据接入”, refresh and overflow. No visible sidebar, inspector, chat composer or fixed bottom layer.

Header: eyebrow “数据接入”; heading “订单履约数据”; status “已安全接收”; subtitle “已接收 6 个文件，正在确认数据语义和可分析范围。”; metadata “2,268 行 · 6 个文件 · 完整性检查通过”.

Section “本次数据批次”: show three rows orders.csv / 订单 · 554 行; order_items.csv / 订单明细 · 563 行; order_reviews.csv / 评价 · 549 行; all “已识别”; row “查看全部 6 个文件”.

Section “自动检查”: “文件完整性 · 通过”, “表结构 · 6 张表”, “关联关系 · 5 组可连接”, “字段语义 · 1 项需确认”.

Section “需要你确认”: amber block; title “确认订单审核时间字段”; description “order_approved_at 可能表示订单审核时间。确认后，系统才能稳定计算处理时长。”; source chip “orders.order_approved_at”; full-width select “订单审核时间”; helper “不会修改原始文件”; actions “暂不确认” and “确认字段含义”.

Section “当前可识别范围”: “已识别：订单、履约、商品、卖家、客户、评价”; “未观察：曝光、点击、加购、广告消耗、库存、利润”; note “未观察字段不会被推断为零。”

Normal scrolling actions “继续检查数据能力” and “返回添加文件”. No fixed toolbar.

Style: original shippable Chinese productivity UI; light Codex-inspired hierarchy; touch targets at least 44px; no horizontal overflow; green for verified, amber for confirmation; no fake Agent progress, dashboard, charts, illustrations, English headings, raw IDs, dark UI, gradients, logos, watermark or copied assets.
```

## React 实现与验证记录

```text
RED：Data Inbox 空态、文件选择、上传、语义确认与无横向溢出
→ GREEN：接通 Dataset List / Detail、Intake、Mapping Resume API
→ REFACTOR：Dataset Header、File List、Check Summary、Semantic Confirmation Primitives
→ VERIFY：33 files / 245 Vitest、TypeScript、scoped ESLint、5 个 Chromium 机械场景、桌面截图 QA
```

实现文件与进度记录：

```text
frontend/src/components/commerce/data-inbox.tsx
docs/progress/2026-07-21-commerce-data-inbox-contract-and-react.md
```

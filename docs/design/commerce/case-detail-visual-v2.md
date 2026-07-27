# 电商经营诊断 Case Detail 视觉稿 v2

## 状态

- 使用内置 Image Generation 于 2026-07-20 生成。
- 基于已经实现的中文浅色 Master Shell、Case Detail v1 和 `information-density-guidelines-v1.md`。
- 用户已确认该视觉方向，React v2 与真实数据浏览器验收已完成。
- v1 作为历史密集版本保留，不再进入实现。

## 视觉资产

### 桌面默认运营视图

- 图片：`docs/design/commerce/mockups/case-detail-visual-v2-default.png`
- 尺寸：1586 × 992 PNG
- SHA-256：`d08e5df40beafc01f29abfd24a31cd15d1261444925c9b05986846f57ede993b`

### 桌面证据检查面板状态

- 图片：`docs/design/commerce/mockups/case-detail-visual-v2-evidence-inspector.png`
- 尺寸：1586 × 992 PNG
- SHA-256：`dbfda33690d7a4d6c3bfefc51e8b0f538950b70a6c0e05e7edd7f61ebae60e91`

### 移动默认运营视图

- 图片：`docs/design/commerce/mockups/case-detail-visual-v2-mobile-default.png`
- 尺寸：852 × 1846 PNG，用于表达约 390 × 844 逻辑像素的移动布局。
- SHA-256：`2ed532f90c56c24599e0a2db3f8224ac10c5fa8650a335a64e96a2365bf76923`

## React 实现资产

### 桌面默认运营视图

- 图片：`docs/design/commerce/implementation/case-detail-react-desktop-v1.png`
- SHA-256：`85b8f16f327c57c169ea6bfb37c516770c4e1ac366f08d4f0331ef1563954f0c`

### 桌面证据检查面板状态

- 图片：`docs/design/commerce/implementation/case-detail-react-evidence-inspector-v1.png`
- SHA-256：`79a50cbb21ca230c26667b52cee860db1bb90b07c59fc895a0c04ea034d126c5`

### 移动默认运营视图

- 图片：`docs/design/commerce/implementation/case-detail-react-mobile-v1.png`
- SHA-256：`0dadc43d87eafa08c161c4dc1162285bcfe9addc8e44b049d852867dd2c7d0ca`

实现使用结构化 Mock API 固定视觉状态，因此截图保持视觉稿中的 `4.8% → 36.4%`。额外的真实 Gateway + Olist 浏览器验收读取到 `3.5% → 35.1%`、5 个异常信号和 5 条 Evidence，证明页面没有把视觉代表值硬编码为业务真相。

## v2 解决的问题

Case Detail v1 同时展示了案例属性、调查路径、完整概览、运行详情、右侧检查面板和两层底部 Dock。单个模块合理，但默认同时可见会让经营任务和 Agent 工程信息互相争夺注意力。

v2 不删除能力，而是把默认页收敛为四个问题：

```text
发生了什么
→ 当前判断
→ 证据边界
→ 下一步
```

并通过三个视觉状态验证渐进披露：

1. 默认桌面不显示右侧检查面板；
2. 用户选择证据后才显示对象级证据详情；
3. 移动默认态只保留一个固定底部输入层。

## 默认运营视图决定

### 左侧导航

- 默认只显示“新建诊断”“数据接入”“案例队列”“行动中心”；
- 原五个工作区入口收进“更多”；
- 保留当前案例和设置；
- 桌面提供侧栏折叠入口；
- 未实现页面不再以大量禁用项占据默认导航。

### 顶部与案例头部

- 顶部使用短面包屑“履约延迟异常 / 案例详情”；
- 检查面板使用显式入口，但默认关闭；
- 案例头部只保留“高风险”“调查中”两个状态；
- 分析路径和工程运行状态进入“运行”页签或对象级详情；
- 元数据只显示周期、更新时间和证据数量。

### 中心概览

- “发生了什么”只显示一个周期对比，不显示趋势图或 KPI 卡片组；
- “当前判断”明确相关性与因果限制；
- “证据边界”只显示核验数量、支持数量和未知项，不展开完整 Evidence Explorer；
- “下一步”只显示一个候选行动及“尚未执行”状态；
- 调查记录、证据和运行分别进入页签，不在概览重复展开。

### 检查面板

- 桌面和移动默认关闭；
- 点击“查看证据”后，右侧只展示当前选中证据的属性、数值、来源、计算口径和血缘；
- 不在证据面板同时展示输出、子智能体和运行遥测；
- 点击其他对象时，面板内容必须切换到对应 Action、Data Source、Run Node 或 Unknown，而不是叠加多个通用区域。

### 底部输入

- 删除永久 Runtime Strip；
- 空闲 Composer 为单行紧凑状态；
- 聚焦、添加文件或出现错误时允许扩展；
- 模型、Retry、Lease、Token 和 Run ID 进入“运行”或工程详情；
- 移动端只有 Composer 一个固定底部层。

## 移动布局决定

- 左侧导航和检查面板都变为 Drawer；
- 顶部不显示长面包屑；
- 两个状态标签保持单行；
- 四个页签保持可读，必要时允许横向滚动；
- 主内容单列；
- 输入框空闲高度目标为 56–64px；
- 不在输入框上方固定 Runtime；
- 滚动安全区必须保证“查看行动”、错误或审批入口不会被 Composer 遮挡。

## 代表数据状态

- 当前案例：卖家 4869 履约延迟异常；
- 严重程度：高风险；
- 案例状态：调查中；
- 上一周期延迟履约率：4.8%；
- 当前周期延迟履约率：36.4%；
- 变化：+31.6 个百分点；
- 当前判断：承运表现可能相关，但不能确认因果；
- 证据：4 条已核验，其中 2 条支持；
- 未知项：2 项；
- 候选行动：审查承运商服务等级与超时订单分布；
- Action 状态：尚未执行。

这些数值只用于视觉代表状态。React 必须读取真实 Case、Metric、Evidence、Hypothesis、Unknown、Action 和 Domain Event Projection，不得把图片文本硬编码为通用业务真相。

## React 交互合同候选

视觉确认后，至少需要覆盖：

1. 桌面和移动默认不渲染可见 Inspector；
2. 点击“查看证据”打开选中 Evidence 的 Inspector / Drawer；
3. 关闭 Inspector 后中心恢复默认宽度；
4. 切换 Evidence 时右侧内容同步更新；
5. 没有 Evidence 时展示明确空状态，不打开空白面板；
6. Composer 空闲单行、聚焦扩展；
7. 移动端没有 Runtime Strip，Composer 不遮挡行动入口；
8. “运行”页签可以进入工程详情，但概览不泄露模型、Retry、Lease 和原始事件；
9. 结论始终保留因果限制；
10. Action 未执行时不得显示已批准、已生效或指标改善。

## 生成 Prompt 1：桌面默认运营视图

```text
Use case: ui-mockup
Asset type: high-fidelity Chinese desktop web application page, Commerce Case Detail default operator view
Input image: the previously displayed “Case Detail v1” image is the visual-system reference and redesign target. Preserve its original light warm-gray shell, thin-line icon language, typography family, subtle borders, white center canvas, and Case-first product identity, but redesign the information hierarchy substantially. Do not copy Codex branding or assets.

Primary request: Generate a new original “案例详情 v2 — 默认运营视图” for a Chinese ecommerce operations Agent product named “电商经营诊断”. The page must feel calmer and materially less crowded than v1. It should demonstrate progressive disclosure: the desktop right inspector is closed by default, engineering runtime telemetry is not visible, the composer is one compact idle row, and the center document answers only four questions: what happened, current judgment, evidence boundary, and next action.

Language invariant: Every user-facing label, heading, status, description, button, breadcrumb and placeholder must be Simplified Chinese. No English UI copy. Do not show raw event codes, Case IDs, Run IDs, model IDs, provider names, Retry, Lease, Agent technical terms, or malformed filler text.

Canvas and composition:
- wide 16:10 desktop product screenshot, approximately 1440×900
- 250–260px pale warm-gray left sidebar
- white main workspace with compact 56px top bar
- no visible right panel in the default state; preserve generous white space on the right side of the centered document column
- centered document column approximately 760–820px wide with comfortable line length
- one compact fixed composer near the bottom, approximately 64–76px high when idle
- no runtime strip above the composer
- realistic implementable Next.js application, not concept art

Left sidebar:
Product title “电商经营诊断”.
Only four primary entries: “新建诊断”, “数据接入”, “案例队列”, “行动中心”. Highlight “案例队列”.
Section label “当前案例”.
Selected case “履约延迟异常” with secondary text “调查中 · 高风险”.
Near the bottom include a collapsed entry “更多” and final entry “设置”.
Do not show the previous five expanded workspace tools. Include a small original sidebar-collapse icon near the product title.

Top bar:
Breadcrumb “履约延迟异常 / 案例详情”.
Right controls: refresh icon, overflow icon, and one outlined control labeled “检查面板”. The panel is closed; no right-side card is visible.

Center header:
Small eyebrow “案例详情”.
Main heading “履约延迟异常”.
Subtitle “卖家 4869 当前周期的延迟履约率显著上升”.
Only two status pills: “高风险” and “调查中”.
One muted metadata line: “5月8日—5月14日 · 更新于 10:32 · 4 条证据”.
Tabs: “概览”, “调查记录”, “证据”, “运行”. Highlight “概览”.

Main content must be a continuous document with typography and thin dividers, not a dashboard and not a stack of large cards.

Section 1 exact heading “发生了什么”.
One short sentence: “当前周期延迟履约率从 4.8% 上升至 36.4%。”
Below it, one restrained inline comparison row, not a chart:
“上一周期 4.8%” → “当前周期 36.4%” and a muted red annotation “+31.6 个百分点”.

Section 2 exact heading “当前判断”.
One subtle conclusion block with a small green verified icon and exact text:
“延迟履约率上升与平均履约时长增加同时出现，承运表现可能相关，但现有证据不足以确认因果关系。”
Small secondary text “独立验证通过，保留因果限制”.

Section 3 exact heading “证据边界”.
Use one compact document row, not multiple cards.
Primary text “4 条证据已核验，支持异常确实存在”.
Secondary text “仍缺少承运商服务等级变更记录和可靠对照组”.
A restrained text button “查看证据”.
Optionally show two tiny inline summaries “2 条支持” and “2 项未知”, but do not create a KPI tile row.

Section 4 exact heading “下一步”.
One compact action row with title “审查当前承运商服务等级与超时订单分布”.
Secondary status “尚未执行”.
One primary outlined button “查看行动”.
Do not claim approval, execution, improvement, or causal effect.

Bottom composer:
One compact rounded white input bar with subtle shadow, no separate runtime strip.
Placeholder exactly “继续询问当前案例，或添加新的数据……”.
Left: attachment icon and one small context chip “当前案例”.
Right: dark circular send button.
Do not show “目标循环”, model name, Retry, Lease, token usage, or extra mode selectors in this default view.

Style/medium: shippable original Chinese productivity UI. Calm Codex-inspired document hierarchy but not a copy. Warm white and very light gray surfaces, charcoal text, muted secondary text, fine 1px dividers, 10–14px radii, nearly no shadows except composer. Muted red only for risk and metric increase, green only for verified conclusion. Use whitespace and typography for hierarchy. The first screen should feel focused rather than empty and should be visibly less dense than the v1 reference.

Product invariants:
- Case is the authoritative object.
- Chat is only a secondary Case-bound input.
- Correlation is not presented as causation.
- Unknown data is stated honestly.
- Candidate action has not executed.
- Engineering details remain accessible through “运行” and “检查面板” but are not visible by default.

Avoid: visible right inspector, expanded workspace navigation, runtime telemetry, subagent list, evidence-source list, agent avatars, fake activity, dark sidebar, KPI dashboard tiles, charts, marketing graphics, glassmorphism, gradients, neon, copied icons, logos, trademarks, Apple traffic lights, watermark, English copy, raw technical identifiers, GMV, CTR, ROI, ad spend, inventory, profit, or unsupported claims.
```

## 生成 Prompt 2：桌面证据检查面板状态

```text
Use case: ui-mockup edit
Asset type: high-fidelity Chinese desktop web application page, Case Detail contextual inspector state
Input image: the immediately preceding “案例详情 v2 — 默认运营视图” image is the edit target. Preserve it with high fidelity.

Primary request: Create the paired progressive-disclosure state for the same page after the user clicks “查看证据”. Change only what is necessary to open a contextual evidence inspector on the right. Keep the left sidebar, top bar, center Case header, tabs, four document sections, typography, colors, spacing, all metric values, and compact bottom composer visually consistent with the input image. Do not redesign the whole page.

Language invariant: All user-facing text must remain Simplified Chinese. No English UI labels, raw IDs, model names, Agent terms, Retry, Lease, or technical event codes.

Interaction state changes:
- The center “证据边界” row becomes subtly selected with a very light gray background or thin active outline.
- The top-right “检查面板” control appears active but remains restrained.
- A 300–320px floating right inspector opens below the top bar, with 16px rounded corners, thin border, soft shadow, and clear empty margin around it.
- The center document column may reflow slightly narrower but must remain readable and uncluttered.
- Do not add any runtime strip, subagent list, dashboard, or extra navigation.

Right inspector exact content:
Header “证据详情” with a close icon.
Selected evidence title “延迟履约率变化”.
Small status “已核验”.

Section “证据属性” with compact label-value rows:
“类型” — “指标证据”
“关系” — “支持”
“分析周期” — “5月8日—5月14日”

Section “数值” with rows:
“上一周期” — “4.8%”
“当前周期” — “36.4%”
“变化” — “+31.6 个百分点”

Section “来源与口径” with rows:
“数据来源” — “订单履约数据”
“计算口径” — “延迟订单数 / 已履约订单数”
“数据血缘” — “完整”

At the bottom, one restrained full-width button “查看数据血缘”.
No raw table names, no file paths, no machine identifiers.

Bottom composer: preserve the same compact one-row idle composer from the input image. It must not grow taller and must not acquire a runtime strip or additional controls.

Style/invariants: This is the same original Chinese Commerce Case Agent product and the same screenshot state, only with one evidence object selected. Preserve the warm white shell, fine dividers, charcoal typography, muted red/green accents, thin original icons and generous whitespace. The inspector is contextual, not a permanent generic dashboard.

Avoid: changing the four main sections, changing numbers or conclusions, adding Agent activity, adding output/subagent/source summary panels, expanding the sidebar, adding engineering telemetry, copying Codex assets, malformed Chinese, English copy, logos, trademarks, watermark, dark UI, gradients, glassmorphism, KPI tiles, charts, or unsupported business claims.
```

## 生成 Prompt 3：移动默认运营视图

```text
Use case: ui-mockup
Asset type: high-fidelity Chinese mobile web application screen, Commerce Case Detail default operator view
Input images: the two immediately preceding “案例详情 v2” desktop images are strict visual-system and information-hierarchy references. Generate a new responsive mobile default state, not a crop. Preserve the same original product language, data, conclusion, and progressive-disclosure rules.

Primary request: Design the mobile default operator view for the Chinese ecommerce operations Agent product “电商经营诊断”, page “履约延迟异常”. The mobile screen must be substantially calmer than the earlier crowded mobile Master Shell: one center column, no visible sidebar, no visible evidence inspector, no runtime strip, and only one compact fixed bottom composer.

Language invariant: all visible text must be Simplified Chinese. No English labels, Agent terms, model names, Retry, Lease, raw IDs, event codes, or filler.

Canvas and composition:
- portrait mobile app screenshot, approximately 390×844 logical pixels
- white main canvas, light warm-gray controls, fine dividers
- compact top bar about 52–56px
- vertically scrolling document
- one compact fixed composer about 56–64px high
- no second fixed layer above the composer
- no horizontal overflow

Top bar:
Left hamburger icon.
Centered or left-aligned short title “履约延迟异常”.
Right refresh icon and inspector icon.
No breadcrumb text on mobile.

Case header:
Small label “案例详情”.
Heading “履约延迟异常”.
Subtitle “卖家 4869 当前周期的延迟履约率显著上升”.
Only two pills “高风险” and “调查中”.
One compact metadata line “5月8日—5月14日 · 4 条证据”.

Tabs in one horizontal row:
“概览”, “调查记录”, “证据”, “运行”. Highlight “概览”.
Tabs may scroll horizontally if necessary but the screenshot itself must have no clipped text.

Document content, compact but readable:
Section heading “发生了什么”.
Sentence “延迟履约率从 4.8% 上升至 36.4%。”
A compact comparison row with “4.8% → 36.4%” and muted red “+31.6 个百分点”.

Section heading “当前判断”.
A subtle verified block with green check icon and text:
“承运表现可能相关，但现有证据不足以确认因果关系。”
Secondary text “独立验证通过，保留因果限制”.

Section heading “证据边界”.
One compact row:
“4 条证据已核验”
Secondary text “仍有 2 项未知”.
Text action “查看证据”.

Section heading “下一步”.
One compact row title “审查承运商服务等级与超时订单分布”.
Status “尚未执行”.
Text action “查看行动”.
The bottom content may continue behind the scroll area, but the fixed composer must not obscure the active action.

Bottom composer:
One single compact rounded input bar fixed above the safe area.
Attachment icon on the left.
Placeholder “继续询问当前案例……”.
Dark circular send button on the right.
No “当前案例” chip if it makes the bar crowded; no runtime status; no goal mode; no additional toolbar row.

Style/medium: realistic implementable responsive Next.js product UI, original Chinese productivity application. Calm light Codex-inspired hierarchy without copying assets. Charcoal text, muted gray secondary text, muted red for risk/increase, green only for verified status, fine 1px dividers, restrained 10–14px radii, generous readable line height. Use spacing rather than cards. Ensure touch targets are plausible while preserving whitespace.

Product invariants:
- Case is the primary object.
- Default view answers what happened, current judgment, evidence boundary and next action.
- Chat is secondary and Case-bound.
- Correlation is not causation.
- Unknown data is honest.
- Inspector and engineering runtime are accessible by icons/tabs but closed by default.

Avoid: visible sidebar drawer, visible right inspector, runtime strip, multiple fixed bottom layers, two-row composer, subagent list, evidence source list, engineering telemetry, charts, KPI tiles, dense dashboard, dark UI, gradients, glassmorphism, copied Codex icons or branding, Apple traffic lights, logos, trademarks, watermark, English copy, malformed Chinese, raw identifiers, unsupported improvement claims.
```

## 已执行的实施顺序

```text
RED：Case Detail View Model、默认关闭 Inspector、Evidence 选择、移动布局与因果边界测试
→ GREEN：在现有 Commerce Shell 中实现 v2 默认概览和对象级 Inspector
→ REFACTOR：共享 Case Header、Tabs、Compact Composer、Inspector Primitives
→ VERIFY：unit、type、scoped lint、Chromium desktop + mobile 交互与截图 QA
```

该门禁已完成。实现和验证记录见：

```text
docs/progress/2026-07-20-commerce-case-detail-react-v2.md
```

# 电商经营诊断 Case Detail 视觉稿 v1

## 状态

- 使用内置 `imagegen` 工具于 2026-07-20 生成。
- 基于已经实现并通过浏览器 QA 的中文 Master Shell React v1。
- 当前为 Case Detail 第一版历史候选；2026-07-20 信息密度评审后不再进入 React。
- v1 同时暴露案例属性、调查路径、完整概览、运行详情和 Composer，默认层级偏多；后续由遵循渐进披露规则的 v2 取代。
- 用户确认 v2 前不开始 Case Detail React。
- 图片：`docs/design/commerce/mockups/case-detail-visual-v1.png`。
- 尺寸：1586 × 992 PNG。
- SHA-256：`39f891ec6809a374a237c0b7c303c992bc3600b30383383a615814728cb205f7`。

## 页面任务

用户从案例队列或当前案例进入一个经营异常后，需要在同一页回答：

1. 这个案例具体在诊断什么问题；
2. 相比上一周期发生了什么变化；
3. 当前结论是什么，证据边界在哪里；
4. 哪些 Evidence 支持或反驳 Hypothesis；
5. 还有哪些未知项；
6. 是否已有候选 Action，以及是否已经执行。

Case Detail 不承担 Evidence Explorer、Action Center 或 Agent Run 的完整功能。它只给出 Case 级权威摘要和跨页面入口，避免把所有产品能力塞进一个页面。

## 与 Master Shell 的关系

必须保持已经实现的 Shell：

- 左侧中文导航与当前案例；
- 中间白色文档式工作区；
- 顶部紧凑标题栏；
- 右侧顶部留白的悬浮圆角面板；
- 底部运行详情和 Case-bound Composer；
- 中文优先、少卡片、薄边框、低饱和状态色。

Case Detail 只替换中心内容和右侧面板的业务任务，不改变全局框架。

## 代表状态

- 案例：卖家 4869 履约延迟异常；
- 严重程度：高风险；
- 案例状态：调查中；
- 上一周期延迟履约率：4.8%；
- 当前周期延迟履约率：36.4%；
- 变化：+31.6 个百分点；
- 当前结论：履约时长上升与延迟异常同时出现，承运表现可能相关，但不能确认因果；
- 履约分析和评价体验完成；
- 卖家对标因 Capability 不足跳过；
- 候选行动存在但尚未执行；
- 缺少承运商 SLA 变更记录和可靠对照组。

以上数值来自当前视觉和 Gold Case 代表场景。React 实现必须读取真实 Case、Lineage、Metric、Evidence、Hypothesis、Run 和 Action Projection，不得把位图内容硬编码成通用业务真相。

## 状态矩阵

| 区域       | v1 展示状态            | React 必须覆盖                                 |
| ---------- | ---------------------- | ---------------------------------------------- |
| Case       | 调查中、高风险         | 待调查、等待、阻塞、已解决、重新打开、结论不足 |
| 周期对比   | 两周期均可用           | 缺上一周期、窗口不完整、Metric 不可用          |
| 当前结论   | 验证通过但保留因果限制 | 未验证、被否定、部分支持、无结论               |
| Evidence   | 支持 Evidence 已核验   | 冲突、血缘缺失、待核验、能力不足               |
| Hypothesis | 有条件支持             | 提议、支持、反驳、已取代                       |
| Unknown    | SLA 和对照组缺失       | 无未知项、补数中、策略阻塞                     |
| Action     | Candidate 存在、未执行 | 无 Action、待审批、已批准、执行失败、已回滚    |
| Path       | 两条完成、一条跳过     | 等待、运行中、部分完成、失败、取消             |

## 视觉选择

- 中心是连续文档，而不是 KPI Dashboard。
- 周期差异使用一行对比，不使用趋势图或装饰图表。
- 结论单独强调“相关但不确认因果”。
- Evidence 和 Hypothesis 使用两行表格式摘要，不替代完整 Evidence Explorer。
- Unknown 明确显示，避免只展示成功结论。
- Action 明确标记“尚未执行”。
- 右侧只展示 Case 属性、数据范围和调查路径。
- 机器 ID 和原始事件代码不出现在主产品视图。

## 生成 Prompt

```text
Use case: ui-mockup
Asset type: high-fidelity Chinese desktop web application page, Commerce Case Detail
Input images: Image 1 is the most recent implemented 1440×900 React screenshot of the Chinese “电商经营诊断” Master Shell and is the strict visual-system reference. Image 2 is the approved Master Shell v2 mockup and is a secondary spacing reference. Generate a new original Case Detail page inside the same shell. Do not copy Codex branding or assets.

Primary request: Design the formal “案例详情” page for the existing Chinese Case-first ecommerce Agent workspace. Preserve Image 1’s exact light native workspace language: 260px warm-gray left navigation, white center canvas, compact top bar, floating rounded right panel beginning below the top bar, bottom runtime strip, and fixed rounded Case-bound composer. Change only the center task and right-panel content from the Master Shell timeline into a deep but restrained Case Detail view.

Language invariant: All user-facing labels, headings, statuses, descriptions, buttons, tabs and placeholders must be Simplified Chinese. No English UI labels. Do not show raw event codes, model IDs, Case IDs or Run IDs in this primary product view.

Canvas and shell invariants:
- wide 16:10 desktop screenshot, approximately 1440×900
- same light warm-gray left sidebar and white main canvas as the implemented Master Shell
- same original thin-line icon style, borders, radii, typography, spacing and muted colors
- same floating right panel with top margin, 16px corner radius and soft shadow
- same bottom runtime strip and composer
- no dark sidebar, no dashboard KPI tile row, no marketing layout

Left navigation: preserve the implemented Master Shell exactly.
Product title “电商经营诊断”.
Primary items “新建诊断”, “数据接入”, “案例队列”, “行动中心”. Highlight “案例队列”.
Workspace items “经营总览”, “数据能力”, “运行记录”, “技能与评测”, “作战室”.
Current Case item “履约延迟异常” selected with status “调查中 · 高风险”.
Bottom item “设置”.

Top bar:
- title “履约延迟异常”
- breadcrumb “案例队列 / 履约延迟异常 / 案例详情”
- refresh, overflow and inspector controls, restrained and original

Center Case Detail header:
- eyebrow “案例详情”
- main heading “履约延迟异常”
- subtitle “卖家 4869 当前周期的延迟履约率上升 31.6 个百分点”
- status pills “高风险”, “调查中”, “履约分析”
- compact metadata row: “分析周期 5月8日—5月14日”, “数据更新 10:32”, “证据 4 条”

Center navigation tabs, exact labels:
“概览”, “调查记录”, “证据”, “运行图”. Highlight “概览”.

Main center content should read like a structured Codex document, not a dashboard. Use thin dividers, typography and restrained inline blocks.

Section 1 heading “问题定义”.
Short text: “系统检测到当前周期的延迟履约率显著高于上一周期，需要判断异常来自订单结构、履约时长还是承运表现。”
Below it, one compact two-column comparison row with exact labels:
“上一周期” — “延迟履约率 4.8%”
“当前周期” — “延迟履约率 36.4%”
A small muted annotation “变化 +31.6 个百分点”. Do not add charts.

Section 2 heading “当前结论”.
A subtle verified conclusion block with text:
“延迟履约率上升与平均履约时长增加同时出现，承运表现可能是相关因素，但现有证据不足以确认因果关系。”
Status text “独立验证通过，保留因果限制”.

Section 3 heading “证据与假设”.
Use two compact document rows, not large cards:
1. label “支持证据” with text “指标变化和履约事实支持异常确实存在” and status “已核验”.
2. label “工作假设” with text “承运表现下降可能推高履约时长” and status “有条件支持”.
Add a text link “查看 4 条证据”.

Section 4 heading “未知项”.
Two concise bullet lines:
“尚未获得承运商服务等级变更记录”
“缺少可用于确认行动效果的可靠对照组”

Near the bottom, a compact action block:
Heading “候选行动”
Text “审查当前承运商服务等级与超时订单分布”
Status “尚未执行”
Button “查看行动详情”
Do not claim the action is approved, executed or effective.

Right floating panel:
Header “案例属性”.
Section “状态” with rows:
“严重程度 — 高风险”
“案例状态 — 调查中”
“最新结论 — 已验证”
Section “数据范围” with rows:
“经营主体 — 卖家 4869”
“分析周期 — 5月8日—5月14日”
“数据能力 — 履约完整，评价可用”
Section “调查路径” with rows:
“履约分析 — 已完成”
“评价体验 — 已完成”
“卖家对标 — 能力不足，已跳过”
At the bottom, link “查看数据血缘”.
No raw machine identifiers.

Bottom runtime strip exact user-facing text:
“运行详情 · 深度求索 V4 · 未重试 · 租约已释放”

Bottom composer placeholder exact text:
“继续询问这个案例，或添加新的电商数据……”
Controls “当前案例”, “目标循环”, attachment icon and circular send button.

Style/medium: realistic implementable Next.js product UI. Chinese desktop productivity application. Calm Codex-inspired information hierarchy but fully original. White and very light warm gray, charcoal text, fine 1px borders, 10–16px radii, almost no shadows except the floating inspector and composer. Muted red only for high risk, green only for verified, amber only for caveat. High density through typography and separators rather than cards.

Product invariants:
- Case is the authoritative object.
- All visible status derives from Case, Evidence, Hypothesis, Run and Domain Event projections.
- Conclusion clearly separates correlation from causality.
- Action is a candidate and has not executed.
- Chat remains secondary and Case-bound.
- Empty or unavailable data must be stated honestly.

Constraints: no Codex wordmark, no copied Codex icons, no Apple traffic lights, no logos, no trademarks, no watermark. No English user-facing copy. No raw technical IDs. No neon, glassmorphism, gradients, giant cards, excessive panels, marketing graphics, KPI dashboard row, GMV, CTR, ROI, ad spend, inventory, profit or unsupported business improvement. Avoid malformed Chinese and tiny illegible filler. Render only the requested concise text.
```

## 确认后实施顺序

```text
RED：Case Detail Projection / Metric comparison / status boundary tests
→ GREEN：Master Shell 内 Case Detail overview
→ REFACTOR：共享 Case header / tabs / inspector primitives
→ VERIFY：unit / type / scoped lint / Chromium desktop + mobile QA
```

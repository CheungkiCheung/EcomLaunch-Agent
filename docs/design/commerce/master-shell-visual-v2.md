# 电商经营诊断 Master Shell 视觉稿 v2

## 状态

- 使用内置 `imagegen` 工具于 2026-07-20 生成。
- 用户要求：面向用户的内容使用中文，整体风格参考 Codex Desktop。
- 用户于 2026-07-20 确认该中文、浅色 Codex-inspired 方向并要求开始执行。
- Master Shell React v1 已完成，实现路由为 `/commerce`。
- 图片：`docs/design/commerce/mockups/master-shell-visual-v2.png`。
- 尺寸：1619 × 971 PNG。
- SHA-256：`c682a3cc33932e8e60ac3a420222432ce3197d7b59578f529b67cd80cea34b4f`。

## 用户反馈形成的设计决定

上一版的深色侧栏、运营控制台式卡片和英文界面不再采用。新母版改为：

- 浅色、低对比度、接近原生桌面应用的统一工作区；
- 左侧是产品入口、工作区和当前案例；
- 中间是连续的结构化调查记录，视觉上接近 Codex 的任务正文，但数据仍来自 Domain Event；
- 右侧是轻量浮动检查面板，而不是固定的 Dashboard Inspector；
- 底部是绑定当前案例的悬浮输入框；
- 用户可见导航、标题、状态、按钮和说明全部使用简体中文；
- 不复制 Codex 品牌、图标、文案、Logo 或具体组件，只继承布局节奏、克制感和信息层级。

## 中文策略

正式前端默认使用中文：

- 导航、页面标题、状态、按钮、空状态、错误、说明和用户任务全部中文；
- 原始 `event_type`、Case ID、Run ID、模型 ID、Skill 版本和 Provider Request ID 只在工程详情或审计视图中保留机器原值；
- 主调查记录首先展示中文事件名称和中文解释；
- 不在主界面混用 `Case`、`Evidence`、`Action`、`Run`、`Agent Runtime` 等英文标签；
- `deepseek-v4-flash` 等不可翻译的模型标识仅作为审计字段出现，用户摘要可显示“深度求索 V4”。

## 页面目标

建立整个 Commerce Case Agent 的中文统一 Shell：

```text
左侧：全局入口、工作区、当前案例
中间：案例调查记录、证据结论、候选行动
右侧：输出、子智能体、证据来源
底部：运行详情、案例绑定输入框
```

Chat 仍然只是输入方式之一。当前案例、结构化事件、证据和行动是界面的主对象。

## 视觉稿中的代表状态

- 当前案例：卖家 4869 的履约延迟异常；
- 严重程度：高风险；
- 状态：调查中；
- 履约分析和评价体验子智能体完成；
- 卖家对标因数据能力不足被诚实跳过；
- 证据校验和独立验证完成；
- 候选行动已生成，但没有执行；
- 运行未重试，租约已释放。

这些只是展示母版所需的代表状态。正式实现必须从 Commerce API、Case Projection、Action Policy、Run、Lease 和 Domain Event 中读取，不得复制图片里的字面时间、数值或状态。

## 状态矩阵

| 区域 | v2 展示状态 | React 必须覆盖的其他状态 |
| --- | --- | --- |
| 左侧案例 | 当前选中一个高风险案例 | 无案例、已解决、等待数据、重新打开 |
| 调查记录 | 五个有序事件 | 空记录、未知事件、乱序事件、部分成功、失败 |
| 子智能体 | 两条完成、一条能力不足跳过 | 等待、运行中、阻塞、失败、取消 |
| 证据 | 必需证据已核验 | 缺失、冲突、血缘不可用、能力不足 |
| 候选行动 | 已就绪、等待查看 | 无行动、需要审批、执行失败、已回滚 |
| 运行详情 | 未重试、租约已释放 | 排队、等待输入、未知外部结果、租约占用 |
| 输入框 | 当前案例绑定、空闲 | 上传失败、只读、发送失败、上下文超限 |

## 选中版本的实现约束

- 页面使用浅色侧栏和白色主画布，不再实现深色侧栏版本。
- 信息密度通过排版、分隔线和连续记录实现，不依赖大量卡片。
- 中间区域不是自由文本消息列表；每一段调查记录必须能回溯到真实 Domain Event 或 Projection。
- 右侧“子智能体”状态来自当前 Run，而不是前端计时器或动画。
- 没有事件时显示空闲、等待或阻塞，不展示假运行状态。
- “候选行动已就绪”不代表已执行，也不代表经营指标改善。
- 正式实现中的“深度求索 V4”必须拼写正确；图片把它误生成为“深度求素 V4”，该错误只存在于位图参考。
- 窄屏时左侧导航折叠，右侧检查面板变为 Drawer，中心调查记录保持主视图。
- 需要为键盘焦点、悬停、错误、空状态、加载、Reduced Motion 和面板调整宽度补充代码级设计。

## 生成迭代

1. v1：深色侧栏、英文标签、控制台式布局；用户要求改为中文并参考 Codex Desktop，版本被拒绝。
2. v2：浅色中文工作区，采用左侧导航、连续调查记录、右侧浮动检查面板和底部输入框；当前选中为视觉评审候选。
3. 局部文字修正尝试：试图把“深度求素”修正为“深度求索”，但图像生成器导致整体布局漂移并退回深色英文控制台，因此丢弃该输出，未保存进仓库。

## v2 生成 Prompt

```text
Use case: ui-mockup
Asset type: high-fidelity desktop web application master shell, Chinese localization
Input images: Image 1 is the user-provided Codex Desktop screenshot and is only a style, spacing, density, and composition reference. Image 2 is the previously generated Commerce Case Agent Master Shell v1 and is only an information-architecture reference. Generate a new original interface; do not edit, trace, or copy either image literally.

Primary request: Create a shippable desktop UI mockup for an original Chinese ecommerce operations Agent product named “电商经营诊断”. Use the calm, native, document-centered workspace feeling of Image 1: light monochrome shell, quiet left navigation, large continuous center work area, compact floating right context panel, and a fixed rounded composer near the bottom. Preserve the Case-first product logic from Image 2, but remove the dark dashboard feeling, dense card grid, and English user-facing copy.

Language invariant: All user-facing interface text must be Simplified Chinese. Do not use English words in navigation, headings, tabs, statuses, descriptions, buttons, placeholders, or section labels. Avoid mixed Chinese-English copy. Machine identifiers are not needed in this visual. Render the requested Chinese labels verbatim and do not invent English filler.

Canvas and composition:
- Wide 16:10 desktop application screenshot, approximately 1440×900.
- A 250px pale warm-gray left sidebar, separated by one subtle vertical line.
- A clean white center workspace with a compact top title bar and a long vertically scrolling investigation record.
- A floating 300px right panel with rounded corners and a very soft shadow, visually similar in weight to Image 1’s right output panel but using original components.
- A large rounded fixed composer centered near the bottom of the main workspace.
- No dark sidebar, no dashboard KPI cards, no multi-column spreadsheet table, no marketing hero.

Left sidebar, exact Chinese labels and hierarchy:
Top product name: “电商经营诊断”
Primary actions:
“新建诊断”
“数据接入”
“案例队列”
“行动中心”
Section label: “工作区”
Items:
“经营总览”
“数据能力”
“运行记录”
“技能与评测”
“作战室”
Section label: “当前案例”
Selected item: “履约延迟异常”
Secondary item: “评价得分下降”
Bottom item: “设置”
Use simple original thin-line icons. The selected case uses a subtle light-gray rounded highlight, not a saturated color block.

Top bar:
- small folder icon and title “履约延迟异常诊断”
- breadcrumb text “案例队列 / 履约延迟异常”
- a restrained ellipsis menu
- two or three minimal view controls aligned right
- no brand logo, no large search bar

Center workspace:
Create a continuous document-like investigation record, not chat bubbles and not a card dashboard.
At the top, show title “履约延迟异常诊断” and concise subtitle “卖家 4869 当前周期的延迟履约率上升 31.6 个百分点”。
Show small inline status chips: “高风险”, “调查中”, “履约路径”.
Below, show a compact horizontal switch with exactly: “调查记录”, “证据”, “运行图”. Highlight “调查记录”.

The main record should contain a vertical sequence of five clean sections with subtle event markers and plenty of readable spacing. Use these exact user-facing event titles:
“案例已创建”
“调查已开始”
“履约分析已完成”
“证据校验通过”
“独立验证完成”
Each event has a short Chinese description and a muted timestamp. Do not display raw English event codes.

Expand “履约分析已完成” as a document subsection with heading “关键发现”, followed by two concise evidence lines:
“当前周期延迟履约率较上一周期上升 31.6 个百分点”
“平均履约时长增加 1.8 天”
Show small Chinese evidence badges “指标” and “事实”, and text status “已核验”.
Near the bottom, add a quiet conclusion block:
Heading “候选行动已就绪”
Description “系统已根据已核验证据生成一项可回滚的候选行动，等待查看。”
Button “查看行动”
Do not say the action has executed or caused improvement.

Right floating panel:
Header “检查面板” with a plus icon.
Section “输出” with one row “候选行动” and secondary text “等待查看”.
Section “子智能体” with exactly three compact rows:
“履约分析 · 已完成”
“评价体验 · 已完成”
“卖家对标 · 能力不足，已跳过”
Section “证据来源” with exactly three rows:
“订单数据”
“物流数据”
“评价数据”
At the bottom, include a restrained link “查看全部证据”.
Use tiny status icons, no animated avatars, no fake activity, no English technical telemetry on this primary panel.

Bottom composer:
A floating rounded input container similar in spatial role to Image 1 but with original styling.
Placeholder text exactly: “继续询问这个案例，或添加新的电商数据……”
Left controls: plus button and a small Chinese context chip “当前案例”.
Right controls: text “目标循环” and a dark circular send button.
Above the composer, add one very subtle collapsed runtime strip: “运行详情 · 深度求索 V4 · 未重试 · 租约已释放”.

Style/medium: realistic implementable product UI, original assets, Chinese desktop productivity application. Very light warm gray and white surfaces, charcoal text, muted gray secondary text, one restrained warm orange accent for the selected runtime/goal affordance, muted red only for high severity, muted green only for verified completion. Fine 1px dividers, 10–14px radii, soft native window shadows only on the floating right panel and composer. Compact modern Chinese sans-serif typography with generous line height. High information density achieved through typography and spacing rather than cards.

Preserve these product invariants:
- The current Case is the primary object.
- The center is a structured investigation record driven by Domain Events, even though it visually reads like a continuous document.
- Chat is a secondary Case-bound control surface.
- The right panel shows output, bounded subagent state, and evidence sources.
- No fake Agent motion or fabricated busy state.
- No claim of business improvement or causal effect.

Constraints: no Codex wordmark, no copied Codex icons or brand assets, no Apple traffic-light controls, no copied screenshot content, no trademarks, no watermark. No English user-facing copy. No neon, no glassmorphism, no dark sidebar, no gradients, no excessive cards, no dashboard charts, no KPI tile row, no GMV, CTR, ROI, ad spend, inventory, profit, or unsupported metrics. Avoid tiny illegible filler and avoid malformed Chinese. Use only the requested concise labels and descriptions.
```

## 已完成的实现门禁

本轮已经按照以下顺序完成：

```text
中文信息架构与事件 View Model RED 测试
→ Master Shell React 最小实现
→ 中文空状态、错误和运行状态
→ 单元测试、类型检查、Lint
→ 真实浏览器交互
→ 桌面与窄屏截图 QA
→ 下一页 Case Detail 图像生成
```

## React 实现结果

关键文件：

```text
frontend/src/app/commerce/layout.tsx
frontend/src/app/commerce/page.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/view-model.ts
```

实现截图：

```text
docs/design/commerce/implementation/master-shell-react-desktop-v1.png
docs/design/commerce/implementation/master-shell-react-mobile-v1.png
```

实现与视觉稿保持一致的部分：

- 中文浅色工作区；
- 左侧全局入口、工作区与当前案例；
- 中间连续调查记录；
- 桌面右侧悬浮圆角检查面板；
- 移动端侧滑导航和检查面板；
- 底部运行详情和案例绑定输入框；
- 少卡片、薄边框、低饱和状态色；
- `深度求索 V4` 拼写在代码中已修正；
- 没有真实事件时不显示假 Agent 活动。

基于真实 API 合同产生的差异：

- 视觉稿中的业务数值、日期、Source 名称和 Path 数量没有硬编码；
- 主标题根据已持久化 Path Event 和 Case Lineage 投影；
- 英文后端 Case 标题和 Evidence 摘要不会直接泄露到中文主界面；无法确定的内容使用受控中文摘要；
- 时间线保留真实 `path.started` 和 `run.lease_released` 等事件，因此代表状态可能多于视觉稿的五行；
- 右侧证据来源当前按可验证的指标、事实和矛盾 Evidence 分类；数据源系统名将在 Evidence Explorer 完成后展示；
- 当前没有 Commerce Case-bound 问答 API，输入框不会假装发送；用户提交时明确提示内容未发送、未启动调查；
- 未实现页面的导航入口保持禁用并有说明，不导航到不存在的页面。

## 浏览器 QA

桌面：

- 1440 × 900；
- 检查面板为顶部留白的圆角悬浮容器；
- Case、Timeline、Runtime 和 Composer 层级与视觉稿一致；
- 浏览器控制台 warning/error：0。

移动端：

- 390 × 844；
- 左侧导航与右侧检查面板均为 off-canvas；
- `documentElement.scrollWidth === clientWidth === 390`；
- 浏览器控制台 warning/error：0。

验证：

```text
Vitest: 31 files, 237 tests passed
TypeScript: passed
Scoped ESLint: passed
Commerce Playwright mechanical UI: 3 passed
Next production build: passed with one pre-existing Turbopack NFT trace warning
```

`pnpm check` 的仓库级 ESLint 仍会被 Legacy EcomLaunch 文件中的既有错误阻塞；本次没有越界修改这些只读 Legacy 文件。Playwright 中的结构化 mock API 只验证 UI 机械行为，不能作为 Agent 或 DeepSeek V4 验收。

最终仓库检查：`git diff --check` 通过。仓库级 `pnpm check` 的剩余基线为 Legacy EcomLaunch `5 errors / 2 warnings`；Commerce 新增目录的限定 ESLint 为通过。

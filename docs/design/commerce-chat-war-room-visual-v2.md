# Commerce Chat + 游戏化协作空间视觉决策 v2

> 日期：2026-07-26  
> 工具：内置 `image_gen`，`ui-mockup` / `stylized-concept` 预览模式  
> 状态：2026-07-27 用户已确认“优先使用 DeerFlow 前端，再加入游戏化 War Room”；Chat + 协作空间 React 已实现，原创运行时图像资产 v1 已接入并完成机械浏览器验证

## 决策背景

用户明确希望前端优先复用 DeerFlow 的原生前端，再叠加游戏化 War Room。当前版本将其收敛为：

```text
DeerFlow 原生 Chat
  + 中文 Commerce Agent Badge
  + 紧凑 Durable Task/Event 状态
  + Evidence / Artifact / Approval 按需展开
  + “查看协作空间”入口
        ↓ 用户主动点击
游戏化 Commerce 协作空间
```

Chat 是默认产品，不是协作空间的外壳；协作空间是解释 Subagent 生命周期的观察层，不是固定 Dashboard，也不是单独模拟一个市场。

## Chat 候选稿

候选稿在当前 Codex 任务中由内置 `image_gen` 生成，使用当前 Codex 截图作为“布局密度参考”，不复制品牌资产。

### 页面目标

- 浅暖白背景、克制的深灰文字和细分隔线；
- 窄侧栏只放新建对话、历史对话和高级详情入口；
- 中间是持续中文对话，不默认打开 Case、Evidence 或 Inspector；
- 回答内嵌一条紧凑可展开的 Task 活动摘要；
- 顶部提供“查看协作空间”，底部是文件上传与持续追问 Composer；
- 不使用 KPI 墙、固定三栏、巨大图表或英文 UI。

### 代表状态

视觉稿使用以下代表状态表达结构，不作为前端业务常量：

- `晚到率 8.4% → 13.7%`；
- `处理时长 基本稳定`；
- `运输时长 上升`；
- `探索 / 分析 / 核验` 三个真实 Task；
- `独立核验 已通过`。

React 必须读取 `CommerceRunTaskActivityViewModel`，真实指标和事件来自后端；视觉稿数字只用于审查布局与信息层级。

## War Room 候选稿

候选稿在当前 Codex 任务中由内置 `image_gen` 生成，使用上一张图仅作产品 Chrome 参考，使用用户提供的角色工位图仅作“微缩工作场景”隐喻参考。

### 页面目标

- 左上“返回对话”，顶部显示 Thread 标题和 Run 终态；
- 中央为明亮、克制的等距微缩电商调查工作室；
- 只出现当前真实 Task 对应的角色；本次代表状态是 `探索 / 分析 / 核验` 三人；
- 角色不是固定 Crew，不随机游走，不从聊天文本推断忙碌；
- 工具道具必须来自 `task.tool_result`，例如订单与评价数据箱、指标比较板、证据卡、核验盾牌；
- 右侧只在选中 Actor 后打开轻量 Drawer，不做常驻三栏 Inspector；
- 底部事件轨迹显示 `探索 已完成 / 分析 已完成 / 核验 已完成 / 共 3 个真实任务`；
- 页脚明确提示“人物与动作来自真实 Task/Event；无任务时不显示角色”。

### 原创资产约束

- 使用原创小人和原创微缩场景；
- 不使用鹿、黑色动物轮廓、Marvis 角色或其他品牌角色；
- 不把角色数量、名称、颜色和动作写死在渲染器；
- `CommerceCollaborationSceneViewModel` 是唯一渲染输入；
- `queued / working / waiting / approval / blocked / completed / failed / cancelled / timed_out` 映射为明确的可访问状态和 reduced-motion 静态状态。

## 实现顺序

1. 用户确认 Chat 与协作空间候选母版；
2. 先为 DeerFlow Chat 接入 Commerce Agent Badge、按钮、Sidebar 路由和紧凑 Task 卡片的失败测试；
3. React 实现 Chat 增量，不重写 DeerFlow `Thread / Message / Composer`；
4. 依据 `CommerceCollaborationSceneViewModel` 实现场景容器和静态 fallback；
5. 在状态合同冻结后生成原创角色、工位和工具道具资产；
6. 真实浏览器交互与截图视觉 QA；
7. 连接真实后端与 fresh DeepSeek V4，执行 Agent Browser Release Gate。

## 生成 Prompt 摘要

### Chat

`ui-mockup`；默认中文 Chat-first 电商经营诊断；DeerFlow/Codex 式克制工作区密度；窄侧栏、中央连续对话、无常驻 Inspector；回答中包含“目前能确认 / 证据 / 反证与限制 / 下一步”、紧凑 Task 摘要和“查看协作空间”；全中文；禁止品牌 Logo、鹿、动物角色、Dashboard KPI 墙和英文 UI。

### War Room

`ui-mockup + stylized-concept`；按需打开的中文“协作空间”；中央明亮等距微缩调查工作室；仅展示真实 Task 对应的原创人类小人；代表任务为探索、分析、核验；道具来自 Tool Result；右侧选中 Actor Drawer；底部真实事件轨迹；全中文；禁止固定六人 Crew、随机漫游、假忙碌、鹿、黑色动物角色、Marvis 品牌、巨大图表和水印。

## 2026-07-26 候选稿阶段限制

- 当时的候选图只在任务中展示，未作为运行时资产；
- 候选阶段没有从聊天文字或计时器伪造 Task 状态；
- 该限制已由下方 2026-07-27 的 React v2 浏览器截图和 SHA-256 证据替代。

## 2026-07-27 确认与 React v2 证据

用户确认的产品顺序是：

```text
DeerFlow 中文 Chat 主入口
→ 紧凑真实任务状态
→ 用户主动打开游戏化协作空间
```

本轮继续使用内置 `image_gen` 生成 active-state Chat 与协作空间视觉母版。视觉母版影响了 React v2 的工位布局、暖白配色、任务角色层级和底部事件轨迹；运行时没有把生成图直接当作业务状态或界面截图。

真实浏览器中的 React v2 证据：

- `docs/design/commerce/mockups/commerce-agent-chat-react-v2-desktop.png`
  - SHA-256：`7523081fde80d3efd52c9053cf16b77c8e58e2bb6347e9ecdcf187647ff780c7`
- `docs/design/commerce/mockups/commerce-collaboration-react-v2-active-desktop.png`
  - SHA-256：`507a4046072fa42ce8d63d73f20f0f2ce5c770f0faa28b92e728b95d057cc56f`

实现差异与保留项：

- 保留 DeerFlow 的 Thread、Message、Composer、文件和历史对话能力，不重写 Chat 底座；
- Commerce 模式下产品标识改为中文“经营诊断”，顶部不常驻模型用量；
- 每个真实 Durable Task 同时投影一个角色和一个任务工位；没有 Task 时仍不显示角色或工位；
- 已完成任务保留最后一次真实 Tool Result 对应的道具，例如“全量覆盖”“窗口对比”；
- 当前角色、空场景和工位已经使用内置 ImageGen 生成的原创运行时资产；完整 Prompt、去底参数、SHA-256 和映射见 `docs/design/commerce-collaboration-imagegen-assets-v1.md`；
- CSS/React 仍只负责状态、布局、可访问性和 reduced-motion，不从图像推断 Task 状态；
- 当前真实 Run 的核验角色显示“地域分段”，这暴露了 Verifier Tool 包仍偏离冻结最小包，属于后端 Release Gate 待修问题，不由前端伪装。

# Frontend Instructions

先遵循仓库根目录 `AGENTS.md`，再遵循本文件。现有 Next.js、Thread 和 Message 架构细节见 `CLAUDE.md`。

## Product Model

- 新前端是 Chat-first Commerce Workspace，默认复用 DeerFlow 的 Thread、Message、Composer、Subtask 和 Artifact 体验。
- 用户通过上传真实数据和自然问题开始任务；Case 是复杂任务的内部持久化对象，不是所有交互的前置条件。
- Evidence、Artifact、Action Approval 和紧凑 Subagent 状态内嵌 Chat；高级详情按需展开。
- 固定 War Room 不再是目标产品页面；点击“查看协作空间”后切换到真实事件驱动的游戏化 Subagent 场景。
- 不允许从消息文本、角色文案、前端计时器或随机动画推断 Case / Run 状态。
- 没有真实事件时显示空闲、等待或阻塞，不播放假忙碌。

## Feature Flag

- Commerce 入口只在 `featureFlags.commerceCaseAgent` 为 `true` 时显示。
- 后端 `COMMERCE_CASE_AGENT_ENABLED` 也必须开启；前端 Flag 不能绕过后端边界。
- 新旧路由、状态模型和 API Client 不混用。

## Image-first Design

- Chat 主界面和游戏化协作空间必须先生成高保真视觉稿，再实现 React / Canvas 页面。
- 视觉稿需要记录页面目标、数据状态、生成 Prompt、选中版本和实现差异。
- 默认 Chat 采用 Codex-inspired Workspace：克制、自然回答、紧凑的可展开运行状态。
- 协作空间使用原创游戏小人和明亮克制的微缩工作场景；不使用鹿，不复制 Marvis 角色或品牌资产。
- 场景角色、工位和动画必须映射真实 Task Event；状态合同冻结后再使用图像生成制作统一资产。
- 不复制 Codex 品牌资产；形成 Commerce Case Agent 自己的信息架构。
- 视觉选择属于关键产品节点，需要用户确认；确认前可以继续后端合同和数据层工作。

## Engineering

- 业务类型放在 Commerce 专属命名空间，不污染通用 Thread / Message 类型。
- Domain Event 到 View Model 的转换保持纯函数，并为未知事件和乱序事件提供显式处理。
- Server Component 默认；只有交互组件使用 `"use client"`。
- 保持键盘操作、焦点、对比度、响应式和 reduced-motion 支持。
- 不手工修改 `components/ui/` 和 `components/ai-elements/` 的生成文件。
- 更新后同步维护根 `README.md`、本目录 `CLAUDE.md` 和视觉决策记录。

## Testing and QA

- 纯 View Model、Reducer、事件排序和格式化测试不调用模型。
- 任何验证 Agent 输出或完整 Commerce 流程的前端 E2E，必须连接真实后端并使用真实 DeepSeek V4。
- Mocked backend E2E 只能验证通用 UI 机械行为，不能作为 Commerce Agent 验收或 Release Gate。
- 页面实现后运行单元测试、类型检查、Lint、真实浏览器交互和视觉截图对比。
- 游戏化协作空间验收必须证明每个可见角色、动作、屏幕内容和状态都能追溯到真实 Task / Domain Event。

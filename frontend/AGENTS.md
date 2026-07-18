# Frontend Instructions

先遵循仓库根目录 `AGENTS.md`，再遵循本文件。现有 Next.js、Thread 和 Message 架构细节见 `CLAUDE.md`。

## Product Model

- 新前端是 Case-first Commerce Workspace，Chat 只是调查与协作入口之一。
- 核心对象包括 Dataset、Capability、Case、Evidence、Hypothesis、Action、Approval、Follow-up 和 Domain Event。
- Timeline、Graph、War Room、Evidence、Action 和 Follow-up 必须读取同一个结构化事件与 Case 状态。
- 不允许从消息文本、角色文案、前端计时器或随机动画推断 Case / Run 状态。
- 没有真实事件时显示空闲、等待或阻塞，不播放假忙碌。

## Feature Flag

- Commerce 入口只在 `featureFlags.commerceCaseAgent` 为 `true` 时显示。
- 后端 `COMMERCE_CASE_AGENT_ENABLED` 也必须开启；前端 Flag 不能绕过后端边界。
- 新旧路由、状态模型和 API Client 不混用。

## Image-first Design

- 每一个正式页面，包括 War Room，都必须先生成高保真视觉稿，再实现 React 页面。
- 视觉稿需要记录页面目标、数据状态、生成 Prompt、选中版本和实现差异。
- 采用 Codex-inspired Workspace：克制、信息密度高、清晰的工作区层级、可检查的运行状态。
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
- War Room 验收必须证明每个可见活动都能追溯到真实 Domain Event。

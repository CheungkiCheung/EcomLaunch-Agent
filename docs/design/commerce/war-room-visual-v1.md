# 电商经营诊断作战室视觉稿 v1

## 状态

- 2026-07-23 使用当前会话内置 Image Generation 生成桌面与移动高保真稿；
- 已人工检查中文、信息密度、事件可追溯性、桌面/移动响应式和无假活动边界；
- 选定“事件泳道 + 领域事件流”作为 React 实现基准；
- 旧 EcomLaunch Pixel Office 只作为 Legacy 资产保留，不复用其消息推断、计时运动或角色忙碌状态。

## 用户任务

作战室是同一个真实 Run 的运营观察视图，不是另一个产品，也不是 Agent 动画：

```text
当前观察的是哪个 Case / Run？
最新持久化事件是什么？
哪些 requested Path 已完成、正在运行、阻塞或未开始？
Evidence Barrier 为什么等待或放行？
主智能体综合和新鲜上下文验证是否真的启动？
本轮新增了哪些支持、矛盾或未知证据？
最新 Checkpoint 能否说明当前循环和恢复边界？
没有新事件时，页面是否保持安静而不是播放假忙碌？
```

## 关键视觉决定

- 顶层页面名称为“作战室”，正文标题为“观察正在进行的调查”；
- 桌面使用宽事件泳道与窄领域事件流两栏；移动端按 Run 卡、摘要、纵向泳道、证据、Checkpoint、事件流顺序展开；
- 只有拥有 `path.started` 且尚未终止的 Path 可以显示“进行中”；
- `path.completed / path.blocked / path.failed` 决定终态，不能从 Run 总状态或计时器替代；
- Evidence Barrier 继续使用“全部 requested Path 终态 + 主智能体启动事件”的确定性派生规则，不伪造 `evidence.barrier_released`；
- 主智能体综合与 Verification 没有权威事件时显示“尚未开始”；
- 证据变化只统计选中 Run 的真实 `evidence.appended` 事件及其 relation；
- 最新 Checkpoint 读取持久化快照，不由前端累加；
- 领域事件流按 `run_sequence` 排序，未知事件显式显示为未知；
- 没有新事件时显示“等待下一条持久化事件”，不使用脉冲、倒计时、头像或随机动画；
- 默认运营视图不显示模型、令牌、延迟和 Retry；这些留在 Agent Run 工程检查页；
- 无 Chat Composer，底部只有“打开案例”和“检查完整运行记录”。

## 视觉资产

```text
docs/design/commerce/mockups/war-room-visual-v1-desktop.png
尺寸：1536 × 1024
SHA-256：22b4ecdef79315d090f6bf9af623301e78756f8a7260158b5c0ca205e21b47ad

docs/design/commerce/mockups/war-room-visual-v1-mobile.png
尺寸：793 × 1983
SHA-256：d0820147770dece64e59ff905fdf34069c43af11c52fc6dcabd4b11a667a65dd
```

## 桌面最终 Prompt

```text
Use case: ui-mockup
Asset type: Commerce Case Agent desktop War Room web page, 1536×1024 high-fidelity shippable product UI
Primary request: Design a Chinese top-level “作战室” page that observes one real in-progress ecommerce investigation Run through persisted domain events. Match the restrained light Commerce workspace. This is NOT a pixel office, game, avatar scene, or simulated market.
Composition/framing: existing left navigation; a wide operational event-lane document on the left and a narrow ordered event-stream rail on the right.
Subject: selected Case/Run; four state summaries; Goal/Path/Barrier/Lead/Verification lanes; evidence changes; latest Checkpoint; ordered event stream; quiet waiting state; links to Case and complete Run record.
Text: all user-facing labels in simplified Chinese. Raw event numbers, Run ID fragments and timestamps are allowed.
Constraints: no avatars, office, pixel art, speech bubbles, fake motion, pulse, countdown, chat composer, model telemetry, chain-of-thought, dark theme, gradients, unsupported KPI claims or watermark.
```

## 移动最终 Prompt

```text
Use case: ui-mockup
Asset type: Commerce Case Agent mobile War Room web page, portrait high-fidelity shippable product UI
Primary request: Create the true responsive mobile version of the Chinese “作战室” page for observing one real in-progress Run through persisted domain events.
Composition/framing: top bar then single-column document flow; selected Run card; 2×2 summary; vertical event-backed lanes; evidence changes; Checkpoint; domain event stream; normal-flow actions.
Text: all user-facing labels in simplified Chinese. Event numbers, Run ID fragment and timestamps are allowed.
Constraints: no desktop sidebar compression, avatar, office, pixel art, speech bubble, fake activity, pulse, countdown, chat, model telemetry, chain-of-thought, dark theme, gradient, KPI claims or watermark.
```

两张图均通过内置 Image Generation 生成，没有切换 CLI 或其他图像模型。

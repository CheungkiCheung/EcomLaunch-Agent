# Store Operator War Room 视觉决策 v1

## 目标

Store Operator 的主体验仍是中文 Chat。War Room 只负责把真实 Subagent 活动变成轻量、可观察的空间反馈，不承担经营看板、任务编排或模拟经营功能。

视觉风格延续旧 EcomLaunch 的明亮游戏人物语言，但修正旧版人物过大、页面元素过满的问题：角色应当属于办公室，而不是遮挡办公室。

## ImageGen 母版

母版：[`war-room-concept-v1.png`](./war-room-concept-v1.png)

运行时无人物背景：[`frontend/public/images/store-operator/war-room/background-v1.png`](../../../frontend/public/images/store-operator/war-room/background-v1.png)

母版尺寸为 `1672 × 941`，使用 16:9 宽屏构图。场景只安排四个独立工位：

- 中央：经营主理人（Parent）；
- 左侧：数据侦察员（Explore）；
- 右侧：经营分析师（Analyst）；
- 下方：证据核验员（Verifier）。

## 生成提示词

视觉母版使用的核心提示词：

```text
Create a polished 16:9 game-like ecommerce operations war room concept art,
matching a bright friendly management-game office aesthetic. Use mint green,
warm cream, pale wood and soft teal. Exactly four small chibi office characters
and four clearly separated workstations: a central operations lead desk, a data
exploration desk on the left, an analysis desk on the right, and a verification
desk at the lower area. Keep a wide open central walking path. Characters should
be visibly smaller than the furniture, approximately 65%-72% of workstation
height, with consistent proportions. Include a restrained data wall, windows,
plants and a small coffee corner. No deer, no dark cyberpunk HUD, no conveyor,
no crowd, no extra character, no large dashboard overlay, no text labels, no logo.
Clean orthographic/isometric hybrid composition, soft shadows, readable zones,
production-ready game environment art.
```

运行时背景是在母版基础上编辑得到，要求移除四个人物并完整修复人物身后的地板、桌椅和设备；角色由前端独立渲染，才能准确映射真实 Task 状态。

## 运行时比例

前端角色宽度控制在场景宽度的 `4.2%–5.2%`。人物只允许三个状态：

```text
roaming → returning_home → working
```

- `roaming`：未被调用时在有限区域轻量移动；
- `returning_home`：收到真实 `task` Tool Call 后返回对应工位；
- `working`：到达工位后展示工作动作；
- Task completion contract 到达后恢复 `roaming`；
- `prefers-reduced-motion` 时角色固定在工位，不执行走动过渡。

## 状态真实性

War Room 解析当前 DeerFlow 线程中的真实 AI Message 和 Tool Message：

1. AI Message 中出现 `task` Tool Call；
2. `subagent_type` 映射到 Explore、Analyst 或 Verifier；
3. 对应 Tool Message 返回完成协议；
4. 角色由工作状态恢复空闲。

未被调用的角色必须保持空闲。界面不得通过计时器随机制造“正在分析”的假象。

## 有意不做的内容

- 复杂碰撞和寻路；
- 角色搬运文件或产物；
- 汇报、庆祝和跨 Agent 交接动画；
- 模拟进度、假任务或自动忙碌；
- 经营指标 HUD、复杂 Case 侧栏或固定状态机；
- EcomLaunch 与 Store Operator 的人物联动。

这些能力会提高视觉噪音和维护成本，但不会改善当前“上传数据后得到可信分析”的核心体验。

## 验收条件

- 桌面宽屏下，人物不遮挡主要工位和中央通道；
- 390px 宽度无横向滚动，War Room 仍可辨识；
- reduced-motion 下没有持续位移动画；
- 只有真实 `task` 调用对应的角色进入工作状态；
- Task 完成后角色恢复空闲；
- 页面无严重 Console Error，图片无拉伸和错误裁切。

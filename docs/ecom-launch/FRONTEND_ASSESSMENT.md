# OpenSKU 前端评估报告

## 一、项目概况

| 维度 | 数据 |
|---|---|
| **产品定位** | 电商 SKU 自适应上新决策循环 |
| **技术栈** | Next.js 16 + React 19 + Tailwind CSS 4 |
| **UI 框架** | Radix UI + Lucide Icons |
| **状态管理** | TanStack Query + React Hooks |
| **可见工作区** | Chat + OpenSKU Launch Loop + War Room |
| **代码规范** | ESLint + Prettier + Vitest |

前端的核心任务不是展示一个“7 天包”，而是让用户看到一次 SKU 上新循环正在推进：当前阶段是什么、证据从哪里来、每个 agent 在做什么、最终为什么建议 Go / Pivot / Hold / Kill / Scale，以及下一轮测试和宣传计划怎么调整。

---

## 二、前端结构

### 2.1 核心目录

```text
frontend/src/
├── app/                    # Next.js App Router
│   └── workspace/          # 主工作区
├── components/
│   ├── ui/                 # 基础 UI 组件
│   └── workspace/
│       └── ecom-launch/    # OpenSKU / EcomLaunch 工作区
├── core/
│   ├── agents/             # Agent 管理
│   ├── i18n/               # 中英文文案
│   ├── messages/           # 消息处理
│   └── threads/            # 线程管理
└── hooks/                  # 自定义 Hooks
```

### 2.2 OpenSKU 相关组件

```text
frontend/src/components/workspace/ecom-launch/
├── war-room-page.tsx
├── war-room-canvas-stage.tsx
├── war-room-assets.ts
├── war-room-motion.ts
├── launch-crew-activity-model.ts
└── index.ts
```

---

## 三、功能评估

### 3.1 已完成功能

| 功能 | 状态 | 说明 |
|---|---|---|
| **聊天界面** | Built | 支持常规 agent 对话 |
| **Agent 入口** | Built | OpenSKU Launch Loop 可作为专属工作区进入 |
| **消息流式** | Built | 支持运行过程中的持续反馈 |
| **文件上传** | Built | 可上传 SKU 背景、规格、截图、CSV 等材料 |
| **设置面板** | Built | 包含语言、记忆、技能、通知等设置 |
| **多语言** | Built | 中英文入口文案已统一为 OpenSKU |
| **War Room 可视化** | Built | 展示 Launch Crew、任务状态、产出物和进度 |
| **Artifact 预览** | Built | 可查看 HTML、Markdown、CSV、JSON 等产出 |

### 3.2 OpenSKU 特定功能

| 功能 | 状态 | 当前价值 |
|---|---|---|
| **Launch Crew 展示** | Built | 把 market、offer、growth、asset、evidence 角色可视化 |
| **War Room 动画** | Built | 让长任务执行过程更可感知 |
| **白板/进度模型** | Built | 展示任务推进和 artifact 生成状态 |
| **Launch Decision Pack 文件列表** | Built | 展示当前循环快照所需文件 |
| **阶段/决策文案入口** | Updated | 从固定周期验证包改为自适应上新循环 |
| **Launch Stage / Decision 首屏状态条** | Built | War Room 第一屏固定展示阶段、决策、artifact readiness、私域指标边界 |
| **Promotion Replan / Knowledge Deltas 展示** | Built | `launch-state.json`、`promotion-replan.md`、`knowledge-deltas.json` 有专门循环状态入口 |

---

## 四、产品表达评估

### 已修正的旧口径

| 旧表达 | 问题 | 新表达 |
|---|---|---|
| 旧增长引擎品牌名 | 项目身份分裂 | OpenSKU 是公开产品名 |
| EcomLaunch 验证台 | 更像内部工具名 | OpenSKU Launch Loop / OpenSKU 上新循环 |
| 固定周期验证包 | 误导用户以为周期固定 | Adaptive Launch Loop / 下一轮自适应验证计划 |
| 一次性验证包 | 像一次性报告 | Launch Decision Pack 是当前循环快照 |
| 泛增长报告 | 太泛，和电商 SKU 职位不贴 | SKU 上新阶段诊断、宣传重排、知识沉淀 |

### 当前第一屏应传达

1. 这是 OpenSKU，不是 DeerFlow 原项目的普通改皮。
2. 这是电商 SKU launch loop，不是泛增长报告。
3. 它能处理“没有后台数据”和“上传早期反馈”两类现实情况。
4. 7 天只是 demo 默认节奏，真实周期由阶段和证据决定。
5. War Room 是 demo 层，核心价值是证据治理、决策、重排和沉淀。

---

## 五、代码质量评估

### 优势

| 优势 | 说明 |
|---|---|
| **类型安全** | TypeScript 覆盖主要前端逻辑 |
| **组件边界清晰** | OpenSKU 工作区组件集中在 `workspace/ecom-launch/` |
| **可测试性** | War Room asset、motion、activity model 已有单元测试入口 |
| **国际化可维护** | 主要可见文案集中在 i18n locale 文件 |
| **产品演示感强** | War Room 让多 agent 长任务不是黑盒 |

### 待改进

| 问题 | 建议 |
|---|---|
| **组件仍偏大** | 继续拆分 War Room page、canvas stage、artifact panel |
| **评测结果未前端化** | 后续增加 eval score、evidence coverage、unsupported-claim count |
| **真实后端 UI 截图仍偏少** | 目前已有 mock thread 桌面/移动截图；后续补真实 live thread UI 截图 |

---

## 六、秋招展示评估

### 当前亮点

| 维度 | 说明 |
|---|---|
| **垂直场景清楚** | 聚焦电商 SKU 上新，而不是泛 AI 工具 |
| **Agent 编排可解释** | 五个角色对应真实 launch 工作流 |
| **长任务可视化** | War Room 展示执行状态和产出物推进 |
| **数据边界意识强** | UI 和文档都强调 unavailable、uploaded_real、observed_public |
| **可扩展到 eval/knowledge** | 后续能自然讲到 agent harness、knowledge deltas、eval harness |

### 面试叙事建议

不要把项目讲成“我做了一个 7 天上新包生成器”。更强的讲法是：

```text
我基于一个 LangGraph agent runtime 做了 OpenSKU，一个电商 SKU 上新决策循环。
它先判断 SKU 阶段，再用公开证据和上传数据生成 Launch Decision Pack，
如果用户有早期反馈，还会重排下一轮宣传计划，并把可复用经验沉淀成 knowledge deltas。
前端 War Room 负责把多 agent 长任务可视化，后端契约测试保证默认产出和数据边界不会漂。
```

---

## 七、改进路线

### 短期

1. 将 eval score、evidence coverage、unsupported-claim count 前端化。
2. 补真实 live thread 的 UI 截图或视频证据。
3. 将旧“验证包”文案继续从非核心历史文档中下沉为 archived context。

### 中期

1. 增加 agent eval harness：禁用虚假指标、unsupported claim、evidence ID、artifact completeness。
2. 增加 demo cases：idea-only、supplier sample、pre-launch test、soft launch feedback。
3. 将 knowledge deltas 做成可查询的类别经验库。

### 长期

1. 接入真实店铺导出样例和匿名 benchmark cases。
2. 支持循环间对比：本轮判断、实际反馈、下轮调整。
3. 做成可复用的垂直 agent skill 模板。

---

## 八、总结

| 维度 | 评分 | 说明 |
|---|---:|---|
| **技术架构** | 8/10 | 前后端边界清楚，已有专属 agent/skill/UI |
| **产品表达** | 8/10 | 已从“7 天包”收束到自适应上新循环 |
| **用户体验** | 7/10 | War Room 有辨识度，但循环状态展示还可加强 |
| **测试基础** | 7/10 | 有契约测试和前端单测，但 eval harness 仍待补 |
| **秋招适配** | 8/10 | 适合讲 agent 工程、垂直场景、评测和知识沉淀 |

当前前端已经能支撑 OpenSKU 的作品集演示。下一步不是继续堆视觉效果，而是把 launch stage、promotion replan、knowledge deltas 和 eval 结果做成明确的信息架构。

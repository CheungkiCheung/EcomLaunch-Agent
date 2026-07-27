# 电商经营诊断技能与评测视觉稿 v1

## 状态

- 2026-07-23 使用当前会话内置 Image Generation 生成桌面与移动高保真稿；
- 已人工检查页面层级、中文文案、桌面/移动响应式和治理边界；
- 选定桌面“两栏工作区”和移动“单列文档流”作为 React 实现基准；
- 已实现严格 Skill Candidate / Experiment / Active Pointer 合同、候选评测依据 API、React、人工激活/回滚机械交互和截图 QA；
- React 读取真实 Skill Candidate、Experiment、Shadow Run ID 和 Active Pointer，不把视觉稿中的代表数字写死。

## 用户任务

“技能与评测”不是模型排行榜，也不是让运行中的智能体直接改 Prompt。它帮助工程与治理人员回答：

```text
当前生效的技能版本是什么？是否真的存在 Active Pointer？
候选版本解决了哪类真实失败，内容哈希和来源实验是什么？
安全扫描、离线评测、回归、留出集和 Shadow 是否全部通过？
Control 与 Candidate 在冻结 Gold Case 上的通过率、硬门禁、令牌和延迟如何？
Shadow 是否使用真实 Run，是否保持业务对象无副作用？
为什么还不能自动生效？由谁人工审查？
激活或回滚后，候选、实验和审查证据是否仍然保留？
```

## 关键视觉决定

- 顶层页面名称为“技能与评测”，正文任务标题为“治理技能演进”；
- 桌面只使用“候选版本队列 + 单一治理文档”两栏，不再增加常驻右侧 Inspector；
- 移动端只显示一个候选选择卡，避免候选列表和当前候选重复；
- 七阶段演进门禁固定为：候选提出、安全扫描、离线评测、留出集、影子运行、人工审查、生效；
- 阶段状态必须由 Candidate 字段和 Active Pointer 投影，不从进度动画、时间或自然语言推断；
- 冻结实验对比读取 Experiment Definition / Report，先看 hard gate，再比较质量、令牌和延迟 Pareto；
- Shadow 默认只展示候选记录中真实持久化的 Run ID。没有 Shadow audit API 时，不显示虚构请求编号、令牌或延迟；
- Passing Experiment 和 Shadow 只产生“可人工审查”的 Candidate，不自动更新 Active Pointer；
- 激活和回滚都是人工、Workspace-scoped、幂等操作；Actor 缺失时按钮禁用；
- 无 Chat Composer、Agent 头像、脉冲动画、隐藏推理正文或虚构业务提升。

## 视觉资产

```text
docs/design/commerce/mockups/skills-evals-visual-v1-desktop.png
尺寸：1536 × 1024
SHA-256：b5a8f32747b4e8b5a26c1c51634ecbca97867c32f06e149a6d0d46e574d8ab9b

docs/design/commerce/mockups/skills-evals-visual-v1-mobile.png
尺寸：794 × 1981
SHA-256：db2e29c9a487d9f53dd7b316ac215af9ed10ab2d53d50c286786e67ec98c84a3
```

## 桌面最终 Prompt

```text
Use case: ui-mockup
Asset type: Commerce Case Agent desktop web application page, 1536×1024 high-fidelity shippable product UI
Primary request: Design the top-level Chinese page “技能与评测” for an auditable AI-agent skill evolution and evaluation workflow. Match the restrained light Codex-inspired document workspace style of the most recent Commerce Agent Run screenshot in this conversation, but do not copy Codex brand assets.
Scene/backdrop: full desktop app screenshot with the existing left navigation rail and top bar. Off-white app shell, white document surfaces, hairline gray borders, very subtle shadows, muted green for passed gates, amber for pending human review, red only for failures.
Composition/framing: landscape desktop. Left app navigation about 260px. Main page uses a calm two-column workspace: a 280px candidate queue on the left and one large document panel on the right. Do not use a crowded three-column dashboard.
Subject: “治理技能演进” header; summary states; candidate queue; selected diagnostic-synthesis 1.3.0 Candidate; seven-stage governance pipeline; frozen Candidate/Control comparison; four Gold Cases; two Shadow Runs; governance boundaries; human promotion actions.
Text: all user-facing labels in simplified Chinese. Technical versions and hashes are allowed.
Constraints: no model leaderboard, no fake business impact, no chat, no avatar, no gradient, no dark theme, no fake live pulse, no chain-of-thought, no watermark.
```

## 移动最终 Prompt

```text
Use case: ui-mockup
Asset type: Commerce Case Agent mobile web application page, portrait high-fidelity shippable product UI
Primary request: Create the responsive mobile version of the Chinese “技能与评测” page for auditable AI-agent skill evolution. Use the same restrained light Commerce workspace style as the desktop mockup, but redesign into a true single-column mobile document flow, not a cropped desktop layout.
Composition/framing: portrait mobile, full page from top; top bar only, then normal vertical document flow; generous side padding and no horizontal overflow.
Subject: page header; 2×2 summary; one candidate selector card; candidate purpose; vertical seven-stage evolution gate; frozen experiment comparison; Gold Case chips; Shadow Run audit rows; governance boundary; normal-flow human activation actions.
Text: all user-facing labels in simplified Chinese. Technical numbers, versions, hashes and truncated Run IDs are allowed.
Constraints: no desktop sidebar; no compressed desktop columns; no chat composer; no avatar; no fake live pulse; no chain-of-thought; no gradient; no dark theme; no watermark.
```

两张图均通过内置 Image Generation 生成，没有切换 CLI 或其他图像模型。

## React 实现资产

```text
backend/app/commerce/api/skill_candidate_service.py
backend/app/commerce/api/schemas.py
backend/app/commerce/api/router.py
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/skills-evals-view-model.ts
frontend/src/components/commerce/skills-evals.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/skills-evals-api.test.ts
frontend/tests/unit/core/commerce/skills-evals-view-model.test.ts
frontend/tests/unit/components/commerce/skills-evals.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/implementation/skills-evals-react-desktop-v1.png
docs/design/commerce/implementation/skills-evals-react-mobile-v1.png
```

实现截图：

```text
docs/design/commerce/implementation/skills-evals-react-desktop-v1.png
尺寸：1536 × 1024
SHA-256：4eb71fdd9171dee4e59bfe1143c964935eebd04bfe4fe589bd182a34878117c8

docs/design/commerce/implementation/skills-evals-react-mobile-v1.png
尺寸：390 × 844
SHA-256：a76c1e14daa613676d558175c3dc7e13d1e5c68e5c8620d95db498f7e7d657b5
```

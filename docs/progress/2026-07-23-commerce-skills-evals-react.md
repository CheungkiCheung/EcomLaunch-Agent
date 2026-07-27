# Commerce 技能与评测 React 收口记录

日期：2026-07-23

## 结果

顶层“技能与评测”页面已经完成 Image-first 设计、候选评测依据后端读 API、严格前端合同、纯 View Model、React、主 Shell 导航接入、人工激活/回滚机械交互、桌面/移动截图和回归验证。

页面把“自进化”实现为受控治理流程，而不是让运行中的智能体直接修改生效 Prompt：

```text
真实失败代码
→ 不可变 Skill Candidate
→ 安全扫描
→ 冻结 Control / Candidate 实验
→ 回归与留出集
→ 无副作用 Shadow
→ 人工审查
→ Active Pointer
→ 可审计回滚
```

当前真实 `commerce-diagnostic-synthesis@1.3.0` Candidate 仍保持 `shadow`，本次开发没有替用户执行真实 Human Review，也没有修改真实 Active Pointer。

## Image-first 资产

选中的高保真视觉稿：

```text
docs/design/commerce/mockups/skills-evals-visual-v1-desktop.png
尺寸: 1536 × 1024
SHA-256: b5a8f32747b4e8b5a26c1c51634ecbca97867c32f06e149a6d0d46e574d8ab9b

docs/design/commerce/mockups/skills-evals-visual-v1-mobile.png
尺寸: 794 × 1981
SHA-256: db2e29c9a487d9f53dd7b316ac215af9ed10ab2d53d50c286786e67ec98c84a3
```

最终 React 截图：

```text
docs/design/commerce/implementation/skills-evals-react-desktop-v1.png
尺寸: 1536 × 1024
SHA-256: 4eb71fdd9171dee4e59bfe1143c964935eebd04bfe4fe589bd182a34878117c8

docs/design/commerce/implementation/skills-evals-react-mobile-v1.png
尺寸: 390 × 844
SHA-256: a76c1e14daa613676d558175c3dc7e13d1e5c68e5c8620d95db498f7e7d657b5
```

桌面采用“候选队列 + 单一治理文档”两栏；移动端使用 2×2 摘要、一个候选选择卡和纵向门禁文档流。没有常驻右侧 Inspector、固定操作底栏或 Chat Composer。

## 新后端读取合同

现有 Candidate API 可以读取候选，但不能直接恢复其冻结实验的 Control/Candidate 汇总。为了让页面真实展示 `8/8`、hard gate、令牌和延迟，本次新增：

```text
GET /api/commerce/skill-candidates/{candidate_id}/evidence
```

响应严格返回：

```text
candidate
experiment_role
definition
report
active_pointer
```

服务只从现有 immutable Experiment Registry 和 Workspace-scoped Skill Candidate Registry 读取，不复制或重算实验，不调用模型。Candidate 不存在、Experiment 文件缺失、身份不一致或 Active Pointer 损坏时返回明确的 404 / 409，不由前端补数据。

## 前端投影

页面实现了：

- Candidate List、状态筛选、中文搜索和选中 Candidate Detail；
- “未建立指针 / 当前版本 / 已回退至版本”三种 Active Pointer 边界；
- 候选提出、安全扫描、离线评测、留出集、影子运行、人工审查、生效七阶段门禁；
- 从 `source_failure_codes` 投影候选目的，不把 Candidate 英文正文直接泄露到默认中文界面；
- 从 Experiment Report 计算 Control/Candidate 的通过率、硬门禁、平均令牌、平均延迟和 Pareto 百分比；
- 从 Experiment Definition 投影四个冻结 Gold Case；
- Experiment Report 的唯一 Provider Request ID 数量；
- Candidate 当前真实 `shadow_live_run_ids`；
- Shadow 请求遥测尚无前端读 API 时明确显示“请求遥测未由当前接口开放”，不把 2 条 Run 推断成 4 个请求；
- 人工激活、稳定幂等重放、Active Pointer 重新读取；
- Active Candidate 回滚原因输入、回滚和 Pointer 重新读取；
- Actor 缺失时禁用激活/回滚，并显示“当前操作需要审查者身份”；
- 空态、错误态、移动端无横向溢出和无 Chat Composer。

## 关键实现文件

```text
backend/app/commerce/api/skill_candidate_service.py
backend/app/commerce/api/schemas.py
backend/app/commerce/api/router.py
backend/tests/commerce/api/test_skill_candidate_router.py
frontend/src/core/commerce/types.ts
frontend/src/core/commerce/api.ts
frontend/src/core/commerce/skills-evals-view-model.ts
frontend/src/core/commerce/index.ts
frontend/src/components/commerce/skills-evals.tsx
frontend/src/components/commerce/master-shell.tsx
frontend/tests/unit/core/commerce/skills-evals-fixture.ts
frontend/tests/unit/core/commerce/skills-evals-api.test.ts
frontend/tests/unit/core/commerce/skills-evals-view-model.test.ts
frontend/tests/unit/components/commerce/skills-evals.test.tsx
frontend/tests/e2e/commerce-master-shell.spec.ts
docs/design/commerce/skills-evals-visual-v1.md
```

## 验证证据

前端：

```text
pnpm exec prettier --check <Skills & Evals scoped files>
PASS

pnpm exec tsc --noEmit
PASS

pnpm exec eslint <Skills & Evals scoped files>
PASS

pnpm test -- --run
49 files / 276 tests passed

pnpm exec playwright test tests/e2e/commerce-master-shell.spec.ts
12 passed

pnpm exec next build --webpack
PASS
```

后端：

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/api/test_skill_candidate_router.py
5 passed, 1 LangChainPendingDeprecationWarning

.venv/bin/ruff check app/commerce/api/skill_candidate_service.py app/commerce/api/schemas.py app/commerce/api/router.py tests/commerce/api/test_skill_candidate_router.py
All checks passed
```

浏览器场景验证：

- “更多 → 技能与评测”拥有独立导航状态；
- Candidate `1.3.0`、`8/8`、Control `6/8`、令牌 `-12.1%`、延迟 `-26.0%` 来自严格 Mock API 的真实合同形状；
- 展开实验依据后显示 Experiment Report 的 32 个唯一请求编号；
- Shadow 只显示 2 条真实 Run 和明确的遥测未开放边界；
- 1536 × 1024 桌面和 390 × 844 移动截图通过视觉检查；
- 页面级宽度没有超过移动 viewport；
- 人工激活后 Candidate 进入 `active` 并重新读取 `1.3.0` Active Pointer；
- 填写原因后回滚，Candidate 进入 `rolled_back`，Pointer 回退至 `1.2.0`；
- 没有 Case Composer。

## 验收边界

本次 Playwright 是结构化 Mock API 机械测试，只证明前端合同、交互和响应式；它没有重新运行四 Gold Experiment 或 Shadow，也没有调用模型。

页面读取和展示的真实历史实验/Shadow 证据来自后端已持久化的 fresh DeepSeek V4 产物；本次新增的 read API 自身是确定性读取。真实 Candidate 的 Human Review/Promotion 仍需要用户明确授权，不能因为页面按钮和 Mock E2E 通过就自动执行。

## 后续

按照实施顺序，下一页进入 War Room 的 Image-first 设计。War Room 必须消费同一个真实 Domain Event Stream，并证明每个可见活动都可追溯，不能复用旧 Pixel Office 的角色动画作为运行状态。

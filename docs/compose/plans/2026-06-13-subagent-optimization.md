# EcomLaunch 多智能体优化计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按照 Anthropic "context-centric decomposition" 原则，将 5 个子代理优化为 3 个，减少协调开销

**Architecture:** 合并强依赖的 market-scout + voc-miner 为 market-voc-researcher，保留 offer-architect 和 asset-studio，evidence-checker 作为独立验证子代理

**Tech Stack:** config.yaml (YAML), TypeScript (React)

---

## 变更概览

```
变更前 (5 个子代理):
market-scout → voc-miner → offer-architect → asset-studio → evidence-checker

变更后 (3 个子代理):
market-voc-researcher → offer-architect → asset-studio
                            ↓
                      evidence-checker (验证)
```

**修改文件:**
- `config.yaml` - 子代理定义
- `frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx` - 前端面板配置
- `skills/custom/ecom-launch/SKILL.md` - 技能文档中的角色描述

---

### Task 1: 更新 config.yaml 子代理配置

**Covers:** 合并 market-scout + voc-miner → market-voc-researcher

**Files:**
- Modify: `config.yaml:166-253` (替换 market-scout 和 voc-miner)

- [ ] **Step 1: 删除旧的 market-scout 和 voc-miner 配置**

删除 `config.yaml` 中 `custom_agents` 下的 `market-scout` 和 `voc-miner` 条目（第 167-253 行）

- [ ] **Step 2: 添加新的 market-voc-researcher 配置**

在 `custom_agents` 下添加：

```yaml
    market-voc-researcher:
      description: Research public market signals, competitors, pricing, and mine
        customer voice, reviews, pain points from public sources
      system_prompt: 'You are `market-voc-researcher`, an ecommerce market and customer-voice
        researcher for EcomLaunch.

        You combine two roles in one context to avoid information loss between handoffs:

        1. MARKET RESEARCH: Find competitors, substitutes, price bands, product claims,
        category trends, and visible platform/content patterns.

        2. CUSTOMER VOICE: Analyze public reviews, Q&A, social posts, forum discussions,
        and uploaded review files. Cluster complaints, praise, usage scenarios, objections,
        and exact customer wording.

        Use public web information and uploaded files only.

        Run budget: use at most 8 web_search calls and 8 web_fetch calls combined
        for both market and VOC research. If sources are thin, blocked, or rate-limited,
        stop and record the limitation.

        Do not write final deliverable files. Return concise structured findings
        to the launch-director.

        Never invent private merchant metrics such as GMV, CTR, CVR, ROI, or ad spend.
        If the user has no backend data, mention private platform metrics only as unavailable,
        uploaded evidence, or future metrics to collect after platform access exists.

        Return structured findings for the launch-director, not final user-facing
        prose. Include:

        MARKET FINDINGS:
        - top public market patterns
        - competitor/substitute list
        - visible price bands
        - recurring claims and category promises
        - visible content/platform patterns

        VOC FINDINGS:
        - pain-point clusters
        - positive triggers
        - purchase objections
        - usage scenarios
        - exact customer wording when available

        EVIDENCE:
        - source list with evidence_type, source_type, confidence, and limitations

        If data is thin or blocked, say so. Do not infer exact sales or market share.
        Do not invent reviews. If direct customer voice is unavailable, say so.

        '
      tools:
      - web_search
      - web_fetch
      - image_search
      - read_file
      skills:
      - ecom-launch
      model: inherit
      max_turns: 60
      timeout_seconds: 480
```

- [ ] **Step 3: 验证配置格式**

Run: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
Expected: 无错误输出

- [ ] **Step 4: Commit**

```bash
git add config.yaml
git commit -m "refactor: merge market-scout + voc-miner into market-voc-researcher

Apply context-centric decomposition principle from Anthropic's multi-agent guide.
Market signals and customer voice are tightly coupled sequential work - merging
them reduces coordination overhead and information loss between handoffs."
```

---

### Task 2: 更新 offer-architect prompt 引用

**Covers:** 更新 offer-architect 对前序子代理的引用

**Files:**
- Modify: `config.yaml:254-300` (offer-architect system_prompt)

- [ ] **Step 1: 修改 offer-architect 的 system_prompt**

将第 265 行的：
```
Prefer synthesis from market-scout and voc-miner.
```

改为：
```
Prefer synthesis from market-voc-researcher.
```

- [ ] **Step 2: 验证配置格式**

Run: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
Expected: 无错误输出

- [ ] **Step 3: Commit**

```bash
git add config.yaml
git commit -m "fix: update offer-architect prompt to reference merged researcher"
```

---

### Task 3: 更新前端 Launch Crew 面板

**Cographs:** 前端可视化适配新的 3 子代理架构

**Files:**
- Modify: `frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx:38-118` (ROLE_CONFIGS)
- Modify: `frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx:120-130` (ARTIFACT_TO_ROLE)

- [ ] **Step 1: 更新 LaunchCrewRole 类型定义**

将第 38-44 行的类型：
```typescript
type LaunchCrewRole =
  | "market-scout"
  | "voc-miner"
  | "offer-architect"
  | "asset-studio"
  | "evidence-checker";
```

改为：
```typescript
type LaunchCrewRole =
  | "market-voc-researcher"
  | "offer-architect"
  | "asset-studio"
  | "evidence-checker";
```

- [ ] **Step 2: 更新 ROLE_CONFIGS 数组**

将第 82-118 行的 ROLE_CONFIGS：
```typescript
const ROLE_CONFIGS: LaunchCrewRoleConfig[] = [
  {
    id: "market-scout",
    name: "Market Scout",
    desk: "公开市场侦察",
    accent: "bg-cyan-500",
    icon: SearchIcon,
  },
  {
    id: "voc-miner",
    name: "VOC Miner",
    desk: "用户声音采矿",
    accent: "bg-amber-500",
    icon: BotIcon,
  },
  {
    id: "offer-architect",
    name: "Offer Architect",
    desk: "定位与验证设计",
    accent: "bg-emerald-500",
    icon: SparklesIcon,
  },
  {
    id: "asset-studio",
    name: "Asset Studio",
    desk: "内容资产工坊",
    accent: "bg-fuchsia-500",
    icon: FileTextIcon,
  },
  {
    id: "evidence-checker",
    name: "Evidence Checker",
    desk: "证据与口径审计",
    accent: "bg-sky-600",
    icon: ShieldCheckIcon,
  },
];
```

改为：
```typescript
const ROLE_CONFIGS: LaunchCrewRoleConfig[] = [
  {
    id: "market-voc-researcher",
    name: "Market & VOC Researcher",
    desk: "市场与用户研究",
    accent: "bg-cyan-500",
    icon: SearchIcon,
  },
  {
    id: "offer-architect",
    name: "Offer Architect",
    desk: "定位与验证设计",
    accent: "bg-emerald-500",
    icon: SparklesIcon,
  },
  {
    id: "asset-studio",
    name: "Asset Studio",
    desk: "内容资产工坊",
    accent: "bg-fuchsia-500",
    icon: FileTextIcon,
  },
  {
    id: "evidence-checker",
    name: "Evidence Checker",
    desk: "证据与口径审计",
    accent: "bg-sky-600",
    icon: ShieldCheckIcon,
  },
];
```

- [ ] **Step 3: 更新 ARTIFACT_TO_ROLE 映射**

将第 120-130 行：
```typescript
const ARTIFACT_TO_ROLE: Array<[string, LaunchCrewRole]> = [
  ["competitor-table.csv", "market-scout"],
  ["source-list.md", "market-scout"],
  ["review-insights.json", "voc-miner"],
  ["positioning-brief.md", "offer-architect"],
  ["launch-calendar.csv", "offer-architect"],
  ["listing-pack.md", "asset-studio"],
  ["content-pack.md", "asset-studio"],
  ["evidence-ledger.json", "evidence-checker"],
  ["launch-war-room.html", "evidence-checker"],
];
```

改为：
```typescript
const ARTIFACT_TO_ROLE: Array<[string, LaunchCrewRole]> = [
  ["competitor-table.csv", "market-voc-researcher"],
  ["source-list.md", "market-voc-researcher"],
  ["review-insights.json", "market-voc-researcher"],
  ["positioning-brief.md", "offer-architect"],
  ["launch-calendar.csv", "offer-architect"],
  ["listing-pack.md", "asset-studio"],
  ["content-pack.md", "asset-studio"],
  ["evidence-ledger.json", "evidence-checker"],
  ["launch-war-room.html", "evidence-checker"],
];
```

- [ ] **Step 4: 更新 WORKFLOW_STAGES 中的 matchers**

将第 158 行的 VOC stage matchers：
```typescript
  {
    id: "voc",
    label: "用户",
    matchers: ["voc", "customer", "review", "voice", "用户", "评论", "痛点"],
    artifactNames: ["review-insights.json"],
  },
```

改为：
```typescript
  {
    id: "research",
    label: "研究",
    matchers: ["market", "voc", "research", "signal", "customer", "review", "市场", "用户", "研究"],
    artifactNames: ["competitor-table.csv", "review-insights.json"],
  },
```

- [ ] **Step 5: 验证 TypeScript 编译**

Run: `cd frontend && pnpm typecheck`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx
git commit -m "refactor: update Launch Crew panel for 3-subagent architecture

Replace market-scout + voc-miner with merged market-voc-researcher role.
Update artifact mappings and workflow stage matchers."
```

---

### Task 4: 更新技能文档

**Covers:** 更新 ecom-launch skill 中的角色描述

**Files:**
- Modify: `skills/custom/ecom-launch/SKILL.md:348-388` (Lead Agent Role 和 Specialist Output Contracts)

- [ ] **Step 1: 更新 Lead Agent Role 部分**

在 `skills/custom/ecom-launch/SKILL.md` 中找到 `## Lead Agent Role` 部分，更新推荐子代理列表：

将：
```
Recommended subagents:

- `market-scout`: public market, competitor, price, claim, and content-pattern scan
- `voc-miner`: review/VOC pain points, praise, purchase objections, usage scenarios, customer wording
- `offer-architect`: segment, job-to-be-done, core promise, differentiators, risks, launch hypotheses, 7-day test plan
- `asset-studio`: title, bullets, detail page, FAQ, short-video scripts, livestream talk tracks, social posts, creator brief
- `evidence-checker`: final evidence audit and unsupported-claim cleanup
```

改为：
```
Recommended subagents:

- `market-voc-researcher`: combined market signals, competitors, pricing, and customer voice/VOC analysis
- `offer-architect`: segment, job-to-be-done, core promise, differentiators, risks, launch hypotheses, 7-day test plan
- `asset-studio`: title, bullets, detail page, FAQ, short-video scripts, livestream talk tracks, social posts, creator brief
- `evidence-checker`: final evidence audit and unsupported-claim cleanup
```

- [ ] **Step 2: 更新 Specialist Output Contracts 部分**

找到 `### market-scout` 和 `### voc-miner` 两个小节，合并为一个 `### market-voc-researcher`：

```markdown
#### market-voc-researcher

Return both market and VOC findings in a single structured response:

MARKET FINDINGS:
- top public market patterns
- competitor/substitute list
- visible price bands
- recurring claims and category promises
- visible content/platform patterns
- source list with evidence_type, source_type, confidence, and limitations

VOC FINDINGS:
- pain-point clusters
- positive triggers
- purchase objections
- usage scenarios
- exact customer wording when available
- VOC evidence map with confidence and limitations

Do not invent exact sales or market share. Do not invent reviews. If direct customer
voice is unavailable, say so and use adjacent public signals cautiously.
```

- [ ] **Step 3: 更新搜索预算说明**

找到 `### 3.1 Run Budget And Search Discipline` 部分，更新预算：

将：
```
market-scout: up to 5 web_search calls and 5 web_fetch calls
voc-miner: up to 4 web_search calls and 4 web_fetch calls
```

改为：
```
market-voc-researcher: up to 8 web_search calls and 8 web_fetch calls (combined market + VOC)
```

- [ ] **Step 4: Commit**

```bash
git add skills/custom/ecom-launch/SKILL.md
git commit -m "docs: update ecom-launch skill for merged market-voc-researcher role"
```

---

### Task 5: 验证整体功能

**Covers:** 确保所有修改协同工作

**Files:** 无新增修改

- [ ] **Step 1: 验证 config.yaml 格式**

Run: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
Expected: 无错误

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `cd frontend && pnpm typecheck`
Expected: 无错误

- [ ] **Step 3: 运行前端 lint**

Run: `cd frontend && pnpm lint`
Expected: 无错误

- [ ] **Step 4: 运行后端测试**

Run: `cd backend && make test`
Expected: 测试通过

---

## 执行方式选择

完成后询问用户执行方式：
- **Subagent**: 每个 Task 使用独立子代理
- **Inline**: 在当前会话中顺序执行

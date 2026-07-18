# Growth Experiment Engine — 定位扩展

> Archived historical plan. This document records the earlier openGrowth / Launch Validation Pack direction and is not the current product positioning. Current public positioning is **OpenSKU: Adaptive SKU Launch Loop**. Use `README.md`, `docs/ecom-launch/README.md`, and `docs/plans/ecom-launch-agent-spec.md` as the source of truth.

> **For agentic workers:** USE superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 EcomLaunch 从"一次性上线前验证引擎"扩展为"增长实验全生命周期引擎"，覆盖 validate-launch + calibrate-content 两个标准化 workflow，吸收 cheat-on-content 的实验校准方法论。

**Architecture:** 不改动 Orchstrator-subagent 架构。新增 1 个 skill（content-calibration），扩展 asset-studio + evidence-checker 的职责边界，更新文档定位。前后端代码零改动。

**Tech Stack:** 不变 — Python 3.12+ / Next.js 19 / LangGraph / Tailwind CSS 4

## Global Constraints

- 所有改动限于 `skills/custom/`、`agents/`、`config.yaml`、文档文件，不动后端/前端业务代码
- 新 skill 遵循 DeerFlow skill 格式（YAML frontmatter + Markdown body）
- 所有 subagent prompt 必须保留现有的 evidence labeling rules 和 forbidden metrics
- 中文用户界面文案，英文文件名和 JSON key
- content-calibration skill 不引入新工具依赖，复用现有 web_search / web_fetch / read_file / write_file

---

### Task 1: 创建 content-calibration skill

**Files:**
- Create: `skills/custom/content-calibration/SKILL.md`

**Interfaces:**
- Consumes: 无（独立 skill）
- Produces: `content-calibration` skill，供 asset-studio 和 evidence-checker 加载

- [ ] **Step 1: 创建 skill 文件**

```markdown
---
name: content-calibration
description: Score-breakdown, blind performance prediction, post-publish retrospective, and scoring-rubric evolution for ecommerce content assets (titles, short-video scripts, listing copy, social posts).
allowed-tools:
  - read_file
  - write_file
  - grep
  - glob
  - web_search
  - web_fetch
  - ask_clarification
---

# Content Calibration

Use this skill when the user needs to:
- score ecommerce content before publishing
- blind-predict expected performance of titles, scripts, or listing copy
- do a post-publish retrospective on content data
- evolve a scoring rubric based on accumulated retro records

This skill does NOT search for new public data. It operates on existing content assets and performance data.

## Core Loop

The content calibration loop turns every content piece into a calibrated experiment:

```
Score → Blind-Predict → Ship → T+3d Retro → Evolve Rubric → Next Score
```

Every piece that ships without retro silently erodes judgment accuracy. Every piece logged with Score → Prediction → Retro compounds into a personal hit formula.

## When To Use

Trigger this skill when the user asks to:
- "score this script"
- "predict how this listing will perform"
- "review this content's performance data"
- "improve my content scoring rubric"
- "which variant should I ship first"
- "what did we learn from last week's content"

## Mode Adaptation

### Flash Mode (闪速)
- Score a single content piece against the current rubric
- Output: scorecard with dimension scores and one-sentence verdict

### Thinking Mode (思考)
- Score + blind-predict for one piece
- Output: full scorecard + prediction with confidence intervals

### Pro Mode (专业)
- Score + blind-predict + T+N retro on one or more pieces
- Output: scorecard set + retro table + rubric adjustment suggestions

### Ultra Mode (极致) - DEFAULT
- Full cycle on a batch: re-score history with proposed rubric change → blind-predict new content → retro published content → evolve rubric → present updated formula
- Output: updated rubric file + calibration ledger

## Scoring Dimensions

Default scoring dimensions for ecommerce content. These evolve based on retro data — the starting rubric is a template, not dogma.

For **listing titles**:

| Dimension | Weight | What to score (1-10) |
|-----------|--------|---------------------|
| hook_clarity | 0.25 | Does the reader understand the product in 2 seconds? |
| pain_address | 0.20 | Does it name the customer's actual pain point? |
| differentiation | 0.20 | Is there a clear reason to pick this over competitors? |
| search_visibility | 0.15 | Does it contain the keywords buyers actually search? |
| emotion_trigger | 0.10 | Does it create urgency, curiosity, or desire? |
| readability | 0.10 | Is it scannable on mobile in < 3 seconds? |

For **short-video scripts**:

| Dimension | Weight | What to score (1-10) |
|-----------|--------|---------------------|
| hook_strength_3s | 0.30 | Does the first 3 seconds stop the scroll? |
| pain_demonstration | 0.20 | Is the problem shown visually, not just stated? |
| solution_clarity | 0.20 | Is the product's fix obvious and believable? |
| objection_preemption | 0.15 | Does it answer the top objection before it forms? |
| share_trigger | 0.10 | Would someone send this to a friend? |
| cta_clarity | 0.05 | Is the next action unmistakable? |

For **listing detail-page modules**:

| Dimension | Weight | What to score (1-10) |
|-----------|--------|---------------------|
| trust_building | 0.25 | Do specs, images, and proof reduce purchase anxiety? |
| objection_coverage | 0.20 | Are the top 3 purchase objections addressed? |
| scan_pattern | 0.15 | Does the layout match how buyers actually scan? |
| spec_completeness | 0.15 | Are missing specs clearly marked, not hidden? |
| social_proof_placement | 0.15 | Is proof placed where hesitation peaks? |
| mobile_readability | 0.10 | Does it work on a phone with one thumb? |

## Blind Prediction Contract

Before publishing, for each content piece, record:

```json
{
  "content_id": "variant-a-leakproof-title-v1",
  "content_type": "listing_title",
  "scored_at": "2026-06-17",
  "scores": {
    "hook_clarity": 7,
    "pain_address": 8,
    "differentiation": 5,
    "search_visibility": 6,
    "emotion_trigger": 7,
    "readability": 8
  },
  "weighted_score": 6.7,
  "blind_prediction": {
    "expected_performance": "above_baseline",
    "confidence": "medium",
    "win_probability_vs_control": 0.60,
    "key_risk": "differentiation is weak — competitors may already use similar phrasing",
    "expected_signal": "CTR above category average, but conversion may lag if listing detail page doesn't support the title promise"
  }
}
```

Performance tier labels:
- `well_above_baseline` — likely top 10%
- `above_baseline` — likely top 30%
- `baseline` — average
- `below_baseline` — likely bottom 30%
- `well_below_baseline` — likely bottom 10%

Confidence levels:
- `high` — strong pattern match with ≥3 similar past pieces
- `medium` — partial pattern match, 1-2 similar past pieces
- `low` — new content type or audience, no similar history
- `unknown` — first piece in this category

## Retrospective Contract

T+N days after publish (default N=3), for each content piece that shipped:

```json
{
  "content_id": "variant-a-leakproof-title-v1",
  "retro_at": "2026-06-20",
  "actual_performance": "above_baseline",
  "was_prediction_correct": true,
  "actual_signals": {
    "ctr_vs_category": "+12%",
    "conversion_vs_control": "+3%",
    "comment_sentiment": "mostly_positive",
    "share_count": 14,
    "top_objection_in_comments": "price_concern"
  },
  "dimension_calibration": {
    "hook_clarity": {"predicted": 7, "actual_evidence": "matches", "adjustment": 0},
    "differentiation": {"predicted": 5, "actual_evidence": "underestimated", "adjustment": "+1"},
    "pain_address": {"predicted": 8, "actual_evidence": "matches", "adjustment": 0}
  },
  "learnings": [
    "Differentiation actually stronger than predicted — the leak-proof angle was more unique than expected",
    "Price concern emerged as top objection — add value justification to next iteration"
  ],
  "rubric_adjustments": {
    "differentiation_weight": {"from": 0.20, "to": 0.25, "reason": "Retro data shows differentiation has outsized impact on CTR in this category"}
  }
}
```

Dimension calibration labels:
- `matches` — prediction within ±1 of actual evidence
- `overestimated` — predicted higher than evidence supports
- `underestimated` — predicted lower than evidence supports

## Rubric Evolution Rules

### When to evolve

Trigger a rubric review when:
1. Three consecutive same-direction misses on the same dimension → suggest weight adjustment
2. A dimension consistently shows zero predictive power (random correlation with outcomes) → suggest removal or merge
3. New public evidence reveals a dimension the rubric doesn't capture → suggest addition

### Evolution safety brake

When proposing a rubric change:
1. Re-score all historical pieces with the proposed rubric
2. Compare ranking accuracy vs the current rubric
3. Only accept if the new rubric ranks historical pieces more accurately
4. Mark the change as `pending_validation` until confirmed by ≥3 new pieces

### Rubric versioning

Keep a rubric changelog:

```markdown
## Rubric Changelog

### v1.1 (2026-06-17)
- differentiation_weight: 0.20 → 0.25
- Reason: 3 of 4 retro cases showed differentiation underestimated
- Validation: re-scored 8 historical pieces; rank correlation improved from 0.72 to 0.81

### v1.0 (2026-06-10)
- Initial rubric based on category defaults
```

## Artifact Contracts

### calibration-ledger.json

```json
[
  {
    "content_id": "variant-a-leakproof-title-v1",
    "content_type": "listing_title",
    "scored_at": "2026-06-17",
    "shipped_at": "2026-06-17",
    "retro_at": null,
    "weighted_score": 6.7,
    "predicted_performance": "above_baseline",
    "prediction_confidence": "medium",
    "actual_performance": null,
    "prediction_correct": null,
    "learnings": null
  }
]
```

### rubric.md

```markdown
# Content Scoring Rubric

**Version:** 1.0
**Last updated:** 2026-06-10
**Category:** portable-coffee-tumbler

## Listing Title Rubric

| Dimension | Weight | Score 1-3 | Score 4-6 | Score 7-9 | Score 10 |
|-----------|--------|-----------|-----------|-----------|----------|
| hook_clarity | 0.25 | Reader confused about product | Product mentioned but vague | Product clear, use case implied | Product + use case instantly clear |
...
```

## Data Boundary

- Use only content assets and performance data the user provides.
- Do not invent CTR, CVR, view count, share count, or any performance metric.
- If performance data is unavailable, mark the retro as `pending_data` rather than fabricating numbers.
- Rubric evolution suggestions must be labeled as estimates until validated with ≥3 retro records.
- Never present a suggested rubric weight change as confirmed without retro evidence.

## Evidence Types

Same labeling scheme as ecom-launch skill:

- `observed_public` — public performance data or benchmarks
- `uploaded_real` — user-uploaded content performance data
- `estimated` — reasoned estimate from patterns
- `unavailable` — data cannot be known

## Final Response

After completing calibration work:
1. Summarize top calibration findings
2. Note rubric changes made or suggested
3. List updated artifacts
4. Recommend next calibration checkpoint

Do not paste raw JSON or full rubric tables into chat. Present files.
```

- [ ] **Step 2: 验证文件存在**

Run: `ls -la "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/skills/custom/content-calibration/SKILL.md"`
Expected: 文件存在

- [ ] **Step 3: Commit**

```bash
git add skills/custom/content-calibration/SKILL.md
git commit -m "feat: add content-calibration skill with Score→Predict→Retro→Evolve loop"
```

---

### Task 2: 更新 EcomLaunch Agent SOUL.md

**Files:**
- Modify: `agents/ecom-launch/SOUL.md`

**Interfaces:**
- Consumes: 无
- Produces: 更新的 agent identity 和 workflow 入口

- [ ] **Step 1: 替换项目定位段落**

将 SOUL.md 第 3-7 行：

```
You are EcomLaunch, a conversational ecommerce new-product launch copilot built on DeerFlow.

Your job is to help the user turn a rough product idea, category, public product link, screenshot, or uploaded product material into a 7-day Launch Validation Pack using public evidence, user-provided context, and clearly labeled assumptions.

You are not a generic research assistant. You are the user's launch-director for ecommerce new-product validation.
```

替换为：

```
You are EcomLaunch, a conversational ecommerce growth experiment copilot built on DeerFlow.

Your job is to help the user turn a rough product idea into a calibrated growth system — from pre-launch validation through content experimentation and performance calibration — using public evidence, user-provided data, and clearly labeled assumptions.

You are not a generic research assistant. You are the user's growth director for ecommerce experimentation.
```

- [ ] **Step 2: 更新 Product Promise 段落**

将 SOUL.md 第 11-20 行的 Product Promise 替换为：

```
## Product Promise

Help the user:

- decide whether a product is worth a small launch test
- choose which audience wedge to start with
- design which offer promise to test first
- create listing and content assets ready to ship
- score content before publishing and predict performance
- run post-publish retrospectives to calibrate judgment
- evolve a personal scoring formula that compounds over time

The flagship workflows are:

```text
validate-launch  -> Launch Validation Pack (7 artifacts)
calibrate-content -> Content Calibration Pack (Score → Predict → Retro → Evolve)
```
```

- [ ] **Step 3: 更新 Required Deliverables 段落**

在 SOUL.md 的 Required Deliverables 段落后，添加 calibrate-content 的产出物列表：

````markdown
For `calibrate-content` runs, create and present:

```text
calibration-ledger.json
rubric.md
content-scorecard.md
```

Optional:

```text
retro-summary.md
rubric-changelog.md
```
````

- [ ] **Step 4: 更新 Final User Response 段落**

将 SOUL.md 第 161-170 行的 Final User Response 替换为：

```
## Final User Response

After presenting files, respond briefly in the user's language:

1. For validate-launch: recommended launch direction, key audience wedge or offer angle, note that private merchant metrics were unavailable if applicable, list the presented artifacts
2. For calibrate-content: top calibration findings, rubric changes made or suggested, recommended next calibration checkpoint, list the presented artifacts

Do not paste the full artifact contents into chat.
```

- [ ] **Step 5: Commit**

```bash
git add agents/ecom-launch/SOUL.md
git commit -m "feat: expand EcomLaunch identity to growth experiment engine, add calibrate-content workflow"
```

---

### Task 3: 更新 EcomLaunch Agent config.yaml

**Files:**
- Modify: `agents/ecom-launch/config.yaml`

**Interfaces:**
- Consumes: content-calibration skill (Task 1)
- Produces: 技能列表包含 content-calibration

- [ ] **Step 1: 添加 content-calibration 到技能列表**

将 `agents/ecom-launch/config.yaml` 的 skills 段从：

```yaml
skills:
  - ecom-launch
```

改为：

```yaml
skills:
  - ecom-launch
  - content-calibration
```

- [ ] **Step 2: Commit**

```bash
git add agents/ecom-launch/config.yaml
git commit -m "feat: add content-calibration to EcomLaunch agent skills"
```

---

### Task 4: 更新 ecom-launch SKILL.md — 添加 calibrate-content workflow

**Files:**
- Modify: `skills/custom/ecom-launch/SKILL.md`

**Interfaces:**
- Consumes: content-calibration skill (Task 1)
- Produces: 添加 calibrate-content workflow 交叉引用

- [ ] **Step 1: 在 Trigger 段末尾添加 calibrate-content 触发条件**

在 SKILL.md 第 103 行后（`validate-launch` trigger 段落之后），插入：

```markdown
Run the `calibrate-content` workflow when the user asks to:

- score or grade ecommerce content before publishing
- predict which title, script, or listing variant will perform better
- review content performance data and extract learnings
- improve or evolve a content scoring rubric
- run a post-publish retrospective
- decide which content variant to ship first

For content calibration tasks, delegate to the `content-calibration` skill. The `asset-studio` subagent handles content scoring and prediction; `evidence-checker` handles retro analysis and rubric auditing.
```

- [ ] **Step 2: 在 subagent 角色描述中添加校准职责**

在 SKILL.md 的 subagent 描述段落（第 386 行附近），将 `asset-studio` 的输出契约扩展为：

在 asset-studio 的 "Return:" 块末尾，添加：

```markdown
When the workflow is `calibrate-content` rather than `validate-launch`, asset-studio also returns:
- content scorecard with dimension scores and weighted total
- blind performance prediction with confidence level
- key risk and upside factors for each content piece
```

- [ ] **Step 3: 在 evidence-checker 输出契约中添加校准职责**

在 evidence-checker 的 "Return:" 块末尾，添加：

```markdown
When the workflow is `calibrate-content`, evidence-checker also returns:
- retro analysis comparing prediction vs actual performance
- dimension-level calibration (overestimated / matches / underestimated)
- rubric evolution suggestions with safety-brake validation
- updated calibration-ledger.json entries
```

- [ ] **Step 4: Commit**

```bash
git add skills/custom/ecom-launch/SKILL.md
git commit -m "feat: add calibrate-content workflow triggers and subagent calibration contracts"
```

---

### Task 5: 更新 config.yaml — 扩展 asset-studio 和 evidence-checker 的 system prompt

**Files:**
- Modify: `config.yaml`（第 310-350 行 asset-studio 段，第 354-395 行 evidence-checker 段）

**Interfaces:**
- Consumes: content-calibration skill (Task 1), 更新的 ecom-launch SKILL.md (Task 4)
- Produces: 子 agent prompt 覆盖校准场景

- [ ] **Step 1: 扩展 asset-studio system_prompt**

将 asset-studio 的 description 从：

```yaml
description: Create ecommerce listing copy, content hooks, short-video scripts,
  live-commerce talk tracks, and creator briefs
```

改为：

```yaml
description: Create ecommerce listing copy, content hooks, short-video scripts,
  live-commerce talk tracks, creator briefs, and content scoring with blind
  performance prediction
```

在 asset-studio 的 system_prompt 末尾（`Every strong claim must trace back to evidence or be labeled as an assumption.` 之后），添加：

```
When the workflow is calibrate-content, also:
- Score each content piece against the active rubric dimensions.
- Record a blind performance prediction with confidence level for each piece.
- Note key risks that may invalidate the prediction.
- Do not invent performance data. Score and predict based on content
  structure and public category patterns only.
```

在 asset-studio 的 skills 列表中添加 content-calibration：

```yaml
skills:
- ecom-launch
- content-calibration
```

- [ ] **Step 2: 扩展 evidence-checker system_prompt**

将 evidence-checker 的 description 从：

```yaml
description: Audit ecommerce recommendations for evidence quality and unsupported
  private metric claims
```

改为：

```yaml
description: Audit ecommerce recommendations for evidence quality, unsupported
  private metric claims, and post-publish content performance calibration
```

在 evidence-checker 的 system_prompt 中，Return 段落的末尾添加：

```
When the workflow is calibrate-content, also:
- Compare blind predictions against actual performance data the user provides.
- Flag dimensions where prediction was consistently over or under.
- Suggest rubric weight adjustments only when ≥3 retro records support them.
- Validate proposed rubric changes with re-scoring of historical pieces.
- Add retro entries to calibration-ledger.json.
- Never invent performance data. If actuals are missing, mark retro as pending_data.
```

在 evidence-checker 的 skills 列表中添加 content-calibration：

```yaml
skills:
- ecom-launch
- ab-test-analysis
- cohort-analysis
- content-calibration
```

- [ ] **Step 3: Commit**

```bash
git add config.yaml
git commit -m "feat: extend asset-studio and evidence-checker prompts for content calibration workflow"
```

---

### Task 6: 更新 README.md 和 README_zh.md

**Files:**
- Modify: `README.md`
- Modify: `README_zh.md`

**Interfaces:**
- Consumes: 新的产品定位
- Produces: 反映新定位的 README

- [ ] **Step 1: 更新 README.md 标题和简介**

将 README.md 第 1-7 行：

```
# openGrowth

> AI多Agent增长引擎 - 从公开信号自动生成增长验证包
```

替换为：

```
# openGrowth

> AI增长实验引擎 — 从公开信号到校准决策，建立你自己的判断公式
```

- [ ] **Step 2: 更新核心特性列表**

将 README.md 的第 15-19 行：

```
- **多Agent协作** - 5个专业Agent并行工作
- **证据驱动** - 基于公开信号，非主观判断
- **游戏化界面** - 像素艺术办公室
- **渐进式模式** - Flash/Thinking/Pro/Ultra 4种模式
- **7件套产出物** - 完整的增长验证包
```

替换为：

```
- **多Agent协作** - 5个专业Agent并行工作
- **证据驱动** - 基于公开信号，非主观判断
- **实验校准** - Score → Predict → Retro → Evolve 闭环
- **游戏化界面** - 像素艺术办公室
- **渐进式模式** - Flash/Thinking/Pro/Ultra 4种模式
- **两大工作流** - validate-launch + calibrate-content
```

- [ ] **Step 3: 更新架构图标题和使用场景**

在 README.md 架构图下方添加 calibrate-content 工作流简述。在使用场景段落末尾添加场景4：

```
### 场景4：卖家校准内容表现

用户：帮我回顾上周发的5条短视频脚本，看看哪些预测准、哪些翻车了
系统：对比blind prediction vs 实际数据，输出校准账本
输出：calibration-ledger.json + 更新后的评分公式
```

- [ ] **Step 4: 更新 README_zh.md**

在 README_zh.md 的"从 Deep Research 到 Super Agent Harness"段落（第 408 行附近），将 DeerFlow 被扩展的用途描述更新，或者在最前面添加一段说明本项目在 DeerFlow 基础上的延伸定位。

在 README_zh.md 的"核心特性"段落（第 420 行附近），添加实验校准相关特性说明。

- [ ] **Step 5: Commit**

```bash
git add README.md README_zh.md
git commit -m "docs: update README for growth experiment engine positioning"
```

---

### Task 7: 更新 AGENTS.md

**Files:**
- Modify: `AGENTS.md`（deer-flow 根目录的）
- Modify: `deer-flow/AGENTS.md`

**Interfaces:**
- Consumes: 新的产品定位
- Produces: 反映新定位的 AGENTS.md

- [ ] **Step 1: 更新 Project Identity**

将 `deer-flow/AGENTS.md` 的 Project Identity 段从：

```
DeerFlow 2.0 is a LangGraph-based AI super agent harness. This repo has been forked and extended with **EcomLaunch Agent** — a vertical ecommerce new-product launch validation product.
```

改为：

```
DeerFlow 2.0 is a LangGraph-based AI super agent harness. This repo has been forked and extended with **EcomLaunch Agent** — a vertical ecommerce growth experiment engine covering pre-launch validation and post-launch content calibration.
```

- [ ] **Step 2: 更新 Architecture 关键目录说明**

在 `deer-flow/AGENTS.md` 的架构目录段中，将 custom skills 描述从：

```
│   └── custom/ecom-launch/     # EcomLaunch skill (827 lines)
```

改为：

```
│   └── custom/
│       ├── ecom-launch/         # EcomLaunch skill (validate-launch workflow)
│       └── content-calibration/ # Content calibration skill (calibrate-content workflow)
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md deer-flow/AGENTS.md
git commit -m "docs: update AGENTS.md for growth experiment engine identity"
```

---

### Task 8: 更新前端 PixelOffice — 添加校准阶段

**Files:**
- Modify: `frontend/src/components/workspace/ecom-launch/pixel-office.tsx`

**Interfaces:**
- Consumes: 无新增接口
- Produces: 白板任务列表包含"内容校准"

- [ ] **Step 1: 在白板任务列表中添加"内容校准"**

将 pixel-office.tsx 第 147 行的任务列表从：

```tsx
{["需求澄清", "市场研究", "增长策略", "内容创作", "数据分析", "证据审计"].map(
```

改为：

```tsx
{["需求澄清", "市场研究", "增长策略", "内容创作", "数据分析", "证据审计", "内容校准"].map(
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workspace/ecom-launch/pixel-office.tsx
git commit -m "feat: add content calibration stage to pixel office whiteboard"
```

---

### Task 9: 更新前端 LaunchCrewPanel — 添加校准 workflow stages

**Files:**
- Modify: `frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx`

**Interfaces:**
- Consumes: 无新增接口
- Produces: WORKFLOW_STAGES 包含校准阶段

- [ ] **Step 1: 在 WORKFLOW_STAGES 中添加 calibration stage**

在 launch-crew-panel.tsx 第 134-202 行的 WORKFLOW_STAGES 数组中，在 `audit` stage 之后、"pack" stage 之前，插入：

```tsx
  {
    id: "calibrate",
    label: "校准",
    matchers: [
      "calibrate",
      "score",
      "predict",
      "retro",
      "rubric",
      "校准",
      "评分",
      "回顾",
      "预测",
    ],
    artifactNames: ["calibration-ledger.json", "rubric.md"],
  },
```

同时将 workflowStages 的 grid 从 `grid-cols-4` 改为 `grid-cols-5`（或更好：调整为两行布局），因为现在有 8 个 stage 了（原来是 7 个）。

在第 609 行附近，将：

```tsx
<div className="grid grid-cols-4 gap-1">
```

改为：

```tsx
<div className="grid grid-cols-4 gap-1">
```

保持 grid-cols-4，让 8 个 stage 自动换行成两行展示。

- [ ] **Step 2: 在 ROLE_CONFIGS 中确保 evidence-checker 的 desk 描述覆盖校准职责**

ROLE_CONFIGS 中 evidence-checker 的 desk 已经是 `"证据与口径审计"`，可以保持。但 asset-studio 的 desk 可以考虑扩展。

将 asset-studio 的 desk 从 `"内容资产工坊"` 改为 `"内容资产与校准"`：

```tsx
  {
    id: "asset-studio",
    name: "Asset Studio",
    desk: "内容资产与校准",
    accent: "bg-fuchsia-500",
    icon: FileTextIcon,
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workspace/ecom-launch/launch-crew-panel.tsx
git commit -m "feat: add calibration workflow stage to launch crew panel"
```

---

### Task 10: 验证 — 跑 lint 和 typecheck

**Files:**
- 无新文件

- [ ] **Step 1: 前端 typecheck**

```bash
cd /Users/zhangqixiang/0_2实习/deepagents/deer-flow/frontend && pnpm typecheck
```
Expected: 无类型错误

- [ ] **Step 2: 后端 lint**

```bash
cd /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend && make lint
```
Expected: 无 lint 错误（ruff 通过）

- [ ] **Step 3: 前端 lint**

```bash
cd /Users/zhangqixiang/0_2实习/deepagents/deer-flow/frontend && pnpm lint
```
Expected: 无 lint 错误

- [ ] **Step 4: 最终 commit（如有修正）**

```bash
git add -A && git commit -m "chore: lint and typecheck fixes"
```

# EcomLaunch Agent Spec

## 1. Product Thesis

EcomLaunch Agent is a vertical ecommerce new-product launch validation product built on DeerFlow's mature agent runtime.

It is not a generic competitor-analysis wrapper and it is not a full-platform crawler. Its core job is:

```text
Turn a rough ecommerce product idea, category, product link, or uploaded material
into a 7-day Launch Validation Pack using public signals, user-provided context,
clearly labeled assumptions, and evidence-aware outputs.
```

The product should be explainable as:

```text
Public-signal ecommerce launch validation agent.
Built on DeerFlow's Lead Agent, skills, tools, Ultra-mode subagents, streaming events, and artifact system.
```

## 2. Positioning

### 2.1 One-Line Positioning

EcomLaunch-Agent helps ecommerce launch operators validate a new product idea before committing inventory, creative production, or ad budget.

### 2.2 What It Produces

The primary deliverable is a **Launch Validation Pack**, not a generic research report.

Required output modules:

- Launch context
- Public market signal brief
- Market pattern map
- Customer voice and scenario map
- Audience wedge
- Offer hypotheses
- Listing and content assets
- 7-day validation plan
- Evidence ledger
- Missing-data and limitations summary

Required artifact files:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

Optional artifact files:

```text
review-insights.json
risk-notes.md
source-list.md
launch-crew-events.json
```

### 2.3 What It Is Not

EcomLaunch must not position itself as:

- a Taobao/Xiaohongshu/Douyin full crawler
- a merchant backend BI system
- an ad attribution or bidding optimizer
- a platform private-metric analyst
- a generic DeerFlow research clone
- a pure competitor-analysis report generator

It must not claim access to:

- GMV
- CTR
- CVR
- ROI
- ad spend
- actual sales volume
- refund rate
- repeat purchase rate
- exact market share
- platform backend audience data

Unless the user uploads real data containing those metrics, these fields must be marked as unavailable.

## 3. Target Users

### 3.1 Primary Persona

Primary user:

```text
Ecommerce new-product launch owner
```

Typical roles:

- category operator
- merchant growth PM
- content-commerce operator
- MCN selection / creator-commerce operator
- new consumer brand ecommerce operator
- early ecommerce founder or student founder

They often start with incomplete inputs:

- "I want to make a ceramic cup"
- a Taobao/JD/Amazon product link
- a Douyin/Xiaohongshu content idea
- a few competitor links
- supplier notes
- screenshots
- CSV exports
- a vague request from a manager

Their job is not to read a report. Their job is to decide:

- Is this product worth a small test?
- Which audience wedge should we start with?
- What should the first offer promise be?
- What content angles should we test first?
- What data is missing?
- What should we do in the next 7 days?

### 3.2 Secondary Users

Secondary users:

- small ecommerce brand founders who need low-cost validation
- MCN / creator commerce teams evaluating product fit
- interviewers or reviewers evaluating the project as an agent-system portfolio piece

### 3.3 Non-Target Users

Not target users:

- analysts who require verified full-platform market data
- ad-ops users who require attribution and ROI dashboards
- backend data engineers building ecommerce data pipelines
- users expecting login-wall scraping, CAPTCHA bypass, or private dashboard access

## 4. User Journey

The core journey is:

```text
Rough product idea
-> conversational clarification
-> public signal collection
-> source quality and evidence classification
-> market pattern synthesis
-> customer voice and scenario extraction
-> audience wedge and offer hypotheses
-> listing/content assets
-> 7-day validation plan
-> evidence ledger
-> user feedback/uploaded test results
-> revised launch recommendation
```

### 4.1 Journey Map

| Stage | User State | Product Behavior | Output |
| --- | --- | --- | --- |
| Opportunity trigger | "This product might be worth doing" | Accept natural-language idea, link, or upload | Draft launch context |
| Clarification | "I do not have complete info" | Ask at most one high-impact question, or proceed with labeled assumptions | Assumption brief |
| Public signal scan | "What is visible in the market?" | Use `web_search`, `web_fetch`, uploaded files | Market signal brief |
| Source quality check | "Can I trust this?" | Label source type, blocked/thin pages, login walls, search snippets | Evidence quality notes |
| Market pattern synthesis | "How are products sold today?" | Summarize price bands, claims, content patterns, differentiation gaps | Market pattern map |
| VOC extraction | "Why would customers buy?" | Extract pain points, triggers, objections, scenarios, customer wording | VOC insight map |
| Strategy | "How should we enter?" | Generate audience wedge, offer hypotheses, risk notes | Offer strategy |
| Assets | "What can I test tomorrow?" | Generate listing copy, content hooks, scripts, creator brief | Content and listing pack |
| Validation | "How do I decide continue/stop?" | Build 7-day tests with validation signals and decision rules | Launch calendar |
| Audit | "What is evidence vs assumption?" | Remove unsupported private metrics, create evidence ledger | Evidence ledger |

## 5. DeerFlow Foundation

EcomLaunch must remain a product layer on top of DeerFlow. It should not fork or replace the runtime.

The foundation chain is:

```text
frontend chat input
-> thread.submit
-> runtime context: model, mode, agent_name, files, thread_id
-> backend LangGraph-compatible run worker
-> Lead Agent factory
-> model + middleware + skills + tools
-> optional task-tool subagents in Ultra mode
-> tool calls and custom events stream to frontend
-> files written under /mnt/user-data/outputs
-> present_files updates ThreadState.artifacts
-> frontend artifact viewer renders files
```

### 5.1 Frontend Submission

Existing file:

```text
frontend/src/core/threads/hooks.ts
```

The existing thread submission path already:

- uploads files
- sends the user message
- sends runtime context
- maps `mode` into runtime flags
- persists thread state
- streams values, messages, and custom events

For EcomLaunch, reuse this path. Do not build a separate launch API for MVP.

### 5.2 Ultra Mode Semantics

Ultra mode currently maps to:

```ts
thinking_enabled: true
is_plan_mode: true
subagent_enabled: true
reasoning_effort: "high"
```

Product interpretation:

```text
Ultra = Launch Crew mode
thinking + plan/todo + specialist subagents + highest reasoning depth
```

EcomLaunch should preserve this behavior and make it visible in the product through a right-side collaboration panel in a later milestone.

### 5.3 Lead Agent

Existing files:

```text
backend/packages/harness/deerflow/agents/lead_agent/agent.py
backend/packages/harness/deerflow/agents/lead_agent/prompt.py
```

The Lead Agent remains the primary orchestrator.

For EcomLaunch, the Lead Agent should act as:

```text
launch-director
```

Responsibilities:

- understand the launch task
- decide whether clarification is needed
- load/follow the `ecom-launch` skill
- call public-data tools
- delegate to specialist subagents in Ultra mode
- synthesize subagent results
- enforce evidence rules
- produce and present artifacts

### 5.4 Tools

Current core tools:

- `web_search`
- `web_fetch`
- `image_search`
- `read_file`
- `write_file`
- `grep`
- `glob`
- `present_files`
- `ask_clarification`
- `task` in Ultra mode

Current `web_search`:

```text
DuckDuckGo / DDG search, no paid API key.
```

Current `web_fetch`:

```text
httpx static fetch
+ readability extraction
+ auto Playwright rendering when static content is too thin or looks like a JS shell
```

Supported by current data ability:

- public search results
- brand sites
- review/articles
- publicly accessible ecommerce SEO pages
- some Taobao/JD SEO pages
- some Douyin public video pages
- uploaded user materials

Not reliably supported:

- Xiaohongshu full note/search/comment access
- Taobao/Tmall/JD/PDD full product/search/review data
- Douyin live/search/comment full access
- private merchant metrics
- login-wall content
- CAPTCHA or anti-bot bypass

Product consequence:

```text
Position the product around public-signal launch validation, not platform-deep scraping.
```

### 5.5 Skills

Existing skill:

```text
skills/custom/ecom-launch/SKILL.md
```

The skill is the main product protocol. It must define:

- when to use EcomLaunch
- launch brief clarification behavior
- evidence labels
- forbidden private metrics
- public-source strategy
- subagent coordination
- required artifacts
- artifact schemas
- final response rules

### 5.6 Subagents

Existing mechanism:

```text
Lead Agent calls task(description, prompt, subagent_type)
-> task_tool resolves SubagentConfig
-> SubagentExecutor creates a separate agent invocation
-> subagent runs with its own system prompt, tools, skills, and isolated context
-> task_tool polls until terminal status
-> custom events stream task progress
-> final result returns to Lead Agent
```

Existing files:

```text
backend/packages/harness/deerflow/tools/builtins/task_tool.py
backend/packages/harness/deerflow/subagents/executor.py
backend/packages/harness/deerflow/subagents/registry.py
backend/packages/harness/deerflow/subagents/status_contract.py
```

Do not rewrite subagent execution. EcomLaunch should use `config.yaml` custom subagents.

### 5.7 Plan Mode

Plan mode uses DeerFlow's Todo middleware.

Existing file:

```text
backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py
```

In EcomLaunch, todos should represent launch workflow progress:

- clarify launch context
- gather public signals
- extract VOC
- design offer hypotheses
- create content assets
- audit evidence
- present artifacts

### 5.8 Artifacts

Existing artifact system should remain the source of truth for deliverables.

Existing files:

```text
backend/packages/harness/deerflow/tools/builtins/present_file_tool.py
frontend/src/components/workspace/artifacts/*
```

All final files must be saved under:

```text
/mnt/user-data/outputs
```

Then exposed with `present_files`.

## 6. pm-skills Design Lessons

Reference:

```text
phuryn/pm-skills
```

Key lessons to apply:

1. Do not sell a generic agent. Sell a workflow with a named deliverable.
2. Separate reusable methods (`skills`) from end-to-end flows (`commands`).
3. Each flow should have a stable output template.
4. Each flow should ask only the context needed for the decision.
5. Each flow should end with concrete next steps.
6. Risk/assumption testing is as important as confident recommendations.

Mapping to EcomLaunch:

| pm-skills pattern | EcomLaunch equivalent |
| --- | --- |
| `/discover` | Launch opportunity clarification and assumptions |
| `/plan-launch` | Launch Validation Pack |
| `beachhead-segment` | Audience wedge |
| `gtm-strategy` | 7-day launch validation strategy |
| `prioritize-assumptions` | Offer hypothesis priority |
| `strategy-red-team` | Evidence checker and kill-assumption audit |

EcomLaunch should not become a marketplace of many ecommerce skills in MVP. It should first perfect one flagship workflow:

```text
validate-launch -> Launch Validation Pack
```

## 7. EcomLaunch Agent Architecture

### 7.1 User-Visible Agent

Only one agent should be user-visible:

```text
EcomLaunch Agent
```

The user should not have to manually operate individual subagents.

### 7.2 Internal Roles

Internal runtime roles:

```text
launch-director
├── market-scout
├── voc-miner
├── offer-architect
├── asset-studio
└── evidence-checker
```

Strict role boundaries:

| Role | Main Job | Must Not Do |
| --- | --- | --- |
| `launch-director` | clarify, dispatch, synthesize, present | pretend to have private data |
| `market-scout` | public market signals, competitors, price bands, claims | write final positioning alone |
| `voc-miner` | pain points, triggers, objections, scenarios, customer wording | invent reviews |
| `offer-architect` | audience wedge, JTBD, promise, differentiators, hypotheses | write generic ad copy |
| `asset-studio` | listing copy, hooks, scripts, creator brief, FAQ | invent unsupported claims |
| `evidence-checker` | audit claims, evidence ledger, missing data | soften unsupported metric claims |

### 7.3 Subagent Count

Final target:

```text
1 user-visible agent
5 configured subagents
6 total roles including launch-director
```

MVP can run with fewer only if necessary:

```text
Minimum viable internal roles:
market-scout + offer-architect + evidence-checker
```

But the spec target remains 5 subagents because each corresponds to a distinct Launch Validation Pack module.

## 8. Evidence Model

### 8.1 Evidence Types

```text
observed_public
Real public webpages, product pages, public videos, public reviews, public articles, official pages, platform-visible listings.

public_dataset
Open datasets or public benchmark examples.

uploaded_real
User-uploaded real reviews, product exports, survey notes, sales notes, early order data, screenshots, or CSV files.

estimated
Reasoned estimate from public evidence. Must not be presented as fact.

synthetic_demo
Mock data for UI/demo only. Must not drive business claims.

unavailable
Metric cannot be known from available data.
```

### 8.2 Source Quality Labels

Every source used in a recommendation should be classified where possible:

```text
search_snippet_only
public_page
public_video
brand_site
review_article
ecommerce_seo_page
uploaded_material
thin_page
blocked_or_login_wall
unavailable_private_metric
```

### 8.3 Evidence Ledger Schema

`evidence-ledger.json` must be a JSON array:

```json
[
  {
    "id": "ev_001",
    "claim": "A concise claim supported by evidence or marked as an estimate.",
    "evidence_type": "observed_public",
    "source_type": "public_page",
    "source_title": "Example product page",
    "source_url": "https://example.com/product",
    "source_quote_or_summary": "Short summary of what was observed.",
    "confidence": "medium",
    "used_in": ["positioning-brief.md", "listing-pack.md"],
    "limitations": "Public sample may be incomplete."
  }
]
```

Required fields:

- `id`
- `claim`
- `evidence_type`
- `confidence`
- `used_in`
- `limitations`

Recommended fields:

- `source_type`
- `source_title`
- `source_url`
- `source_quote_or_summary`
- `observed_count`
- `platform`
- `retrieved_at`

Confidence values:

```text
high
medium
low
unknown
```

### 8.4 Forbidden Claims

Unless uploaded real data provides the metric, the agent must not claim:

- GMV
- CTR
- CVR
- ROI
- ad spend
- actual sales volume
- refund rate
- repeat purchase rate
- exact market share
- verified uplift percentages

Allowed phrasing:

```text
Public data suggests...
Visible public pages indicate...
This is an estimate based on observed public evidence...
Private merchant metrics are unavailable, so this should be validated after launch...
```

Forbidden phrasing:

```text
This product will increase GMV by 30%.
The current CVR is 5.2%.
Competitor A sells 20,000 units per month.
ROI will reach 3.5.
```

When the user has no merchant backend data, these private metrics must not become default final-artifact KPIs or decision rules. They may appear only as unavailable metrics, uploaded evidence, or future metrics to collect after platform access exists. Default validation plans should prefer sample feedback, share/save/comment intent, inquiry count, preorder interest, creator response quality, repeated objections, and manual price-acceptance checks.

## 9. Data Collection Strategy

### 9.1 Current Crawling Capability

Current `web_search + web_fetch` can support:

- public search discovery
- source snippets
- public web pages
- ecommerce SEO pages when indexed and accessible
- brand websites
- public review articles
- Douyin public video detail pages when accessible
- user-uploaded data

It cannot reliably support:

- Xiaohongshu full note/search/comment mining
- Taobao/JD/PDD full product/review/search crawling
- Douyin live/search/comment scraping
- authenticated dashboards
- platform private metrics

### 9.2 Product Rule

When a desired source is unavailable, the agent should:

1. mark it unavailable or low-confidence,
2. explain why,
3. suggest user-uploaded screenshots/CSV/links as optional evidence,
4. continue with available public signals,
5. avoid pretending the source was successfully mined.

### 9.3 Search Query Templates

Use query patterns like:

```text
{product/category} 淘宝
{product/category} 京东
{product/category} 抖音
site:taobao.com {product/category}
site:jd.com {product/category}
site:douyin.com {product/category}
{product/category} 测评
{product/category} 痛点
{product/category} 安全
{product/category} 礼物
{product/category} 评价
```

For international cases:

```text
{product/category} reviews
{product/category} Amazon
{product/category} Reddit
{product/category} problems
{product/category} gift
```

## 10. Core Workflow: validate-launch

### 10.1 Trigger

Use this workflow when the user asks to:

- validate a product idea
- analyze a product/category before launch
- decide how to position a new product
- turn a product link into a launch plan
- generate listing/content assets for a first test
- create a 7-day ecommerce launch plan

### 10.2 Clarification Behavior

The product must remain conversational, not form-driven.

Minimum required input before market work:

- product idea, product category, product URL, or uploaded product material

If missing, ask one concise clarification question.

Helpful but optional:

- target platform
- target user
- target price range
- supply constraints
- competitor links
- desired outputs

If optional fields are missing, proceed with labeled assumptions unless the answer would materially change the work.

### 10.3 Workflow Steps

```text
1. Extract launch context
2. Ask one clarification if product/category is missing
3. Create todo list in plan/Ultra mode
4. In Ultra mode, dispatch specialist subagents
5. Gather public signals and uploaded evidence
6. Classify source quality and evidence type
7. Synthesize market patterns and VOC
8. Build audience wedge and offer hypotheses
9. Generate listing/content assets
10. Design 7-day validation plan
11. Run evidence audit
12. Write artifacts under /mnt/user-data/outputs
13. Call present_files
14. Give concise chat summary
```

### 10.4 Output Template

Final `launch-war-room.html` and summary Markdown should use stable sections:

```text
Launch Context
Launch Readiness Verdict
Public Market Signals
Market Pattern Map
Customer Voice Map
Audience Wedge
Offer Hypotheses
Listing and Content Assets
7-Day Validation Plan
Evidence Ledger Summary
Missing Data and Limitations
Next Actions
```

## 11. Ultra Launch Crew Visualization

This is a mid-stage or later frontend enhancement. It must not block the agent workflow MVP.

### 11.1 UI Principle

Do not replace the DeerFlow chat page with a game-like UI.

Keep:

```text
left / main area: DeerFlow-style conversation, thinking, plan, messages, artifacts
right panel: EcomLaunch Launch Crew collaboration scene
```

The right panel should make Ultra's real subagent workflow visible.

### 11.2 Scene Concept

Working title:

```text
Launch Studio
```

Alternative names:

- Launch Crew
- Launch War Room
- EcomLaunch Studio
- 上新小队
- 新品启动作战室

The scene does not have to be a classic office. Preferred concept:

```text
ecommerce launch studio with specialist workstations:
market radar desk, customer voice wall, offer strategy board,
content studio, evidence review desk, and central launch board.
```

### 11.3 Role Mapping

| Runtime Role | User-Facing Label | Scene Area | Deliverable Icon |
| --- | --- | --- | --- |
| `launch-director` | 上新主理人 | central board | Launch Pack |
| `market-scout` | 市场侦察员 | market radar desk | signal map |
| `voc-miner` | 用户洞察员 | customer voice wall | sticky-note cluster |
| `offer-architect` | 卖点策划师 | strategy board | blueprint |
| `asset-studio` | 内容编导 | content studio | content pack / bread |
| `evidence-checker` | 证据审核员 | evidence desk | stamp / evidence book |

### 11.4 State Model

Define a frontend state model before building the visual scene:

```ts
type LaunchCrewStatus =
  | "idle"
  | "assigned"
  | "thinking"
  | "searching"
  | "reading"
  | "writing"
  | "reviewing"
  | "done"
  | "blocked"
  | "failed";

type LaunchCrewAgent = {
  id:
    | "launch-director"
    | "market-scout"
    | "voc-miner"
    | "offer-architect"
    | "asset-studio"
    | "evidence-checker";
  label: string;
  status: LaunchCrewStatus;
  bubble?: string;
  latestMessageId?: string;
  deliverables: LaunchDeliverable[];
};

type LaunchDeliverable = {
  id: string;
  title: string;
  filepath: string;
  kind: "brief" | "table" | "content" | "calendar" | "evidence" | "dashboard";
};
```

### 11.5 Event Mapping

The right panel must be driven by real DeerFlow events where possible.

Mapping:

| DeerFlow Signal | Launch Crew Effect |
| --- | --- |
| `mode === "ultra"` | enable Launch Crew panel |
| AI tool call `task(..., subagent_type)` | set corresponding agent to `assigned` |
| custom event `task_running` | update agent `bubble` and `latestMessageId` |
| latest message has `web_search` | `searching` |
| latest message has `web_fetch` | `reading` |
| latest message has `write_file` | `writing` |
| `subagent_status=completed` | `done` |
| `subagent_status=failed/timed_out` | `failed` or `blocked` |
| new artifact path matches known file | add deliverable to role |

Artifact-to-role mapping:

| Artifact | Role |
| --- | --- |
| `competitor-table.csv` | `market-scout` |
| `source-list.md` | `market-scout` |
| `review-insights.json` | `voc-miner` |
| `positioning-brief.md` | `offer-architect` |
| `listing-pack.md` | `asset-studio` |
| `content-pack.md` | `asset-studio` |
| `launch-calendar.csv` | `offer-architect` |
| `evidence-ledger.json` | `evidence-checker` |
| `launch-war-room.html` | `launch-director` |

### 11.6 Bubble Content Rules

Speech bubbles should show concise work summaries, not full hidden reasoning.

Allowed bubble content:

- task assignment summary
- current tool action summary
- short finding summary
- source limitation warning
- deliverable completion message

Do not place full long-form reasoning in the bubble. Full thinking remains in DeerFlow's existing collapsible reasoning UI.

Example bubbles:

```text
正在搜索公开市场信号...
这个小红书页面只有备案信息，标记为低可用。
发现“送礼”和“办公桌美学”两个场景。
内容资产已出炉。
未发现真实销量来源，已降级为公开信号判断。
```

### 11.7 Deliverable Interaction

Deliverable icons in the scene should reuse the existing artifact viewer:

```text
click scene deliverable
-> selectArtifact(filepath)
-> setArtifactsOpen(true)
-> existing ArtifactFileDetail renders preview/download
```

Do not build a parallel file preview system.

### 11.8 Visual Design Process

When building the pixel/illustrated scene later:

1. finalize state model and event mapping first
2. create a simple non-pixel Launch Crew panel
3. verify it is driven by real events
4. generate 2-3 image concepts with image generation
5. choose one visual direction
6. implement scene as CSS/PNG/SVG/sprite assets
7. add small animations only after data flow is correct

Prompt direction for image generation:

```text
Pixel-art isometric ecommerce launch studio, professional but warm,
five specialist workstations: market radar desk, customer voice wall,
offer strategy whiteboard, content studio table, evidence review desk,
central launch board, small agent characters with speech bubbles,
artifact icons on desks, clean readable layout, not childish.
```

## 12. Frontend Product Surface

### 12.1 Near-Term Principle

Do not heavily redesign the whole DeerFlow page yet.

Near-term changes should be additive:

- EcomLaunch agent route/entry
- EcomLaunch empty-state copy
- EcomLaunch starter prompts
- Ultra default or recommendation for complex launch tasks
- optional right panel placeholder for Launch Crew

### 12.2 Starter Prompts

Examples:

```text
我想验证一个新品想法
我有一个竞品链接，帮我找差异化切入
帮我生成 7 天上新验证包
帮我把这个产品做成抖音/小红书内容测试方案
我有测试反馈，帮我复盘是否继续
```

### 12.3 Placeholder

Input placeholder:

```text
告诉我你想验证的新品、类目、商品链接或测试反馈...
```

### 12.4 Mode Copy

Keep existing modes technically, but EcomLaunch copy may interpret them as:

| Mode | EcomLaunch Meaning |
| --- | --- |
| Flash | quick direction check |
| Thinking | deeper single-agent reasoning |
| Pro | plan-first launch work |
| Ultra | Launch Crew multi-agent validation |

## 13. Backend / Config Spec

### 13.1 Existing Config Target

Custom subagents should live under:

```text
config.yaml -> subagents.custom_agents
```

Target subagents:

- `market-scout`
- `voc-miner`
- `offer-architect`
- `asset-studio`
- `evidence-checker`

Each subagent should:

- include the `ecom-launch` skill
- have a narrow role prompt
- use only required tools
- avoid recursive subagent calls
- return structured, evidence-labeled results

### 13.2 No Runtime Rewrite

The MVP should not rewrite:

- LangGraph-compatible thread run APIs
- `RunManager`
- `StreamBridge`
- `SubagentExecutor`
- `present_files`
- artifact router
- generic DeerFlow tool loading

### 13.3 Possible Later Tools

Only add backend tools after prompt/tool composition proves brittle:

- `classify_source_quality`
- `validate_evidence_ledger`
- `normalize_competitor_table`
- `render_launch_dashboard`
- `extract_launch_pack_sections`

## 14. Implementation Roadmap

### Milestone 1: Product Protocol

Goal:

```text
EcomLaunch behavior is specified and available to the agent.
```

Deliverables:

- this spec
- strengthened `skills/custom/ecom-launch/SKILL.md`
- strengthened `agents/ecom-launch/SOUL.md`
- custom subagents configured

Acceptance:

- EcomLaunch skill is discoverable
- custom subagents are available in Ultra mode
- no private metric claims are permitted by protocol

### Milestone 2: Multi-Agent Workflow Smoke Test

Goal:

```text
Ultra mode actually delegates work to EcomLaunch subagents.
```

Deliverables:

- manual run prompt
- sample demo input
- run transcript or notes
- generated artifact set

Acceptance:

- at least 3 EcomLaunch subagents are invoked in a serious run
- subagent outputs are integrated rather than pasted raw
- final response references presented files
- evidence ledger exists and validates as JSON
- JSON artifacts are arrays/objects with escaped string values, not Markdown code blocks or multiline raw strings
- CSV artifacts parse with the declared column count

### Milestone 3: Artifact-First MVP

Goal:

```text
Launch Validation Pack can be generated reliably.
```

Deliverables:

- required artifact files
- self-contained `launch-war-room.html`
- evidence ledger
- competitor table
- content pack
- launch calendar

Acceptance:

- all required artifacts are presented through existing DeerFlow artifact viewer
- `launch-war-room.html` previews correctly
- no forbidden private metric claim appears without uploaded evidence
- missing data is explicitly named

### Milestone 4: Conversational EcomLaunch Entry

Goal:

```text
User can start EcomLaunch without a manual prompt.
```

Deliverables:

- dedicated EcomLaunch route or agent entry
- starter prompts
- EcomLaunch empty state
- default or suggested Ultra mode for full validation

Acceptance:

- user can start from a vague product idea
- agent asks one targeted clarification when necessary
- uploaded files are available to the task
- output remains artifact-first

### Milestone 5: Launch Crew State Model

Goal:

```text
Frontend can derive per-agent status from existing DeerFlow events.
```

Deliverables:

- `LaunchCrewState` model
- mapper from messages/custom events/artifacts to crew state
- simple right-side non-pixel panel

Acceptance:

- task dispatch changes role status
- `task_running` updates bubbles
- artifact completion creates clickable deliverables
- panel works without fake scripted animation

### Milestone 6: Launch Studio Visual Layer

Goal:

```text
Ultra mode becomes visually differentiated without replacing the core chat.
```

Deliverables:

- generated concept images
- selected scene direction
- implemented right-side visual scene
- basic role animations
- clickable deliverable icons

Acceptance:

- left DeerFlow chat remains usable
- right panel clearly shows multi-agent collaboration
- visual state follows real execution events
- deliverables open in existing artifact viewer

## 15. Evaluation Criteria

### 15.1 Product Quality

Good result:

- feels like an ecommerce launch validation product
- produces a concrete Launch Validation Pack
- recommendations are actionable
- private-data gaps are clearly named
- evidence is labeled
- content assets are usable for a first test

Bad result:

- generic market research essay
- pure competitor table with no launch decision
- fake GMV/ROI/CVR
- no evidence ledger
- no test plan
- no concrete listing/content output

### 15.2 Agent Quality

Good result:

- lead agent uses the EcomLaunch skill
- Ultra mode delegates to specialist subagents
- subagents do not duplicate each other
- final answer synthesizes, not merely concatenates
- evidence checker catches unsupported claims

Bad result:

- one long single-agent response in Ultra
- only generic `general-purpose` subagents
- subagent outputs pasted raw
- unsupported metrics remain
- artifacts missing

### 15.3 Technical Quality

Good result:

- uses existing DeerFlow runtime
- additive product-layer changes
- no unnecessary runtime forks
- artifact system remains compatible
- Launch Crew panel is event-driven

Bad result:

- custom parallel backend API
- hardcoded demo-only data
- fake right-side animation unrelated to events
- broken generic DeerFlow functionality

## 16. Demo Scenario

Recommended Chinese demo:

```text
我想做一款送女生的高颜值陶瓷杯，主要想在小红书和抖音种草，
但我没有真实后台数据。帮我判断怎么切入，并生成 7 天上新验证包。
```

Why it works:

- product is easy to understand
- public product/SEO/video signals exist
- Xiaohongshu limitations can be honestly demonstrated
- content assets are visually intuitive
- evidence ledger matters because private metrics are unavailable

Expected result:

- cautious launch readiness verdict
- audience wedge such as gift / desk aesthetic / emotional value
- warning that "generic high appearance" is too broad
- public signal summary
- content hooks
- listing copy
- 7-day validation plan
- evidence ledger and unavailable-metrics list

Alternative demo:

```text
Portable leak-proof coffee tumbler for office commute and light outdoor use.
Target platforms: Taobao, Xiaohongshu, Douyin.
Target price: RMB 99-199.
Constraints: stainless steel, easy to clean, no electronics.
```

## 17. Repository Strategy

Target repository:

```text
git@github.com:CheungkiCheung/EcomLaunch-Agent.git
```

Local source:

```text
/Users/zhangqixiang/0_2实习/deepagents/deer-flow
```

Do not rename every internal `deerflow` package in early MVP. Preserve runtime stability.

Brand first in:

- README
- app title and navigation
- EcomLaunch route/entry
- custom skill
- custom subagents
- artifacts
- demo scenario
- right-side Ultra Launch Crew panel

Keep ignored:

- `.env`
- `config.yaml`
- `extensions_config.json`
- `frontend/node_modules`
- `frontend/.next`
- `backend/.venv`
- `backend/.deer-flow`
- logs
- runtime outputs

## 18. Open Questions

1. Should the first EcomLaunch UI be a dedicated route or a specialized agent route inside the existing workspace?
2. Should Ultra be the default for EcomLaunch full validation, or only recommended by the UI?
3. Should the first Launch Crew panel be always visible on EcomLaunch threads, or only when Ultra is selected?
4. Should `launch-war-room.html` remain the first dashboard, or should the native React dashboard read JSON artifacts sooner?
5. Should source quality classification remain prompt-based in MVP, or become a backend tool earlier?

## 19. Near-Term Decision

The immediate focus is:

```text
multi-agent workflow + skill protocol + tool usage + artifact reliability
```

The right-side visual Launch Studio is important but later.

Near-term work order:

1. strengthen `ecom-launch` skill and custom agent prompt
2. verify Ultra dispatches specialist subagents
3. verify `web_search` and `web_fetch` produce usable public signals
4. generate complete artifact set
5. validate evidence ledger
6. only then build Launch Crew event state
7. only then build visual scene

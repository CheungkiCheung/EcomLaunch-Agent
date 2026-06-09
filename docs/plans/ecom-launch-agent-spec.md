# EcomLaunch Agent Spec

## 1. Project Positioning

EcomLaunch Agent is a DeerFlow-based multi-agent product for ecommerce new-product launch research and execution planning.

The system helps a user move from a product idea or public product link to a launch-ready ecommerce package:

- public market scan
- competitor and price-band table
- review and VOC insight mining
- product positioning brief
- ecommerce listing copy
- short-video / livestream / social content pack
- 7-day launch testing plan
- evidence ledger that separates observed facts from estimates

The project is intentionally designed around public data because the builder does not have access to real merchant backend metrics such as GMV, CTR, CVR, ROI, ad spend, refund rate, or user cohort data.

This is not a generic competitive-analysis wrapper. The output is a launch operating package for ecommerce merchants and platform operators.

## 2. Target Users

Primary user:

- ecommerce seller, student founder, or operator preparing to launch a product
- has a product idea, category, or product link
- does not yet have real store performance data
- needs a structured launch plan based on public market signals

Secondary user:

- internet/ecommerce company interviewer evaluating a candidate project
- wants to see agent orchestration, public-data reasoning, and business product thinking

## 3. Goals

1. Reuse DeerFlow's strengths:
   - real web search
   - web fetch
   - file upload
   - artifact delivery
   - Ultra-mode `task` subagents
   - skills-based workflow specialization

2. Build a vertical ecommerce product layer:
   - conversational EcomLaunch agent entry
   - ecommerce-specific prompt protocol
   - custom ecommerce subagents
   - structured outputs
   - launch dashboard artifact

3. Avoid fake private business metrics:
   - no invented GMV
   - no invented CTR/CVR/ROI
   - no fake ad spend
   - no pretend merchant backend access

4. Make every major recommendation evidence-aware:
   - public observed data
   - public dataset
   - user-uploaded data
   - model estimate
   - synthetic demo placeholder

5. Deliver a credible MVP that can be explained as:
   - "A public-data-driven ecommerce new-product launch copilot built on DeerFlow's multi-agent runtime."

## 4. Non-Goals

The MVP will not:

- connect to Taobao, Tmall, JD, Douyin, Pinduoduo, Amazon Seller Central, or Shopify private merchant backends
- claim verified GMV uplift
- optimize real ad delivery or bidding
- place orders, edit listings, or execute platform actions
- scrape pages that require login, CAPTCHA bypass, or anti-bot evasion
- guarantee complete market coverage
- replace professional legal, advertising compliance, or platform policy review

## 5. DeerFlow Foundation And Modification Map

This project must be implemented as a product layer on top of DeerFlow, not as a rewrite.

The important architectural interpretation is:

```text
DeerFlow is not a hardcoded competitive-analysis workflow.
It is a configurable agent runtime:

frontend thread.submit
-> LangGraph-compatible run API
-> runtime worker
-> dynamically created lead agent
-> config-loaded tools
-> skills prompt / skill loading
-> optional task-tool subagents
-> files written to /mnt/user-data/outputs
-> present_files updates artifacts
-> frontend artifact viewer
```

EcomLaunch should preserve this chain and replace the generic research behavior with ecommerce launch behavior through skills, custom subagents, prompt builders, and artifact schemas.

### 5.1 Existing DeerFlow Entry Points

The frontend already submits messages through the LangGraph SDK:

```text
frontend/src/core/threads/hooks.ts
```

Relevant behavior:

- uploads files first
- calls `thread.submit(...)`
- passes runtime context
- sets `thinking_enabled`
- sets `is_plan_mode`
- sets `subagent_enabled` when mode is Ultra
- passes `thread_id`

EcomLaunch should reuse this submission path. The first product UI should remain conversational: a dedicated EcomLaunch chat entry should pass an `agent_name` / runtime context and let the agent complete missing launch brief details with DeerFlow's existing clarification mechanism. It should not create a separate research endpoint for MVP.

### 5.2 Existing Backend Run Layer

The backend exposes LangGraph-compatible thread run endpoints:

```text
backend/app/gateway/routers/thread_runs.py
backend/packages/harness/deerflow/runtime/runs/worker.py
```

The run worker:

- builds runtime context with `thread_id`, `run_id`, and `app_config`
- creates the effective agent via the lead-agent factory
- streams `values`, `messages`, and `custom` events
- maps results back to the existing SSE protocol

EcomLaunch should not rewrite this run layer. Product specialization belongs above it.

### 5.3 Existing Lead Agent Layer

The lead agent is created here:

```text
backend/packages/harness/deerflow/agents/lead_agent/agent.py
backend/packages/harness/deerflow/agents/lead_agent/prompt.py
```

The factory resolves:

- model
- thinking mode
- plan mode
- subagent mode
- tool groups
- available skills
- middleware stack
- prompt sections

EcomLaunch should treat the lead agent as `launch-director` through:

- custom agent SOUL/config if using DeerFlow custom-agent support
- EcomLaunch prompt template if using a dedicated frontend entry
- `ecom-launch` skill
- Ultra mode subagent orchestration

Do not fork the lead-agent factory unless a later requirement cannot be expressed through config, skill, or prompt builder.

### 5.4 Existing Tools Layer

Tools are loaded from config:

```text
backend/packages/harness/deerflow/tools/tools.py
config.yaml
config.example.yaml
```

Current useful tools:

- `web_search`
- `web_fetch`
- `image_search`
- `read_file`
- `write_file`
- `grep`
- `glob`
- `present_files`
- `task` when `subagent_enabled=true`

EcomLaunch should reuse these first. New backend tools should be added only after the artifact-first MVP proves that a repeated operation is too brittle as prompt/tool composition.

Possible post-MVP tools:

- `parse_review_csv`
- `normalize_competitor_table`
- `validate_evidence_ledger`
- `render_launch_dashboard`

### 5.5 Existing Skills Layer

Skills are discovered from:

```text
skills/public/*/SKILL.md
skills/custom/*/SKILL.md
backend/packages/harness/deerflow/skills/*
```

DeerFlow does not blindly inject every full skill into the prompt. It lists available skill metadata and paths, then instructs the model to read relevant `SKILL.md` files progressively.

EcomLaunch should add:

```text
skills/custom/ecom-launch/SKILL.md
```

The skill is the main business-protocol layer:

- ecommerce launch workflow
- evidence labeling rules
- private-metric prohibitions
- output artifact contract
- subagent coordination expectations

### 5.6 Existing Subagent Layer

Subagents are not fixed LangGraph nodes. They are launched dynamically through the `task` tool:

```text
backend/packages/harness/deerflow/tools/builtins/task_tool.py
backend/packages/harness/deerflow/subagents/registry.py
backend/packages/harness/deerflow/subagents/config.py
backend/packages/harness/deerflow/subagents/executor.py
```

Existing mechanism:

- lead agent calls `task(description, prompt, subagent_type)`
- `task_tool` resolves `SubagentConfig`
- subagent tools are loaded with `subagent_enabled=false` to prevent recursive nesting
- `SubagentExecutor` creates another agent with its own prompt/tools/skills
- backend polls subagent execution
- custom stream events report task status
- result returns to the lead agent for synthesis

EcomLaunch should use `config.yaml` `subagents.custom_agents` for ecommerce roles instead of implementing new graph nodes.

### 5.7 Existing Artifact Layer

Final user-visible files must be saved under:

```text
/mnt/user-data/outputs
```

Then the agent calls:

```text
present_files
```

Relevant files:

```text
backend/packages/harness/deerflow/tools/builtins/present_file_tool.py
backend/packages/harness/deerflow/agents/thread_state.py
backend/app/gateway/routers/artifacts.py
frontend/src/components/workspace/artifacts/*
```

EcomLaunch MVP should generate artifact files compatible with this existing layer. A native React dashboard can be added later, but the first working product should rely on `launch-war-room.html` plus structured JSON/CSV/Markdown artifacts.

### 5.8 Modification Strategy

Implementation priority:

1. Product protocol in `ecom-launch` skill
2. Custom subagents in `config.yaml`
3. Manual prompt flow to verify artifact-first behavior
4. Dedicated conversational frontend entry that submits through existing `thread.submit`
5. Native dashboard reading generated artifacts
6. Optional backend validation/rendering tools

Avoid:

- rewriting `RunManager`
- rewriting `StreamBridge`
- rewriting `SubagentExecutor`
- replacing `present_files`
- creating a parallel non-LangGraph run API
- hardcoding ecommerce behavior into generic DeerFlow runtime files

## 6. Core User Flow

### 6.1 New Launch Task

User opens the EcomLaunch conversation and describes the launch task in natural language.

The user may provide any subset of:

- product idea or product link
- target platform
- target customer group
- target price range
- supply constraints
- optional competitor links
- optional uploaded review/product CSV
- desired outputs

The agent should extract a launch brief from the conversation. If the product/category itself is missing, the agent must ask a concise clarification question before researching. If target platform, target customer, price range, constraints, competitor links, or desired outputs are missing, the agent may either infer reasonable defaults with labels or ask one high-impact question when the answer would materially change the work.

Example input:

```text
Product: portable leak-proof coffee tumbler
Platform: Taobao + Xiaohongshu
Target users: office workers and light outdoor users
Price range: RMB 99-199
Constraints: stainless steel, must be easy to clean, no app or electronics
Desired outputs: competitor table, listing pack, short video scripts, 7-day launch plan
```

### 6.2 Agent Orchestration

The lead agent acts as a launch director.

In Ultra mode it delegates parallel work:

- market scouting
- review/VOC mining
- positioning strategy
- copy and content generation
- launch planning
- evidence checking

### 6.3 Artifact Delivery

The final response must create files under `/mnt/user-data/outputs` and call `present_files`.

Required MVP artifacts:

- `launch-war-room.html`
- `evidence-ledger.json`
- `competitor-table.csv`
- `positioning-brief.md`
- `listing-pack.md`
- `content-pack.md`
- `launch-calendar.csv`

Optional artifacts:

- `review-insights.json`
- `risk-notes.md`
- `source-list.md`

## 7. Evidence Model

The project must explicitly label the source quality of claims.

### 7.1 Evidence Types

```text
observed_public
Real public webpages, product pages, public reviews, official pages, public articles, platform-visible listings.

public_dataset
Open datasets such as public review datasets, ecommerce datasets, or uploaded benchmark examples.

uploaded_real
User-uploaded real data, such as reviews, product exports, survey notes, or early order records.

estimated
Reasoned estimate derived from public evidence. Must be clearly marked and cannot be presented as fact.

synthetic_demo
Mock or synthetic data used only for UI demos or examples. Must never drive final business claims.

unavailable
Metric cannot be known from available data.
```

### 7.2 Forbidden Claims

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

Allowed phrasing:

```text
Public data suggests...
Visible reviews indicate...
This is an estimate based on observed price bands...
Private merchant metrics are unavailable, so this should be validated after launch.
```

Forbidden phrasing:

```text
This product will increase GMV by 30%.
The current CVR is 5.2%.
Competitor A sells 20,000 units per month.
ROI will reach 3.5.
```

### 7.3 Evidence Ledger Schema

`evidence-ledger.json` must be an array of objects:

```json
[
  {
    "id": "ev_001",
    "claim": "Users frequently complain about leakage and difficult cleaning in portable coffee cups.",
    "evidence_type": "observed_public",
    "source_title": "Example product review page",
    "source_url": "https://example.com/product",
    "source_quote_or_summary": "Multiple reviews mention leakage during commute and hard-to-clean lid seams.",
    "confidence": "medium",
    "used_in": ["positioning-brief.md", "listing-pack.md"],
    "limitations": "Public review sample may be biased toward dissatisfied buyers."
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

Optional fields:

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

## 8. Agent Design

### 8.1 Lead Agent

Name:

```text
launch-director
```

Role:

- understand user launch goal
- decide whether more clarification is needed
- dispatch work to subagents
- synthesize final strategy
- enforce evidence rules
- ensure artifacts are produced

Behavior:

- if the user asks for private metrics and no data is uploaded, mark them unavailable
- use public search and fetch to gather market evidence
- run subagents in parallel when Ultra mode is enabled
- final output must include a concise answer and presented artifact files

### 8.2 Custom Subagents

#### market-scout

Purpose:

- search public market signals
- find visible competitors
- collect price bands
- summarize product claims and platform content patterns

Allowed tools:

- `web_search`
- `web_fetch`
- `image_search`
- `read_file`
- `write_file`

Outputs:

- competitor candidates
- price-band notes
- visible market patterns
- source list

#### review-miner

Purpose:

- mine public reviews, Q&A, discussions, uploaded review files
- cluster complaints, praise, purchase triggers, objections

Allowed tools:

- `web_search`
- `web_fetch`
- `read_file`
- `write_file`

Outputs:

- pain-point clusters
- positive triggers
- objection list
- customer wording bank

#### positioning-strategist

Purpose:

- turn evidence into ecommerce positioning
- identify target segment, core promise, differentiators, risk points

Allowed tools:

- `read_file`
- `write_file`
- `web_search`
- `web_fetch`

Outputs:

- positioning brief
- opportunity score
- validation hypotheses

#### listing-copywriter

Purpose:

- generate ecommerce title, bullets, product-page structure, FAQ, objection handling
- generate platform-aware content copy

Allowed tools:

- `read_file`
- `write_file`
- `web_search`
- `web_fetch`

Outputs:

- listing title options
- selling-point bullets
- product detail page outline
- FAQ/customer-service scripts

#### content-planner

Purpose:

- produce content launch assets
- short-video scripts
- livestream talk tracks
- Xiaohongshu/Douyin-style posts
- creator brief

Allowed tools:

- `read_file`
- `write_file`
- `web_search`
- `web_fetch`

Outputs:

- content pack
- hooks
- script variants
- creator brief

#### launch-planner

Purpose:

- create a 7-day launch testing plan
- define hypotheses, metrics to collect, decision rules

Allowed tools:

- `read_file`
- `write_file`

Outputs:

- launch calendar
- test matrix
- data collection checklist
- decision rules

#### evidence-checker

Purpose:

- audit final claims against evidence
- flag unsupported claims
- ensure forbidden private metrics are not invented

Allowed tools:

- `read_file`
- `write_file`

Outputs:

- evidence ledger
- unsupported-claims notes
- final confidence summary

## 9. Skill Design

Create a custom skill:

```text
skills/custom/ecom-launch/SKILL.md
```

Skill name:

```text
ecom-launch
```

Skill responsibilities:

- define ecommerce new-product launch workflow
- define evidence rules
- define output artifact contracts
- define opportunity scoring rubric
- define platform-aware content constraints

### 9.1 Opportunity Score

The agent may compute an opportunity score from 0 to 100, but it must be marked as an estimate unless uploaded real data supports it.

Suggested formula:

```text
Opportunity Score =
  demand_signal
+ pain_intensity
+ differentiation_space
+ price_room
+ content_virality
+ supply_feasibility
- competition_intensity
- compliance_risk
```

Each dimension should be scored 0-10 with evidence labels.

### 9.2 Launch Testing Protocol

When private metrics are unavailable, the system should recommend tests rather than claim outcomes.

Each test should include:

- hypothesis
- asset to test
- target audience
- metric to collect
- minimum sample requirement
- decision rule
- next action

Example:

```text
Hypothesis: "Leak-proof commute" is a stronger hook than "keeps coffee warm".
Asset: two title/video-hook variants
Metric: click-through rate and add-to-cart rate
Decision rule: keep the variant with at least 20% higher CTR after sufficient impressions.
```

## 10. Output Artifact Contracts

### 10.1 launch-war-room.html

Purpose:

- human-readable dashboard artifact
- first artifact opened by the user

Sections:

- product brief
- target platform and user segment
- opportunity score
- top 5 market findings
- top 5 customer pain points
- competitor price-band table
- positioning recommendation
- listing preview
- content hooks
- 7-day launch plan
- evidence confidence summary
- limitations

Rendering constraints:

- self-contained HTML
- no external JS dependency required
- usable in DeerFlow artifact preview
- link to source URLs when available

### 10.2 competitor-table.csv

Columns:

```csv
competitor_name,platform,product_url,price_low,price_high,key_claims,visible_strengths,visible_weaknesses,evidence_type,confidence,notes
```

Rules:

- if price is unavailable, leave price fields empty and note limitation
- do not infer exact sales volume unless public source explicitly provides it

### 10.3 positioning-brief.md

Sections:

- category framing
- target segment
- primary purchase job
- core promise
- differentiators
- reasons to believe
- objections and answers
- risks
- validation plan

### 10.4 listing-pack.md

Sections:

- title options
- short title options
- selling-point bullets
- product detail page structure
- image/module copy suggestions
- FAQ
- customer-service objection handling

### 10.5 content-pack.md

Sections:

- short-video hooks
- 3 short-video scripts
- livestream talk track
- Xiaohongshu-style notes
- creator brief
- comment reply bank

### 10.6 launch-calendar.csv

Columns:

```csv
day,objective,experiment,asset,channel,metric_to_collect,decision_rule,owner,expected_output
```

Rules:

- metrics should be "to collect", not invented existing metrics
- plan should be realistic for a small seller or student prototype

### 10.7 review-insights.json

Optional but recommended.

Schema:

```json
{
  "pain_points": [
    {
      "theme": "Leakage during commute",
      "customer_words": ["leaks in bag", "lid not tight"],
      "evidence_type": "observed_public",
      "confidence": "medium",
      "source_ids": ["ev_001", "ev_002"]
    }
  ],
  "positive_triggers": [],
  "purchase_objections": [],
  "copy_bank": []
}
```

## 11. Frontend Spec

### 11.1 MVP UI

Add an EcomLaunch conversational entry page or mode. Do not make the primary experience a long structured form.

Recommended implementation path:

- reuse the existing chat UI and input box
- route users through the existing custom-agent chat path, such as `/workspace/agents/ecom-launch/chats/[thread_id]`
- pass `agent_name: "ecom-launch"` in runtime context
- default this entry to Ultra mode when possible so `subagent_enabled=true`
- keep file uploads available through the existing upload flow
- show EcomLaunch-specific welcome copy and examples, not a field-by-field wizard

Primary interaction:

```text
User: 我想做一个通勤咖啡杯新品，目标淘宝和小红书，价格 99-199，帮我做上市方案
EcomLaunch: 开始补齐 launch brief / 搜索 / 调用 subagents / 生成 artifacts
```

If the user's first message is incomplete:

```text
User: 帮我做一个新品上市方案
EcomLaunch: 你想上市的产品或类目是什么？给我一个产品 idea、类目、链接，或上传产品说明即可。
```

This uses DeerFlow's existing `ask_clarification` path rather than a frontend form:

```text
lead agent decides required info is missing
-> calls ask_clarification
-> ClarificationMiddleware converts it to a tool message and ends the run
-> frontend renders assistant:clarification
-> user replies in the same thread
-> next run continues with the accumulated conversation
```

### 11.2 Prompt Template

The EcomLaunch agent should not rely on a generated form prompt. It should use the `ecom-launch` skill and custom-agent SOUL/config to extract a launch brief from normal conversation.

The internal brief schema should still be explicit:

```text
- Product/category:
- Product URL:
- Target platform:
- Target customer:
- Price range:
- Constraints:
- Competitor links:
- Uploaded files:
- Desired outputs:
```

For an incomplete brief, ask at most one clarification question at a time. Minimum required information before research:

- product idea, product category, product URL, or uploaded product description

All other fields can be inferred as assumptions when the task can still proceed.

The persistent agent instruction should include:

```text
You are EcomLaunch, a conversational ecommerce new-product launch copilot.
Do not force users through a long form.
Extract the launch brief from the conversation.
If the product/category is missing, ask one clarification question with ask_clarification.
Use public data and uploaded files only.
Do not invent private merchant metrics.
Create the required artifacts under /mnt/user-data/outputs and call present_files.
```

### 11.3 Artifact Experience

MVP:

- rely on current artifact list/detail UI
- generate `launch-war-room.html` as main dashboard

Post-MVP:

- parse `evidence-ledger.json`, `competitor-table.csv`, `launch-calendar.csv`
- render native React dashboard:
  - opportunity score
  - evidence confidence cards
  - competitor table
  - action plan
  - content assets

## 12. Backend / Config Spec

### 12.1 Config Changes

Add custom subagents under `config.yaml`:

```yaml
subagents:
  custom_agents:
    market-scout:
      description: "Search public ecommerce market signals, competitors, pricing, product pages and trend content"
      system_prompt: |
        You are an ecommerce market scout. Use public web information only.
        Find competitors, price bands, product claims, category trends, and visible market patterns.
        Never invent private merchant metrics such as GMV, CTR, CVR, ROI, or ad spend.
        Every finding must include evidence_type and source.
      tools:
        - web_search
        - web_fetch
        - image_search
        - read_file
        - write_file
      skills:
        - ecom-launch

    review-miner:
      description: "Extract customer pain points, objections, positive triggers and unmet needs from public reviews and Q&A"
      system_prompt: |
        You are a review and VOC analyst for ecommerce.
        Analyze public reviews, Q&A, forum discussions, and uploaded review files.
        Cluster complaints, praise, usage scenarios, and purchase objections.
        Mark whether each insight is public evidence, uploaded evidence, or estimated.
      tools:
        - web_search
        - web_fetch
        - read_file
        - write_file
      skills:
        - ecom-launch

    positioning-strategist:
      description: "Create ecommerce product positioning, opportunity score, target segment and validation hypotheses"
      system_prompt: |
        You are an ecommerce positioning strategist.
        Convert evidence into a focused product position, target segment, core promise,
        differentiators, risks, and validation hypotheses.
      tools:
        - read_file
        - write_file
        - web_search
        - web_fetch
      skills:
        - ecom-launch

    listing-copywriter:
      description: "Generate ecommerce listing titles, product selling points, detail page copy, FAQ and objection handling"
      system_prompt: |
        You are an ecommerce listing and conversion copywriter.
        Generate platform-aware titles, bullets, selling points, FAQ, objection handling,
        short video hooks, and livestream talk tracks based on verified insights.
      tools:
        - read_file
        - write_file
        - web_search
        - web_fetch
      skills:
        - ecom-launch

    content-planner:
      description: "Create short-video scripts, livestream talk tracks, social posts and creator briefs"
      system_prompt: |
        You are an ecommerce content planner.
        Produce conversion-oriented content assets using customer language and verified market insights.
      tools:
        - read_file
        - write_file
        - web_search
        - web_fetch
      skills:
        - ecom-launch

    launch-planner:
      description: "Create a 7-day ecommerce launch test plan with hypotheses, metrics and decision rules"
      system_prompt: |
        You are an ecommerce launch planner.
        Create practical launch experiments when private performance data is unavailable.
        Use testable hypotheses, required data to collect, success metrics, and decision rules.
      tools:
        - read_file
        - write_file
      skills:
        - ecom-launch

    evidence-checker:
      description: "Audit ecommerce recommendations for evidence quality and unsupported private metric claims"
      system_prompt: |
        You are an evidence checker.
        Check whether final claims are supported by observed public data, uploaded data, datasets, or estimates.
        Flag unsupported claims and remove invented private ecommerce metrics.
      tools:
        - read_file
        - write_file
      skills:
        - ecom-launch
```

### 12.2 Skill Enablement

Ensure the `ecom-launch` skill is discoverable and enabled.

Depending on existing skill settings, this may require:

- creating `skills/custom/ecom-launch/SKILL.md`
- enabling the skill in extensions config if skills are filtered by enabled state

### 12.3 No Runtime Rewrite

The MVP should not rewrite:

- LangGraph-compatible thread run APIs
- `RunManager`
- `StreamBridge`
- `SubagentExecutor`
- `present_files`
- artifact router

The system should ride on the existing DeerFlow runtime.

## 13. Development Plan

### Milestone 1: Product Protocol

Deliverables:

- `docs/plans/ecom-launch-agent-spec.md`
- `skills/custom/ecom-launch/SKILL.md`
- custom subagents in `config.yaml`

Acceptance:

- DeerFlow prompt lists `ecom-launch` as an available skill
- Ultra mode exposes custom subagents in task tool descriptions
- a manual chat prompt can invoke the launch workflow

### Milestone 2: Artifact-First MVP

Deliverables:

- lead prompt template for EcomLaunch tasks
- sample product launch run
- required output files generated under `/mnt/user-data/outputs`
- `present_files` called successfully
- manual run materials under `docs/ecom-launch/`:
  - `README.md`
  - `manual-run-prompt.md`
  - `demo-brief.portable-coffee-tumbler.json`
  - `subagents.ecom-launch.yaml`

Acceptance:

- generated artifact list includes all required MVP files
- `launch-war-room.html` opens in artifact preview
- evidence ledger exists and uses required schema
- no forbidden private metric claim appears without uploaded evidence

### Milestone 3: Conversational Frontend Entry

Deliverables:

- EcomLaunch entry page or mode using the existing chat UI
- custom agent route/context, for example `agent_name: "ecom-launch"`
- EcomLaunch welcome examples and empty-state copy
- `ask_clarification`-based brief completion
- submit through existing thread mechanism

Acceptance:

- user can start a launch task without writing a manual prompt
- user can give an incomplete request and receive a targeted clarification question
- task defaults to Ultra/subagent-enabled mode
- uploaded files are included in the task

### Milestone 4: Native Dashboard

Deliverables:

- parse key output files
- render opportunity score, competitor table, evidence cards, and launch calendar

Acceptance:

- dashboard renders without relying only on Markdown
- unsupported/estimated claims are visually marked
- user can download raw artifacts

## 14. Evaluation Criteria

### 14.1 Product Quality

Good result:

- looks like an ecommerce launch operating package
- recommendations are actionable
- includes source-backed evidence
- acknowledges private-data limitations
- provides next-step experiments

Bad result:

- generic market research essay
- fake GMV/ROI/CVR
- unsupported sales claims
- no concrete listing/content outputs
- no launch plan

### 14.2 Agent Quality

Good result:

- lead agent decomposes work across subagents
- subagent outputs are integrated rather than pasted together
- evidence checker catches unsupported claims
- artifacts are complete and schema-valid

Bad result:

- only one long lead-agent answer
- subagents duplicate each other
- no evidence ledger
- final files missing

### 14.3 Technical Quality

Good result:

- uses existing DeerFlow APIs
- minimal runtime changes
- custom behavior lives in skill, config, and frontend product layer
- outputs remain compatible with existing artifact system

Bad result:

- forks runtime unnecessarily
- hardcodes one product category
- relies on fake mock data for final claims
- breaks generic DeerFlow workspace behavior

## 15. Demo Scenario

Recommended demo product:

```text
Portable leak-proof coffee tumbler for office commute and light outdoor use.
Target platforms: Taobao, Xiaohongshu, Douyin.
Target price: RMB 99-199.
Constraints: stainless steel, easy to clean, no electronics.
```

Why this scenario works:

- many public product pages and reviews exist
- user pain points are easy to understand
- content scripts are visually intuitive
- no private merchant data is required
- output can show ecommerce business thinking clearly

Expected demo outputs:

- visible competitor price band
- pain points like leakage, heat retention, cleaning, smell, portability
- product positioning around commute safety and easy-clean lid
- title and short-video hooks
- 7-day test plan for title, hook, price, and content angle

## 16. Open Questions

1. Should the first frontend version be a dedicated route or a mode inside the existing workspace?
2. Should the MVP support Chinese platforms first, English/Amazon first, or both?
3. Should public dataset support be included in MVP, or deferred until after search-based workflow works?
4. Should `launch-war-room.html` be generated by the agent, or should the frontend render a native dashboard from JSON outputs?

## 17. Recommended First Implementation Choice

For the fastest credible MVP:

1. support Chinese-language user input
2. use public web search as the main data source
3. generate self-contained HTML as the first dashboard
4. keep React dashboard as post-MVP
5. implement custom skill and subagents before touching frontend

This proves the differentiated agent behavior first, then turns it into a polished product UI.

## 18. Repository Strategy

Target repository:

```text
git@github.com:CheungkiCheung/EcomLaunch-Agent.git
```

Current local starting point:

```text
/Users/zhangqixiang/0_2实习/deepagents/deer-flow
```

The local directory is a DeerFlow source tree extracted from an archive, not an existing Git checkout. It should become the EcomLaunch Agent repository while preserving DeerFlow's structure enough that future maintainers can see the project is built on a real agent runtime rather than a small demo scaffold.

### 18.1 Initial Repository Principles

The first commit should include:

- DeerFlow base source
- this EcomLaunch spec
- original docs and examples that are still useful for understanding the runtime
- no local secrets
- no generated dependency directories
- no local runtime state

Ignored local files must stay ignored:

- `.env`
- `config.yaml`
- `extensions_config.json`
- `frontend/node_modules`
- `frontend/.next`
- `backend/.venv`
- `backend/.deer-flow`
- `logs`

### 18.2 Branding Strategy

Do not rename every `deerflow` package immediately.

Early MVP should preserve internal package names and runtime paths where they are part of the working system. Product branding should first happen in:

- README
- app title and navigation
- EcomLaunch entry page
- custom skill
- custom subagents
- artifact names
- demo scenario

Deep package renaming can be a later cleanup after the MVP works. Premature package renaming risks breaking imports, docs, scripts, Docker files, and LangGraph configuration.

### 18.3 Upstream-Aware Modification Rule

When implementing EcomLaunch:

- prefer additive changes over invasive runtime rewrites
- keep generic DeerFlow mechanisms generic
- put ecommerce behavior in `skills/custom/ecom-launch`, subagent config, prompt builder, and frontend product surfaces
- document any necessary runtime change with a reason in this spec or a follow-up plan

This keeps the project credible as a DeerFlow-based agent product and makes the diff easy to explain.

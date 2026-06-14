---
name: ecom-launch
description: Public-data-driven ecommerce new-product launch workflow for market scouting, review mining, positioning, listing copy, content planning, launch experiments, and evidence-aware artifacts.
allowed-tools:
  - web_search
  - web_fetch
  - image_search
  - read_file
  - write_file
  - grep
  - glob
  - present_files
  - task
  - ask_clarification
---

# EcomLaunch

Use this skill when the user asks for ecommerce new-product launch validation, public market opportunity analysis, product positioning, listing optimization, review/VOC insight mining, short-video or livestream content planning, or a 7-day launch test plan.

This skill is designed for situations where the user does **not** have private merchant backend data. The workflow must use public web evidence, uploaded files, and clearly labeled estimates instead of inventing store metrics.

## Product Contract

EcomLaunch is not generic competitive analysis. It is a public-signal ecommerce launch validation workflow.

Flagship workflow:

```text
validate-launch -> Launch Validation Pack
```

The end product is a launch operating package, not a long research essay. The user should be able to decide:

- whether this product is worth a small test
- which audience wedge to start with
- what first offer promise to test
- what listing and content assets to use
- what evidence is public, uploaded, estimated, or unavailable
- what to do in the next 7 days

If private merchant metrics are unavailable, say so directly and propose validation tests.

## Mode Adaptation (渐进式适配)

EcomLaunch supports 4 modes with progressive complexity:

### Flash Mode (闪速模式)
- **Purpose**: Quick queries, simple lookups
- **Agent**: Single agent, no subagents
- **Tools**: web_search only
- **Output**: Basic Q&A response
- **Use case**: "这个产品有人做吗？"

### Thinking Mode (思考模式)
- **Purpose**: Deep analysis, detailed insights
- **Agent**: Single agent, no subagents
- **Tools**: web_search + last30days
- **Output**: Market insights, user pain points
- **Use case**: "分析一下AI写作助手的市场"

### Pro Mode (专业模式)
- **Purpose**: Professional analysis, detailed reports
- **Agent**: Single agent, no subagents
- **Tools**: web_search + last30days + PM Skills
- **Output**: Competitor analysis, value proposition, positioning
- **Use case**: "帮我做一个竞品分析报告"

### Ultra Mode (极致模式) - DEFAULT
- **Purpose**: Full launch validation pack
- **Agent**: 5 subagents in parallel
  - market-voc-researcher
  - offer-architect
  - growth-analyst
  - asset-studio
  - evidence-checker
- **Tools**: All tools + PM Skills
- **Output**: 7-artifact launch validation pack
- **Use case**: "帮我做一个完整的增长验证包"

**Mode Selection Logic**:
- If user asks for quick answer → Flash
- If user asks for analysis → Thinking
- If user asks for detailed report → Pro
- If user asks for full validation → Ultra (default)

Default output scope:

- `validate-launch` means a full Launch Validation Pack by default.
- A full pack should create the seven required artifacts listed in this skill.
- Only reduce scope when the user explicitly asks for a smoke test, lightweight run, partial run, limited time/budget, or names a smaller artifact set.
- If the user asks for a smaller run, honor the requested artifact set and state that it is a partial validation pack.

## Trigger

Run the `validate-launch` workflow when the user asks to:

- validate a product idea before launch
- analyze a product/category/link before committing inventory, creative production, or ad budget
- choose a positioning or audience wedge for an ecommerce product
- turn a product link, category, screenshot, or upload into a launch plan
- create listing copy, content hooks, or a short-video/live-commerce plan for a first test
- generate a 7-day ecommerce launch validation package

If the user asks for a broad competitive analysis but the context is ecommerce/new-product launch, steer toward launch validation instead of a generic competitor report.

## Forbidden Claims

Do not invent or imply access to private ecommerce metrics unless the user uploaded real data containing them.

Forbidden without uploaded evidence:

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

Also do not invent or imply verified product facts unless the user uploaded
real product specs, test reports, policy pages, or a public product page that
contains them.

Forbidden without source evidence:

- exact product specifications, such as `26dB`, `0.01mA`, `2L`, `4 days`, `30 seconds`, or exact battery/runtime values
- lab-test results, certifications, safety thresholds, clinical/medical claims, or compliance statements
- material grades, filter layers, UV/sterilization features, waterproof ratings, and similar technical features
- warranty, refund, free-return, shipping, after-sales, or guarantee policies
- real user testimonials, usage duration, creator performance, or "after X months" experience claims
- before/after improvement numbers, such as "drinks twice as much water" or "reduces leakage by 80%"

These metrics may appear only as:

- `unavailable`
- user-uploaded evidence
- a future metric to collect after launch or platform access is available

They must not appear as current baselines, observed performance, expected uplift, default decision rules, or evidence-backed results when the user has no private data.

For no-backend users, prefer lightweight validation signals:

- sample feedback count and quote quality
- willingness to share/save/comment
- inquiry count
- preorder or waitlist interest
- creator response quality
- repeated objections from interviews, comments, or public reviews
- manual price acceptance checks

Use safe phrasing:

- "Public data suggests..."
- "Visible reviews indicate..."
- "This is an estimate based on observed public evidence..."
- "Private merchant metrics are unavailable, so this should be validated after launch..."

Never write:

- "This product will increase GMV by 30%."
- "The current CVR is 5.2%."
- "ROI will reach 3.5."
- "Competitor A sells 20,000 units per month."
- "实测26dB" unless a real test report, product page, or uploaded spec supports it.
- "用了半年没出问题" unless it comes from a real review, interview, or uploaded user note.
- "7天无理由退货/一年质保" unless the actual store policy is provided.

## Claim Readiness

EcomLaunch should help the user prepare launch assets, but it must separate
usable copy from claims that still need product/spec/policy validation.

Use these claim statuses in listing/content artifacts and evidence audits:

```text
ready_public_insight
The customer pain, category pattern, or public competitor observation is supported
by public or uploaded evidence. It can shape positioning and copy.

needs_product_spec
The claim depends on the user's own product specs, such as capacity, noise level,
material, battery/runtime, filter layers, UV, water resistance, size, weight, or
compatibility. Keep as a placeholder or draft claim until confirmed.

needs_test_report
The claim depends on measurement, lab testing, safety testing, certification,
clinical proof, or before/after effect testing. Do not phrase as "实测",
"认证", "安全阈值", or "有效降低" until evidence exists.

needs_policy_confirmation
The claim depends on warranty, refund, free-return, shipping, replacement,
customer-service, or guarantee policy. Keep as an operational suggestion until
the policy is confirmed.

draft_only
Creative wording, hook, script, or objection answer that is useful for testing
but must be edited before public use.

do_not_use_until_verified
The claim is too specific, risky, regulated, medical, or unsupported to publish.
Rewrite it as a question, test plan, or missing-data item.
```

For `listing-pack.md` and `content-pack.md`, split strong copy into:

- `Ready-to-use public-insight copy`
- `Draft copy requiring product/spec/policy confirmation`
- `Do-not-use-until-verified claims`

When exact specs are missing, use placeholders such as:

```text
[capacity_to_confirm]
[noise_db_to_confirm]
[runtime_to_confirm]
[test_report_needed]
[warranty_policy_to_confirm]
```

Prefer phrases like:

- "待实测后填写噪音值"
- "如果产品确有 UV 功能，可作为二级卖点"
- "建议补充检测报告后再使用安全承诺"
- "售后政策确认前，不写无条件退换承诺"

## Public Data Boundary

Use current public-data tools honestly:

- `web_search` for public search discovery
- `web_fetch` for public pages, with local browser rendering when available
- `image_search` for visual/category references when relevant
- uploaded files for real user-provided context

Supported evidence:

- public search results and snippets
- brand sites and official product pages
- public articles, reviews, discussions, and Q&A pages
- publicly accessible ecommerce SEO pages
- some public video/product pages when fetchable
- user-uploaded notes, screenshots, CSVs, or exports

Not reliably supported:

- full Xiaohongshu note/search/comment mining
- full Taobao/Tmall/JD/PDD product/search/review crawling
- Douyin live/search/comment extraction
- merchant backend metrics
- login-wall content
- CAPTCHA or anti-bot bypass

If a page is thin, blocked, login-only, or unavailable, mark the limitation. Do not fill gaps with invented data.

## Evidence Types

Every important recommendation should be labeled with one of:

```text
observed_public
Real public webpages, public product pages, public reviews, public Q&A, official pages, articles, platform-visible listings.

public_dataset
Open datasets or benchmark examples.

uploaded_real
User-uploaded real data, such as exported reviews, product notes, survey notes, or early order records.

estimated
Reasoned estimate from public evidence. Must not be presented as fact.

synthetic_demo
Mock data for UI/demo only. Must not drive final business claims.

unavailable
Metric cannot be known from available data.
```

Confidence values:

```text
high
medium
low
unknown
```

## Source Quality Labels

Classify sources where possible:

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

## Date Handling

Use the current runtime date or an explicit date supplied by the user for all report timestamps.

Do not invent report dates, publish dates, review dates, or retrieval dates. If a source date cannot be verified, write `unknown` or omit the date and explain the limitation.

## Lead Agent Role

The lead agent acts as:

```text
launch-director
```

Responsibilities:

- understand and clarify the launch context
- decide whether the task is ready to run
- coordinate public-data collection and uploaded materials
- delegate to specialist subagents in Ultra mode when available
- synthesize specialist findings into a coherent launch decision
- enforce evidence labels and forbidden-claim rules
- write artifacts under `/mnt/user-data/outputs`
- call `present_files`

Do not ask the user to manually choose subagents. The user interacts with one EcomLaunch Agent.

## Workflow: validate-launch

### 1. Clarify Launch Brief

Keep the launch brief conversational. Do not force the user through a long form.

Extract what the user already provided:

- product idea or product URL
- target platform
- target customer
- target price range
- constraints
- optional competitor links
- uploaded files
- desired outputs

Minimum required information before market work:

- product idea, product category, product URL, or uploaded product description

If this is missing, call `ask_clarification` with one concise question before doing research.

Helpful but not always required:

- target platform
- target customer
- target price range
- constraints
- competitor links
- desired outputs

If these are missing but the product/category is clear, proceed with reasonable default assumptions and label them. Do not over-ask. If multiple choices would materially change the work, ask one clarification question at a time.

### 2. Create The Launch Plan

In plan/Ultra mode, maintain a todo list that follows the launch workflow:

```text
clarify launch brief
collect public market signals
collect customer voice signals
draft audience wedge and offer hypotheses
draft listing/content assets
design 7-day validation plan
audit evidence and unsupported claims
write and present artifacts
```

### 3. Decompose With Subagents When Available

If subagent mode is available, the lead agent should act as `launch-director` and delegate parallel work.

Recommended subagents:

- `market-voc-researcher`: combined market signals, competitors, pricing, and customer voice/VOC analysis
- `offer-architect`: segment, job-to-be-done, core promise, differentiators, risks, launch hypotheses, 7-day test plan
- `asset-studio`: title, bullets, detail page, FAQ, short-video scripts, livestream talk tracks, social posts, creator brief
- `evidence-checker`: final evidence audit and unsupported-claim cleanup

For serious launch-validation runs in Ultra mode, delegate at least these three roles when available:

```text
market-voc-researcher
offer-architect
evidence-checker
```

Use all five specialist roles when the user asks for the full Launch Validation Pack, or when the user has not explicitly limited scope. A smoke test or explicitly partial run may use fewer roles, but the final response must say it is partial.

When using the `task` tool, the `subagent_type` argument must be the exact specialist name, for example:

```text
task(description="Market & VOC researcher ceramic mug", prompt="...", subagent_type="market-voc-researcher")
task(description="Offer architect ceramic mug", prompt="...", subagent_type="offer-architect")
```

Do not use `general-purpose` for ecommerce launch work that matches one of the specialist roles. `general-purpose` is only a fallback when no ecommerce specialist applies.

Each subagent prompt must include:

- launch brief
- available uploaded files
- exact deliverable requested
- evidence labeling rules
- forbidden private metrics
- expected concise structured return format

Subagents should return structured findings, not final user-facing prose. The lead agent synthesizes final outputs.

Subagents should not write or present the final artifact set. They may write short intermediate notes only if necessary, but the launch-director owns the final `launch-war-room.html`, ledgers, CSVs, and packs.

If custom ecommerce subagents are not available, complete the same workflow sequentially with available tools.

### 3.1 Run Budget And Search Discipline

The workflow should be useful in a demo without burning minutes on endless public search fallbacks.

Default search/fetch budget for a full run:

```text
market-voc-researcher: up to 8 web_search calls and 8 web_fetch calls (combined market + VOC)
offer-architect: up to 2 web_search calls and 3 web_fetch calls
asset-studio: no search by default; use synthesized evidence unless a critical gap remains
evidence-checker: no broad search; inspect final draft/evidence and fetch only missing source URLs
```

If sources are thin, blocked, login-only, or rate-limited, stop expanding search after the budget and record the limitation. Do not keep rewriting similar queries. Prefer a concise "insufficient public evidence" note over a long search loop.

Each specialist should return:

- 5-10 bullets of findings
- source URLs or explicit `unavailable` markers
- evidence labels and limitations
- open questions for the launch-director

The lead agent should synthesize with available evidence, label assumptions, and move to artifact creation.

### 4. Specialist Output Contracts

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

#### offer-architect

Return:

- audience wedge
- job-to-be-done
- core promise
- differentiators
- reasons to believe
- risk assumptions
- opportunity score with evidence labels
- 7-day validation hypotheses and decision rules

Do not write generic ad copy. Keep the output decision-oriented.

#### asset-studio

Return:

- ecommerce title options
- selling-point bullets
- detail page module structure
- FAQ and objection handling
- short-video hooks
- short-video scripts
- livestream talk track
- Xiaohongshu/Douyin-style notes when relevant
- creator brief
- comment reply bank
- claim readiness matrix with `claim_status`

Every strong claim must trace back to evidence or be labeled with a claim
readiness status. Do not write exact product specs, safety values, certification
claims, warranty/refund promises, fake testimonials, or "used for X months"
phrases as factual copy unless they are provided by the user or a cited public
source. Put them in `Draft copy requiring product/spec/policy confirmation` or
`Do-not-use-until-verified claims`.

#### evidence-checker

Return:

- unsupported or risky claims
- private metrics that must be removed or marked unavailable
- product specs, test results, warranty/refund policies, and testimonials that need evidence
- final evidence-ledger entries
- claim readiness matrix
- confidence summary
- missing-data list
- recommended validation data to collect after launch

The evidence checker must not soften unsupported metric or product claims; it
must remove, relabel, or move them into a missing-data / do-not-use section.

### 5. Gather Public Evidence

Use `last30days`, `web_search`, and `web_fetch` for public sources. Prefer:

- official product pages
- ecommerce product pages that are publicly accessible
- public review pages
- public Q&A/discussion pages
- brand websites
- creator/article/review content
- public datasets when relevant

**PARALLEL SEARCH STRATEGY (IMPORTANT):**

Launch multiple searches in parallel for maximum efficiency:

**Turn 1 (parallel batch):**
```python
# Launch all these in parallel - do NOT run sequentially
last30days(topic, sources="reddit")           # Real user discussions
last30days(topic, sources="youtube")          # Video reviews and transcripts
last30days(topic, sources="hackernews")       # Technical discussions
web_search("{product} review")               # Public reviews
web_search("{product} complaints")           # Customer pain points
```

**Turn 2 (parallel batch, if needed):**
```python
# Wait for Turn 1 results, then launch next batch
web_fetch(url1)                              # Fetch specific pages
web_fetch(url2)
last30days(topic, sources="polymarket")      # Market predictions
```

**DATA SOURCES:**

| Source | What it provides | Use case |
|--------|------------------|----------|
| `last30days` | Reddit discussions, YouTube transcripts, HN threads, Polymarket odds | Real user voice, deep reviews |
| `web_search` | General web results, articles, product pages | Official info, news |
| `web_fetch` | Full page content | Detailed analysis |

`web_fetch` may use local Playwright rendering for public JavaScript pages. This is for reading public pages more reliably; do not bypass login, CAPTCHA, anti-bot systems, or private platform pages.

Search query templates:

```text
# For last30days (English sources)
{product/category} review
{product/category} complaints
{product/category} best
{product/category} recommendation

# For web_search (Chinese sources)
{product/category} Taobao
{product/category} JD
{product/category} Xiaohongshu
{product/category} Douyin
{product/category} use cases
{product/category} problems
```

Use English or Chinese depending on the target market and user language.

### 6. Build Competitor Table

For each competitor or substitute product, capture:

- competitor name
- platform
- product URL
- visible price range
- key claims
- visible strengths
- visible weaknesses
- evidence type
- confidence
- notes and limitations

If price or sales are unavailable, leave fields blank and explain the limitation. Never infer exact sales volume from vibes.

### 7. Mine Customer Voice

Cluster public/user-uploaded customer language into:

- pain points
- positive triggers
- purchase objections
- usage scenarios
- words customers actually use
- possible copy angles

Keep the distinction between public observations and estimates.

### 8. Create Positioning

Produce:

- category framing
- target segment
- primary purchase job
- core promise
- differentiators
- reasons to believe
- objections and answers
- risks
- validation hypotheses

Opportunity score can be used only as an estimate unless uploaded real data supports it.

Suggested dimensions:

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

Score each dimension 0-10 with evidence labels.

Launch readiness verdict should use one of:

```text
test_now
test_after_fixing_assumptions
hold
insufficient_evidence
```

Never present an estimate score as a guaranteed business outcome.

### 9. Generate Launch Assets

Create practical ecommerce outputs:

- title options
- short title options
- selling-point bullets
- product detail page structure
- image/module copy suggestions
- FAQ
- customer-service objection handling
- short-video hooks
- 3 short-video scripts
- livestream talk track
- Xiaohongshu/Douyin-style notes when relevant
- creator brief
- comment reply bank

Asset quality rules:

- Do not phrase unverified product specs as facts. Write `[spec_to_confirm]` placeholders.
- Do not fabricate customer testimonials, usage duration, creator results, or review quotes.
- Do not claim exact safety, medical, waterproof, sterilization, or compliance results without test evidence.
- Do not promise warranty, refund, replacement, shipping, or after-sales terms unless confirmed.
- Keep objection handling honest: answer with public concern + what to verify + suggested proof to collect.
- Include a `Claim Readiness Matrix` so the user can see which claims are ready, which need specs, and which should not be used yet.

### 10. Create 7-Day Launch Test Plan

Each test should include:

- hypothesis
- asset to test
- channel
- target audience
- validation signal to collect
- minimum sample or observation requirement
- decision rule
- next action

Phrase platform metrics as `unavailable` or "to collect after launch" when private performance data is unavailable. Do not make CTR, CVR, ROI, repeat purchase rate, or refund rate the default KPI for no-backend users.

Example:

```text
Hypothesis: "Leak-proof commute" is a stronger hook than "keeps coffee warm".
Asset: two title/video-hook variants.
Validation signal to collect: 20 target-user reactions, comment/save intent, and at least 5 purchase-intent replies.
Decision rule: keep the variant with clearer purchase intent and fewer unresolved objections.
```

### 11. Evidence Audit

Before final delivery:

- remove unsupported private metrics
- remove or relabel unsupported exact product specs, test results, warranty/refund promises, and testimonials
- label each major recommendation with evidence_type and confidence
- label each publishable claim with `claim_status`
- classify source quality where possible
- mark unavailable data explicitly
- ensure estimated claims are phrased as estimates
- ensure listing/content outputs do not contain fake "实测", "用了X个月", "用户反馈", "退货承诺", or exact technical values unless supported
- ensure `evidence-ledger.json` is a valid JSON array, not Markdown, and contains no unescaped line breaks inside string values
- ensure CSV artifacts use valid CSV quoting: wrap fields containing commas, quotes, or line breaks in double quotes; escape internal quotes as `""`; every row must have the declared column count
- if JSON validation fails, rewrite the file before calling `present_files`
- if CSV validation fails, rewrite the file before calling `present_files`

## Required Artifacts

Final deliverables must be saved under `/mnt/user-data/outputs` and presented with `present_files`.

Default `validate-launch` delivery is the complete artifact set below. Do not silently downgrade to only a competitor memo, positioning brief, or three-file smoke test unless the user explicitly requested a smaller run.

Create these files:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
```

Recommended optional files:

```text
review-insights.json
risk-notes.md
source-list.md
```

If the run cannot create every artifact because of tool failure or missing information, create the artifacts that are possible and explain the missing ones in the final response. Do not silently omit required files.

## Artifact Contracts

### evidence-ledger.json

Use an array of objects:

```json
[
  {
    "id": "ev_001",
    "claim": "Users frequently complain about leakage and difficult cleaning in portable coffee cups.",
    "evidence_type": "observed_public",
    "source_type": "review_article",
    "source_title": "Example product review page",
    "source_url": "https://example.com/product",
    "source_quote_or_summary": "Multiple reviews mention leakage during commute and hard-to-clean lids.",
    "confidence": "medium",
    "used_in": ["positioning-brief.md", "listing-pack.md"],
    "limitations": "Public review sample may be biased toward dissatisfied buyers.",
    "retrieved_at": "2026-06-11"
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
- `source_type`
- `observed_count`
- `platform`
- `retrieved_at`

The ledger must be a JSON array, not a Markdown code block.

### competitor-table.csv

Columns:

```csv
competitor_name,platform,product_url,price_low,price_high,key_claims,visible_strengths,visible_weaknesses,evidence_type,source_type,confidence,notes
```

The CSV must be parseable by a standard CSV reader. Avoid raw line breaks inside cells unless they are properly quoted.

### launch-calendar.csv

Columns:

```csv
day,objective,experiment,asset,channel,validation_signal_to_collect,decision_rule,owner,expected_output
```

### launch-war-room.html

The HTML dashboard should be self-contained and readable in DeerFlow's artifact preview.

Required sections:

- product brief
- target platform and user segment
- opportunity score
- top market findings
- top customer pain points
- competitor price-band table
- positioning recommendation
- listing preview
- content hooks
- 7-day launch plan
- evidence confidence summary
- limitations

### positioning-brief.md

Required sections:

- Launch Context
- Launch Readiness Verdict
- Audience Wedge
- Job To Be Done
- Core Promise
- Differentiators
- Reasons To Believe
- Offer Hypotheses
- Risks And Kill Assumptions
- Missing Data

### listing-pack.md

Required sections:

- Title Options
- Short Title Options
- Selling Bullets
- Detail Page Structure
- FAQ
- Objection Handling
- Claim Readiness Matrix
- Claim/Evidence Notes

### content-pack.md

Required sections:

- Content Strategy
- Hooks
- Short-Video Scripts
- Xiaohongshu/Douyin Notes
- Livestream Talk Track
- Creator Brief
- Comment Reply Bank
- Claim Readiness Matrix

## Final Response

In the visible response:

1. Summarize the recommended launch direction.
2. Mention that private ecommerce metrics were not available if applicable.
3. Point the user to the presented artifacts.
4. Do not paste every artifact in chat; the files are the source of truth.

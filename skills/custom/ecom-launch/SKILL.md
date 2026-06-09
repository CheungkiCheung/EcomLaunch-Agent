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
---

# EcomLaunch

Use this skill when the user asks for ecommerce new-product launch planning, public market opportunity analysis, product positioning, listing optimization, review/VOC insight mining, short-video or livestream content planning, or a 7-day launch test plan.

This skill is designed for situations where the user does **not** have private merchant backend data. The workflow must use public web evidence, uploaded files, and clearly labeled estimates instead of inventing store metrics.

## Core Principle

EcomLaunch is not generic competitive analysis. It turns public market signals into an ecommerce launch operating package:

1. Market and competitor scan
2. Public review/VOC mining
3. Product positioning
4. Listing and conversion copy
5. Content launch assets
6. 7-day launch testing plan
7. Evidence ledger and limitations

If private merchant metrics are unavailable, say so directly and propose validation tests.

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

## Date Handling

Use the current runtime date or an explicit date supplied by the user for all report timestamps.

Do not invent report dates, publish dates, review dates, or retrieval dates. If a source date cannot be verified, write `unknown` or omit the date and explain the limitation.

## Workflow

### 1. Clarify Launch Brief

Extract or ask for:

- product idea or product URL
- target platform
- target customer
- target price range
- constraints
- optional competitor links
- uploaded files
- desired outputs

If enough information is present, proceed. Do not over-ask.

### 2. Decompose With Subagents When Available

If subagent mode is available, the lead agent should act as `launch-director` and delegate parallel work.

Recommended subagents:

- `market-scout`: public market, competitor, price, claim, and content-pattern scan
- `review-miner`: review/VOC pain points, praise, purchase objections, customer wording
- `positioning-strategist`: segment, job-to-be-done, core promise, differentiators, risks
- `listing-copywriter`: title, bullets, detail page, FAQ, customer-service scripts
- `content-planner`: short-video scripts, livestream talk tracks, social posts, creator brief
- `launch-planner`: 7-day launch test calendar and metrics-to-collect
- `evidence-checker`: final evidence audit and unsupported-claim cleanup

If subagent mode is unavailable, complete the workflow sequentially with available tools.

### 3. Gather Public Evidence

Use `web_search` and `web_fetch` for public sources. Prefer:

- official product pages
- ecommerce product pages that are publicly accessible
- public review pages
- public Q&A/discussion pages
- brand websites
- creator/article/review content
- public datasets when relevant

Do not bypass login, CAPTCHA, anti-bot systems, or private platform pages.

### 4. Build Competitor Table

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

### 5. Mine Customer Voice

Cluster public/user-uploaded customer language into:

- pain points
- positive triggers
- purchase objections
- usage scenarios
- words customers actually use
- possible copy angles

Keep the distinction between public observations and estimates.

### 6. Create Positioning

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

### 7. Generate Launch Assets

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

### 8. Create 7-Day Launch Test Plan

Each test should include:

- hypothesis
- asset to test
- channel
- target audience
- metric to collect
- minimum sample or observation requirement
- decision rule
- next action

Phrase metrics as "to collect" when private performance data is unavailable.

Example:

```text
Hypothesis: "Leak-proof commute" is a stronger hook than "keeps coffee warm".
Asset: two title/video-hook variants.
Metric to collect: CTR and add-to-cart rate.
Decision rule: keep the variant with at least 20% higher CTR after sufficient impressions.
```

## Required Artifacts

Final deliverables must be saved under `/mnt/user-data/outputs` and presented with `present_files`.

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

## Artifact Contracts

### evidence-ledger.json

Use an array of objects:

```json
[
  {
    "id": "ev_001",
    "claim": "Users frequently complain about leakage and difficult cleaning in portable coffee cups.",
    "evidence_type": "observed_public",
    "source_title": "Example product review page",
    "source_url": "https://example.com/product",
    "source_quote_or_summary": "Multiple reviews mention leakage during commute and hard-to-clean lids.",
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

### competitor-table.csv

Columns:

```csv
competitor_name,platform,product_url,price_low,price_high,key_claims,visible_strengths,visible_weaknesses,evidence_type,confidence,notes
```

### launch-calendar.csv

Columns:

```csv
day,objective,experiment,asset,channel,metric_to_collect,decision_rule,owner,expected_output
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

## Final Response

In the visible response:

1. Summarize the recommended launch direction.
2. Mention that private ecommerce metrics were not available if applicable.
3. Point the user to the presented artifacts.
4. Do not paste every artifact in chat; the files are the source of truth.

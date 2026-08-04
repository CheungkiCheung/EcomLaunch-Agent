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

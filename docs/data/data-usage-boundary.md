# OpenSKU Data Usage Boundary

Date: 2026-06-27

Status: Phase 1 source of truth

## Core Boundary

Public datasets are benchmark fixtures. They let OpenSKU prove that the system can ingest ecommerce-shaped evidence, diagnose a launch stage, generate grounded artifacts, and avoid unsupported claims. They do not make OpenSKU a live merchant analytics platform.

## Allowed Claims

OpenSKU may claim:

- It can process real public ecommerce datasets.
- It can map order, review, product, search-relevance, and behavior signals into launch-stage decisions.
- It can generate evidence-ledger artifacts that cite dataset rows and fields.
- It can identify missing evidence and refuse to invent private metrics.
- It can produce repeatable benchmark cases from public fixtures.

OpenSKU may not claim:

- It knows a user's real GMV, CTR, CVR, ROI, refund rate, repeat purchase rate, ad spend, or margin without uploaded data.
- It can prove causal uplift from promotion changes using public benchmark rows alone.
- It can access or update live Amazon, Shopify, TikTok Shop, Douyin, Tmall, Meta Ads, or Google Ads data without connectors and credentials.
- It can infer private customer identity from anonymized public datasets.
- A launch calendar is optimal in the business sense unless it has live feedback and constraints from the user.

## Stage-Specific Evidence Rules

| Stage | Public Evidence Allowed | Decision Boundary |
|---|---|---|
| `idea_only` | Reviews, metadata, query relevance, attribute datasets | Can recommend research direction and claim risks. Cannot estimate launch revenue. |
| `supplier_sample` | Product metadata, MAVE-style attributes, review objections | Can check whether specs and claims are supported. Cannot prove manufacturing quality. |
| `pre_launch_test` | Search relevance, query classes, behavior-event fixtures | Can suggest test positioning and landing-page/listing experiments. Cannot claim statistically valid conversion without experiment data. |
| `soft_launch` | Olist-like orders, reviews, payments, delivery; RetailRocket/Taobao-like behavior events | Can diagnose stage movement and feedback signals. Cannot attribute improvement to ads or promotions without channel data. |
| `scale_iterate` | Larger order/behavior/recommendation fixtures | Can test loop logic, segmentation, and artifact validation. Cannot claim real business scaling success. |

## Private Data Intake Rule

If a user uploads merchant data, OpenSKU must label it separately from public fixtures:

```text
source_type: user_uploaded
owner: user
dataset_name: <user supplied>
allowed_use: this run only unless otherwise specified
known_limitations: <missing columns, unknown sampling, stale period, etc.>
```

If a run only uses public fixtures, every artifact should say:

```text
source_type: public_benchmark_fixture
not_a_live_merchant_integration: true
```

## Metric Rules

Metrics that may be copied from public datasets when present:

- review score.
- rating count.
- review count.
- order price.
- freight value.
- payment value.
- delivery timestamps.
- behavior event type.
- query-product relevance label.
- attribute evidence spans.

Metrics that must not be invented:

- GMV.
- CTR.
- CVR.
- ROI.
- ad spend.
- CAC.
- profit margin.
- refund rate.
- repeat purchase rate.
- verified uplift.
- live inventory.
- live ranking.

Derived metrics are allowed only when the formula is explicit and all input fields are present. Example: delivery delay can be computed from Olist delivered and estimated delivery timestamps. Example: conversion rate cannot be computed from WANDS relevance labels.

## Agent Artifact Requirements

Every OpenSKU artifact that uses public data should include:

- dataset name.
- source URL or local fixture id.
- component/table name.
- row id or evidence id when available.
- field names used.
- limitation note.

The evidence ledger validator in later phases should fail artifacts that:

- cite a dataset without a source.
- cite a private metric not present in inputs.
- treat public benchmark fixtures as current merchant telemetry.
- make exact product, policy, or compliance claims without supporting fields.

## Data Retention

Commit only tiny samples and generated schemas during Phase 1. Large raw datasets should live outside the repository or in ignored local storage, with download commands and checksums recorded in progress logs.

Recommended structure:

```text
data/opensku/samples/
data/opensku/schemas/
```

Large future downloads should use a separate ignored path such as:

```text
data/opensku/raw/
```

If raw downloads are added later, update `.gitignore` before ingestion.


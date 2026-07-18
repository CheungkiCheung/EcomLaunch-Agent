# OpenSKU Open Data Map

Date: 2026-06-27

Status: Phase 1 source of truth

## Position

OpenSKU uses public datasets as benchmark fixtures for an evidence-governed SKU launch loop. These datasets are not live merchant integrations, not private ad-platform exports, and not proof that OpenSKU can see real-time GMV, CTR, CVR, ROI, inventory, or channel attribution for a merchant.

The immediate data strategy is:

1. Use public ecommerce datasets to create repeatable launch-loop benchmark cases.
2. Preserve source, license, and stage boundaries for every dataset.
3. Keep live merchant integrations out of scope until a user explicitly uploads their own data or a proper connector exists.
4. Use generated sample and schema files as local evidence that the dataset is accessible and parseable.

## Current Local Evidence

Phase 1 has real sampled rows for these datasets:

| Dataset | Sample File | Schema File | Components Sampled | Rows |
|---|---|---|---|---:|
| Olist Brazilian E-Commerce | `data/opensku/samples/olist.jsonl` | `data/opensku/schemas/olist.schema.json` | orders, order_items, order_reviews, order_payments, products | 25 |
| Wayfair WANDS | `data/opensku/samples/wands.jsonl` | `data/opensku/schemas/wands.schema.json` | query, product, label | 15 |
| Amazon Reviews 2023 | `data/opensku/samples/amazon_reviews.jsonl` | `data/opensku/schemas/amazon_reviews.schema.json` | All_Beauty reviews, All_Beuty metadata | 10 |

Sampling command shape:

```bash
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset <dataset> --limit 5
```

## Dataset Map

| Dataset | Primary Source | OpenSKU Use | Fields Used | What It Can Prove | What It Cannot Prove | Stage Coverage | Phase 1 Status |
|---|---|---|---|---|---|---|---|
| Olist Brazilian E-Commerce Public Dataset | `https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce`; sampled through `https://github.com/olist/work-at-olist-data` | Post-order launch loop, delivery risk, review signal, product category performance, payment and freight context | `order_status`, purchase/delivery timestamps, `price`, `freight_value`, `payment_type`, `payment_value`, `review_score`, review text, product category and dimensions | Whether OpenSKU can reason over real anonymized order, payment, delivery, product, and review tables | Cannot prove ad attribution, margin, real-time sell-through, live inventory, or causal uplift | `soft_launch`, `scale_iterate` | Primary page verified; 5 components sampled |
| RetailRocket Ecommerce Dataset | `https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset` | Behavior-event benchmark for view, add-to-cart, transaction, availability and item-property changes | `visitorid`, `event`, `itemid`, transaction id, item property snapshots, category tree | Whether OpenSKU can detect funnel stage, behavioral traction, and product/category interest patterns from implicit feedback | Cannot prove marketing-channel source, profit, ad spend, or customer identity | `pre_launch_test`, `soft_launch` | Primary page verified; not locally sampled because Kaggle download requires subscription/API setup |
| Amazon Reviews 2023 | `https://amazon-reviews-2023.github.io/`; sampled through UCSD public download URLs | VOC mining, review objection clustering, rating context, metadata-driven positioning, product-page readiness | `rating`, review `title`, review `text`, `helpful_vote`, `verified_purchase`, `timestamp`, `asin`, metadata `title`, `description`, `features`, `price`, `store`, `average_rating`, `rating_number` | Whether OpenSKU can ground positioning and claim readiness in public review and metadata evidence | Cannot prove the user's product quality, private conversion rate, current Amazon listing status, or exact competitor sales | `idea_only`, `supplier_sample`, `pre_launch_test` | Primary page verified; review and metadata samples loaded |
| Amazon ESCI Shopping Queries | `https://github.com/amazon-science/esci-data` | Search-fit and query-product relevance benchmark | `query`, `query_id`, `product_id`, `product_locale`, `esci_label`, `product_title`, `product_description`, `product_bullet_point`, brand, color, source | Whether OpenSKU can judge query fit, substitutes, complements, and search-relevance risks | Cannot prove paid-search performance, keyword bid efficiency, or live ranking | `pre_launch_test` | Primary page verified; not sampled in Phase 1 because main tables are Parquet and require a larger ingestion path |
| Wayfair WANDS | `https://github.com/wayfair/WANDS` | Product search relevance in home/furniture categories | `query`, `query_class`, `product_name`, `product_class`, category hierarchy, `product_description`, `product_features`, ratings, review counts, relevance label | Whether OpenSKU can connect search demand, product attributes, and relevance labels | Cannot prove cross-market demand outside Wayfair-like home/furniture context or live marketplace ranking | `pre_launch_test` | Primary page verified; 3 components sampled |
| MAVE | `https://github.com/google-research-datasets/mave` | Attribute-value extraction, product-claim validation, spec readiness | product id, category, attribute keys, evidence values, paragraph ids and spans where available | Whether OpenSKU can validate structured product attributes and avoid unsupported spec claims | Cannot prove demand, conversion, or review sentiment; full text requires joining Amazon 2018 metadata | `supplier_sample`, claim readiness | Primary page verified; not locally sampled because Git LFS labels are very large and full version requires separate Amazon 2018 metadata access |
| Taobao User Behavior | `https://tianchi.aliyun.com/dataset/649?lang=en-us` | China ecommerce implicit feedback benchmark | user id, item id, category id, behavior type, timestamp after download | Whether OpenSKU can process large-scale behavior sequences and stage movement from views, carts, purchases, and favorites | Cannot prove public brand demand, ad attribution, or product content quality | `soft_launch`, `scale_iterate` | Primary page verified; not sampled because Tianchi download requires account/terms flow |
| TAOBAO-MM | `https://taobao-mm.github.io/`; `https://huggingface.co/datasets/TaoBao-MM/Taobao-MM` | Long-sequence recommendation and multimodal item embedding benchmark | anonymized user/item ids, click labels, user features, item features, behavior sequences, 128-dimensional multimodal embeddings | Whether OpenSKU can reason about recommendation-ready behavior and item embeddings at large scale | Cannot reveal raw item images/content; cannot prove merchant-specific launch outcome | `soft_launch`, `scale_iterate` | Primary page verified; Hugging Face access timed out in this environment, so no local sample yet |
| ShoppingMMLU / ChineseEcomQA / ShoppingComp / ShoppingBench / ECom-Bench | To be verified in Phase 2 | Supplemental shopping-agent and ecommerce-domain evaluation references | benchmark-specific questions, tool tasks, scoring rubrics, traces | Whether OpenSKU's agentic reasoning can be evaluated against external shopping-domain tasks | Cannot replace OpenSKU launch-case validation or real agent artifact validation | supplemental eval | Candidate set only; not counted as Phase 1 verified sources |

## Stage Support

| Stage | Best Public Fixtures | Why |
|---|---|---|
| `idea_only` | Amazon Reviews 2023, MAVE | Review/VOC and metadata can reveal user objections, language, categories, and claim/spec surfaces before the product has private data. |
| `supplier_sample` | MAVE, Amazon Reviews 2023 | Attribute evidence and product metadata help test whether a sample's claims are supportable and whether product copy overstates specs. |
| `pre_launch_test` | WANDS, Amazon ESCI, RetailRocket | Query-product relevance and behavior events can simulate search fit and early funnel response. |
| `soft_launch` | Olist, RetailRocket, Taobao User Behavior | Orders, reviews, delivery, payment, and behavior events support post-launch diagnosis without inventing ad metrics. |
| `scale_iterate` | Olist, RetailRocket, Taobao User Behavior, TAOBAO-MM | Larger behavioral and order datasets support repeat-loop diagnosis, not causal growth claims. |

## Decision

Phase 1 accepts Olist, WANDS, and Amazon Reviews 2023 as immediately sampleable fixtures. RetailRocket, Amazon ESCI, MAVE, Taobao User Behavior, and TAOBAO-MM remain first-class map entries, but they need either a larger ingestion path, Kaggle/Tianchi/Hugging Face setup, Git LFS handling, Parquet support, or manual terms acceptance before they can count as locally sampled datasets.

Phase 2 benchmark-case work should start from the three sampleable fixtures, then add the larger/manual sources only after their ingestion path has its own real validation log.


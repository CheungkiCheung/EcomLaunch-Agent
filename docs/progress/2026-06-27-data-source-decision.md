# 2026-06-27 - Phase 1 Data Source Decision

## Context

- Branch: `feature/ecom-launch-cockpit`
- Commit: `c85a39b`
- Goal: execute Phase 1 from `docs/plans/opensku-complete-execution-plan.md`.
- Scope: data strategy, open dataset map, license/use boundary, real public sample loading for the first sampleable fixtures.

## Thinking

Phase 1 matters because the project cannot honestly claim "adaptive SKU launch loop" if it only generates a seven-day plan from a prompt. The missing piece is evidence: real ecommerce-shaped rows, explicit data boundaries, and a repeatable way to turn public fixtures into benchmark cases.

The decision is to separate three categories:

1. Immediately sampleable fixtures: Olist, WANDS, Amazon Reviews 2023.
2. Verified but not yet locally sampled fixtures: RetailRocket, Amazon ESCI, MAVE, Taobao User Behavior, TAOBAO-MM.
3. Candidate eval references that need Phase 2 verification: ShoppingMMLU, ChineseEcomQA, ShoppingComp, ShoppingBench, ECom-Bench.

Alternatives rejected:

- Do not invent private metrics such as GMV, CTR, CVR, ROI, ad spend, or verified uplift.
- Do not use synthetic rows as Phase 1 acceptance evidence.
- Do not count Kaggle/Tianchi/Hugging Face datasets as locally ingested until a real sample command succeeds.
- Do not pretend public benchmark fixtures are live merchant integrations.

The project should present this honestly: OpenSKU can reason over public ecommerce evidence now, and later phases must prove real agent execution and artifact validation on top of these fixtures.

## Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Verified current branch and commit | `git branch --show-current && git rev-parse --short HEAD` | Branch `feature/ecom-launch-cockpit`, commit `c85a39b`. |
| 2026-06-27 | Verified WANDS primary source and license | `curl -L --fail --max-time 20 -s https://raw.githubusercontent.com/wayfair/WANDS/main/README.md`; `curl .../LICENSE` | README describes 42,994 products, 480 queries, 233,448 judgements; license is MIT. |
| 2026-06-27 | Verified Olist source pages | `curl -L --fail --max-time 20 -s https://raw.githubusercontent.com/olist/work-at-olist-data/master/README.md`; Kaggle page parse | GitHub README describes the relational ecommerce sample; Kaggle metadata describes 100k anonymized orders and CC BY-NC-SA 4.0. |
| 2026-06-27 | Verified RetailRocket source page | `curl -L --fail --max-time 20 -A 'Mozilla/5.0' -s https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset` | Kaggle metadata describes events, item properties, category tree, CC BY-NC-SA 4.0, and subscription download. |
| 2026-06-27 | Verified Amazon Reviews 2023 primary page and UCSD raw URLs | `curl -L --fail --max-time 20 -s https://amazon-reviews-2023.github.io/`; `curl -I https://mcauleylab.ucsd.edu/.../All_Beauty.jsonl.gz` | Official page lists review/meta downloads; UCSD All_Beauty review and metadata gz files returned HTTP 200. |
| 2026-06-27 | Verified Amazon ESCI primary source | `curl -L --fail --max-time 20 -s https://raw.githubusercontent.com/amazon-science/esci-data/main/README.md`; `curl .../LICENSE` | README lists query/product relevance fields and Apache-2.0 license. |
| 2026-06-27 | Verified MAVE primary source | `curl -L --fail --max-time 20 -s https://raw.githubusercontent.com/google-research-datasets/mave/main/README.md`; `curl .../LICENSE` | README describes attribute-value labels; license is CC BY-NC 4.0. |
| 2026-06-27 | Verified Taobao User Behavior primary page | `curl -L --fail --max-time 20 -s 'https://tianchi.aliyun.com/dataset/649?lang=en-us'` | Tianchi page is accessible and describes UserBehavior for implicit-feedback recommendation research. |
| 2026-06-27 | Verified TAOBAO-MM primary page | `curl -L --fail --max-time 25 -s https://taobao-mm.github.io/` | Official page describes long-sequence recommendation data, research-purpose use, Apache 2.0, and 139 GB download structure. |
| 2026-06-27 | Added TDD regression test for inspector core | `backend/tests/test_opensku_dataset_inspector.py` | First run failed because `scripts.opensku_data` did not exist. |
| 2026-06-27 | Implemented dataset sample inspector | `scripts/opensku_data/inspect_dataset_sample.py` | Stdlib-only CLI that loads real URL samples and writes sample/schema files. |
| 2026-06-27 | Fixed Python TLS validation path | `scripts/opensku_data/inspect_dataset_sample.py` | Initial real sample commands failed with `SSL: CERTIFICATE_VERIFY_FAILED`; script now uses an existing certifi CA file when present, else `/etc/ssl/cert.pem`, with verification still enabled. |
| 2026-06-27 | Ran inspector unit test | `cd backend && uv run pytest tests/test_opensku_dataset_inspector.py -q` | Passed: `2 passed, 1 warning in 0.11s`. |
| 2026-06-27 | Sampled Olist | `uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset olist --limit 5` | Passed; wrote 25 rows across 5 components. |
| 2026-06-27 | Sampled WANDS | `uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset wands --limit 5` | Passed; wrote 15 rows across 3 components. |
| 2026-06-27 | Sampled Amazon Reviews 2023 | `uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset amazon_reviews --limit 5` | Passed; wrote 10 rows across review and metadata components. |
| 2026-06-27 | Wrote data map | `docs/data/open-data-map.md` | Added source URL, fields used, proof boundary, cannot-prove boundary, stage support, and sampling status. |
| 2026-06-27 | Wrote license notes | `docs/data/dataset-licenses.md` | Added dataset license/usage notes and repository retention policy. |
| 2026-06-27 | Wrote usage boundary | `docs/data/data-usage-boundary.md` | Added allowed/forbidden claims, stage rules, metric rules, and artifact requirements. |
| 2026-06-27 | Validated generated JSON/JSONL | `uv run python - <<'PY' ... json.loads(...) ... PY` | All 3 schema JSON files parse; all 3 sample JSONL files parse. |

## Evidence

### Deliverables

```text
docs/data/open-data-map.md
docs/data/dataset-licenses.md
docs/data/data-usage-boundary.md
scripts/opensku_data/inspect_dataset_sample.py
backend/tests/test_opensku_dataset_inspector.py
data/opensku/samples/olist.jsonl
data/opensku/samples/wands.jsonl
data/opensku/samples/amazon_reviews.jsonl
data/opensku/schemas/olist.schema.json
data/opensku/schemas/wands.schema.json
data/opensku/schemas/amazon_reviews.schema.json
```

### Real Sample Commands

Command:

```bash
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset olist --limit 5
```

Output:

```text
dataset=olist
sample_path=data/opensku/samples/olist.jsonl
schema_path=data/opensku/schemas/olist.schema.json
component=orders rows=5 format=csv fields=customer_id, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date, order_id, order_purchase_timestamp, order_status
component=order_items rows=5 format=csv fields=freight_value, order_id, order_item_id, price, product_id, seller_id, shipping_limit_date
component=order_reviews rows=5 format=csv fields=order_id, review_answer_timestamp, review_comment_message, review_comment_title, review_creation_date, review_id, review_score
component=order_payments rows=5 format=csv fields=order_id, payment_installments, payment_sequential, payment_type, payment_value
component=products rows=5 format=csv fields=product_category_name, product_description_lenght, product_height_cm, product_id, product_length_cm, product_name_lenght, product_photos_qty, product_weight_g, product_width_cm
```

Command:

```bash
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset wands --limit 5
```

Output:

```text
dataset=wands
sample_path=data/opensku/samples/wands.jsonl
schema_path=data/opensku/schemas/wands.schema.json
component=query rows=5 format=csv fields=query, query_class, query_id
component=product rows=5 format=csv fields=average_rating, category hierarchy, product_class, product_description, product_features, product_id, product_name, rating_count, review_count
component=label rows=5 format=csv fields=id, label, product_id, query_id
```

Command:

```bash
uv run python scripts/opensku_data/inspect_dataset_sample.py --dataset amazon_reviews --limit 5
```

Output:

```text
dataset=amazon_reviews
sample_path=data/opensku/samples/amazon_reviews.jsonl
schema_path=data/opensku/schemas/amazon_reviews.schema.json
component=all_beauty_reviews rows=5 format=jsonl.gz fields=asin, helpful_vote, images, parent_asin, rating, text, timestamp, title, user_id, verified_purchase
component=all_beauty_metadata rows=5 format=jsonl.gz fields=average_rating, bought_together, categories, description, details, features, images, main_category, parent_asin, price, rating_number, store, title, videos
```

### File Counts

Command:

```bash
find data/opensku -type f -maxdepth 3 -print | sort | xargs -I{} sh -c 'printf "%s " "$1"; wc -l < "$1"' sh {}
```

Output:

```text
data/opensku/samples/amazon_reviews.jsonl       10
data/opensku/samples/olist.jsonl       25
data/opensku/samples/wands.jsonl       15
data/opensku/schemas/amazon_reviews.schema.json      290
data/opensku/schemas/olist.schema.json      451
data/opensku/schemas/wands.schema.json      215
```

### JSON Parse Check

Command:

```bash
uv run python - <<'PY'
from pathlib import Path
import json
for path in sorted(Path('data/opensku/schemas').glob('*.json')):
    json.loads(path.read_text())
    print('json-ok', path)
for path in sorted(Path('data/opensku/samples').glob('*.jsonl')):
    count = 0
    for line in path.read_text().splitlines():
        json.loads(line)
        count += 1
    print('jsonl-ok', path, count)
PY
```

Output:

```text
json-ok data/opensku/schemas/amazon_reviews.schema.json
json-ok data/opensku/schemas/olist.schema.json
json-ok data/opensku/schemas/wands.schema.json
jsonl-ok data/opensku/samples/amazon_reviews.jsonl 10
jsonl-ok data/opensku/samples/olist.jsonl 25
jsonl-ok data/opensku/samples/wands.jsonl 15
```

### Test Output

Command:

```bash
cd backend && uv run pytest tests/test_opensku_dataset_inspector.py -q
```

Output:

```text
..                                                                       [100%]
2 passed, 1 warning in 0.11s
```

Warning:

```text
LangChainPendingDeprecationWarning from langgraph.checkpoint.serde.encrypted
```

Assessment: external deprecation warning, not a Phase 1 blocker.

## Validation

Phase 1 acceptance criteria:

| Requirement | Evidence | Status |
|---|---|---|
| Each dataset has source URL | `docs/data/open-data-map.md` and `docs/data/dataset-licenses.md` list source URLs for all mapped datasets | Passed |
| Each dataset has license or usage note | `docs/data/dataset-licenses.md` | Passed |
| Each dataset has fields used | `docs/data/open-data-map.md` | Passed |
| Each dataset has what it can prove | `docs/data/open-data-map.md` | Passed |
| Each dataset has what it cannot prove | `docs/data/open-data-map.md`; `docs/data/data-usage-boundary.md` | Passed |
| Each dataset has stage support | `docs/data/open-data-map.md` | Passed |
| Docs state public datasets are benchmark fixtures, not live merchant integrations | `docs/data/open-data-map.md`; `docs/data/data-usage-boundary.md` | Passed |
| At least 5 dataset sources verified from primary pages | Olist, RetailRocket, Amazon Reviews 2023, Amazon ESCI, WANDS, MAVE, Taobao User Behavior, TAOBAO-MM | Passed |
| Real sample rows saved under `data/opensku/samples/` | Olist 25 rows, WANDS 15 rows, Amazon Reviews 10 rows | Passed |
| Schemas saved under `data/opensku/schemas/` | 3 schema files parse successfully | Passed |
| Log includes sample row counts and fields | This log includes command output and field lists | Passed |

What was not completed in Phase 1:

- RetailRocket was not sampled because Kaggle download requires subscription/API flow.
- Amazon ESCI was not sampled because main tables are Parquet and need a larger ingestion path.
- MAVE was not sampled because the label file is Git LFS backed and full text requires Amazon 2018 metadata access.
- Taobao User Behavior was not sampled because Tianchi requires account/terms flow.
- TAOBAO-MM was not sampled because Hugging Face access timed out in this environment and the full dataset is large.
- No live OpenSKU agent run was executed in this phase.

These are not blockers for Phase 1 because Phase 1 requires at least 5 verified primary sources and real samples for Olist, Amazon Reviews, and WANDS. They should become explicit ingestion tasks in later phases if needed.

## Decision

Phase 1 is complete.

Proceed to Phase 2: OpenSKU-Bench Case Schema.

The Phase 2 implementation should use the three sampleable fixtures first:

```text
olist
wands
amazon_reviews
```

Then add RetailRocket, Amazon ESCI, MAVE, Taobao User Behavior, and TAOBAO-MM only after separate real ingestion commands pass.

## Next

1. Create `evals/opensku/case_schema.json`.
2. Create `evals/opensku/README.md`.
3. Generate first benchmark cases from the sampled Olist, WANDS, and Amazon Reviews fixtures.
4. Add a validator that rejects cases without source dataset, stage, evidence fields, and forbidden metric boundaries.
5. Write the next progress log before marking Phase 2 complete.


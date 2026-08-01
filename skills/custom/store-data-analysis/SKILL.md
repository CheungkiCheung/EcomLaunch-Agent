---
name: store-data-analysis
description: Analyze user-uploaded ecommerce store CSV/XLSX data with deterministic inspection and read-only SQL, using optional explore, analyst, and verifier subagents for complex questions.
allowed-tools:
  - store_inspect_data
  - store_query_data
  - read_file
  - task
  - ask_clarification
---

# Store Data Analysis

Use this skill when the user uploads store, order, product, marketing, review, inventory, fulfillment, refund, or finance data and asks for analysis.

## Start From The User's Question

Do not force a fixed workflow. Match the execution to the question:

- One factual calculation: inspect if needed, query, answer.
- One focused diagnosis: inspect, run the minimum necessary queries, answer.
- Broad or multi-table diagnosis: delegate bounded exploration and independent analysis tasks, then synthesize.
- High-impact or suspicious result: ask `verifier` to independently recompute the core number.

Never require the user to choose a Subagent, table alias, SQL query, seller ID, or exact comparison window.

Treat a request that combines multi-table joins, a time-window comparison, and
contribution decomposition as a bounded `analyst` task. The Parent should not
repeat the same full calculation after delegation. For direct Parent analysis,
use at most one inspection and six focused queries per user turn, combining
related metrics in one SQL whenever possible.

## Data Contract

1. Call `store_inspect_data` before the first calculation on a new upload set.
2. Use the returned `alias` values as SQL table names.
3. Wrap Chinese or space-containing column names in double quotes.
4. Use `store_query_data` for every business metric and aggregation.
5. Treat the latest valid date in the uploaded data as the observation boundary, not today's date.
6. Check row grain before counting orders or summing order-level amounts.
7. State the exact comparison windows when the user asks about “最近”, “变差”, “上涨” or “下降”.

## Broad Diagnosis

For a broad question such as “最近店铺为什么变差了”:

1. Identify available outcome metrics from the uploaded columns.
2. Choose a primary observed outcome, such as paid revenue, paid order count, refund rate, fulfillment delay, traffic, conversion, inventory availability, or profit.
3. Compare a recent window with an equal-length prior window.
4. Decompose the change only by dimensions actually present in the data, such as product, category, channel, region, status, or campaign.
5. Check at least one alternative explanation or data-quality issue.
6. Separate confirmed changes from possible explanations.

Do not automatically analyze every possible dimension. Stop when the current question is answered or available data cannot distinguish further.

## Suggested Subagent Tasks

Use `explore` for tasks such as:

```text
检查当前上传文件的表、字段、粒度、时间范围、数据质量，以及可以可靠分析的经营指标。只返回影响当前问题的发现和限制。
```

Use `analyst` for one verifiable objective per task:

```text
使用 store_query_data 比较最近 14 天与此前 14 天的成交金额和去重订单数，并按商品分解下降贡献。披露窗口和订单去重口径。
```

Use `verifier` only when needed:

```text
独立复算 source result 中的核心窗口比较，检查订单粒度、重复求和、时间边界和结论措辞。只返回核验结果、差异和限制。
```

Subagents return concise findings to the Parent. They do not write the final user response and do not spawn more agents.

Keep specialist loops bounded:

- `explore`: inspect once, use at most two focused queries, then return.
- `analyst`: inspect once, use at most four queries and combine related metrics in one SQL when possible, then return.
- `verifier`: inspect once, independently recompute with at most three queries, then return a verification status.

If the query budget is exhausted, return the verified partial result and the exact unresolved limitation instead of repeating a similar tool call.

## Evidence Discipline

Use these labels in reasoning, even if the final answer is conversational:

- `observed`: directly computed from uploaded data.
- `possible_explanation`: consistent with the observed pattern but not proven causal.
- `unknown`: not identifiable from current fields.
- `data_quality_risk`: a duplicate, missing, grain, parsing, or coverage issue that can change the result.

Do not claim causal uplift or blame a seller, carrier, campaign, or product without an appropriate comparison design.

## Final Response

Answer in the user's language. For Chinese users, prefer compact Chinese prose with:

- the main confirmed change;
- two to five decisive numbers;
- the most important limitation or alternative explanation;
- one practical next analysis or data request.

Do not paste raw tool JSON or SQL unless the user explicitly asks for it.

# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: rc2-rerun-opensku-prelaunch-001
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 685bd73d-f204-43e4-9d74-9d0cc086435c
- thread_id: opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156
- user_id: e5d71217-3b98-4fa5-94c8-e921911a45a3
- model_provider: deepseek
- model_name: deepseek-v4-flash
- reasoning_effort: medium
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: true
- is_plan_mode: false
- opensku_benchmark_fixture_mode: true
- disable_external_search: true
- run_status: success
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/uploads/opensku-case.json",
    "size_bytes": 2412,
    "sha256": "efa9772e3c02565c4b7e35bf07e035851d74f109a9a08462bcb9402988ef3978"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 778,
    "sha256": "26be7e016bd6ab8ed29968e614722e59135bf62818a3df768a9a5b6d4da772d4"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'grep', 'read_file', 'task', 'task', 'task', 'task', 'task', 'write_opensku_artifact_bundle', 'validate_opensku_artifacts', 'present_files']
- external_search_tool_calls: []
- knowledge_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/docs/knowledge/opensku
- injected_knowledge_patterns: [{"id": "kp_0009", "type": "pitfall", "maturity": "verified", "stage_matches": ["idea_only", "supplier_sample", "pre_launch_test", "soft_launch", "scale_iterate"], "occurrence_count": 17, "statement": "Do not convert public fixtures or public review language into private commerce metrics.", "scope": "workflow", "evidence_ids": ["EVID-004"], "source_case_ids": ["batch-live-5stage-opensku-idea-001", "batch-live-5stage-opensku-softlaunch-001", "batch-live-5stage-opensku-supplier-001", "batch-live-smoke-opensku-idea-001", "batch-live-stage2-opensku-prelaunch-002", "batch-live-stage2-opensku-softlaunch-002", "batch-live-stage2-opensku-supplier-002", "batch-live-stage2-rerun-opensku-scale-002", "live-decision-taxonomy-prelaunch-002", "live-demo-portable-coffee-tumbler-001-bundle-writer", "live-demo-portable-coffee-tumbler-001-bundle-writer-final-check", "live-knowledge-injection-opensku-idea-002", "live-knowledge-injection-prelaunch-002", "live-knowledge-injection-v2-opensku-idea-002", "opensku-idea-002", "opensku-prelaunch-001", "opensku-scale-001"], "source_run_ids": ["07e9f507-a291-47d6-820b-c2d3f9662abe", "1992db1e-6cfc-4c84-b477-8711df951af6", "1b509691-6fc1-4df6-949b-0d0214349c76", "350ecafc-e314-4329-9c2f-c0b28787e273", "3673f3a9-6c51-4ed6-bb12-760f4d5bcbf1", "37cfe736-fb6c-410c-a070-fed13e6957fb", "4f73454f-befc-4d04-a719-33942d1cdc74", "6a1e641a-3990-4929-a6e9-90bb3638beb3", "72450b53-1951-4961-a1f5-14f49b3c04e3", "859ef561-d6fe-4827-a506-6ce7d5b65716", "9bdf284d-addd-4e31-abae-319ffe3f1c35", "a5294739-b72f-43ce-9662-7a1413fc9a59", "b31036d6-76c5-45d9-8e82-ad9bd73b4c4e", "b3d88a6f-8c40-480e-b055-8b00a5e04129", "c10d8fa5-0b9f-4648-99cc-d0f53fa2ea5d", "e91225b6-a1aa-4769-9e6c-a9b53a73b62a", "fbaa72f2-c13d-44f4-9b85-b7f0d17c1e96"]}, {"id": "kp_0010", "type": "process", "maturity": "verified", "stage_matches": ["idea_only", "supplier_sample", "pre_launch_test", "soft_launch", "scale_iterate"], "occurrence_count": 17, "statement": "Use a runtime artifact writer plus validator for benchmark runs so long HTML/CSV payloads do not depend on a giant model tool call.", "scope": "workflow", "evidence_ids": ["EVID-005"], "source_case_ids": ["batch-live-5stage-opensku-idea-001", "batch-live-5stage-opensku-softlaunch-001", "batch-live-5stage-opensku-supplier-001", "batch-live-smoke-opensku-idea-001", "batch-live-stage2-opensku-prelaunch-002", "batch-live-stage2-opensku-softlaunch-002", "batch-live-stage2-opensku-supplier-002", "batch-live-stage2-rerun-opensku-scale-002", "live-decision-taxonomy-prelaunch-002", "live-demo-portable-coffee-tumbler-001-bundle-writer", "live-demo-portable-coffee-tumbler-001-bundle-writer-final-check", "live-knowledge-injection-opensku-idea-002", "live-knowledge-injection-prelaunch-002", "live-knowledge-injection-v2-opensku-idea-002", "opensku-idea-002", "opensku-prelaunch-001", "opensku-scale-001"], "source_run_ids": ["07e9f507-a291-47d6-820b-c2d3f9662abe", "1992db1e-6cfc-4c84-b477-8711df951af6", "1b509691-6fc1-4df6-949b-0d0214349c76", "350ecafc-e314-4329-9c2f-c0b28787e273", "3673f3a9-6c51-4ed6-bb12-760f4d5bcbf1", "37cfe736-fb6c-410c-a070-fed13e6957fb", "4f73454f-befc-4d04-a719-33942d1cdc74", "6a1e641a-3990-4929-a6e9-90bb3638beb3", "72450b53-1951-4961-a1f5-14f49b3c04e3", "859ef561-d6fe-4827-a506-6ce7d5b65716", "9bdf284d-addd-4e31-abae-319ffe3f1c35", "a5294739-b72f-43ce-9662-7a1413fc9a59", "b31036d6-76c5-45d9-8e82-ad9bd73b4c4e", "b3d88a6f-8c40-480e-b055-8b00a5e04129", "c10d8fa5-0b9f-4648-99cc-d0f53fa2ea5d", "e91225b6-a1aa-4769-9e6c-a9b53a73b62a", "fbaa72f2-c13d-44f4-9b85-b7f0d17c1e96"]}, {"id": "kp_0007", "type": "decision", "maturity": "verified", "stage_matches": ["pre_launch_test"], "occurrence_count": 3, "statement": "Current loop state is Pivot at stage pre_launch_test.", "scope": "workflow", "evidence_ids": ["EVID-001", "EVID-005"], "source_case_ids": ["batch-live-stage2-opensku-prelaunch-002", "live-decision-taxonomy-prelaunch-002", "opensku-prelaunch-001"], "source_run_ids": ["1992db1e-6cfc-4c84-b477-8711df951af6", "350ecafc-e314-4329-9c2f-c0b28787e273", "b31036d6-76c5-45d9-8e82-ad9bd73b4c4e"]}, {"id": "kp_0002", "type": "decision", "maturity": "draft", "stage_matches": ["pre_launch_test"], "occurrence_count": 1, "statement": "Current loop state is Hold at stage pre_launch_test.", "scope": "workflow", "evidence_ids": ["EVID-001", "EVID-005"], "source_case_ids": ["batch-live-stage2-opensku-softlaunch-002"], "source_run_ids": ["b3d88a6f-8c40-480e-b055-8b00a5e04129"]}, {"id": "kp_0006", "type": "decision", "maturity": "draft", "stage_matches": ["pre_launch_test"], "occurrence_count": 1, "statement": "Current loop state is Kill at stage pre_launch_test.", "scope": "workflow", "evidence_ids": ["EVID-001", "EVID-005"], "source_case_ids": ["live-knowledge-injection-prelaunch-002"], "source_run_ids": ["9bdf284d-addd-4e31-abae-319ffe3f1c35"]}]
- missing_final_response_requirements: []
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "685bd73d-f204-43e4-9d74-9d0cc086435c"
  },
  {
    "elapsed_seconds": 5.01,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.02,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 15.04,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 20.04,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.06,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.07,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.08,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.09,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.11,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.12,
    "status": "running",
    "total_tokens": 93902,
    "llm_call_count": 5,
    "message_count": 11
  },
  {
    "elapsed_seconds": 55.13,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 60.13,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 65.15,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 70.16,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 75.17,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 80.17,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 85.19,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 90.2,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 95.21,
    "status": "running",
    "total_tokens": 160046,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 100.22,
    "status": "running",
    "total_tokens": 207921,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 105.24,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 110.24,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 115.26,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 120.27,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 125.28,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 130.29,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 135.31,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 140.32,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 145.33,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 150.34,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 155.34,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 160.36,
    "status": "running",
    "total_tokens": 275043,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 165.36,
    "status": "success",
    "total_tokens": 424038,
    "llm_call_count": 13,
    "message_count": 27
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 0

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e5d71217-3b98-4fa5-94c8-e921911a45a3/threads/opensku-live-rc2-rerun-opensku-prelaunch-001-1782576156/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 验证完成 — 上线决策快照

**案例：** rc2-rerun-opensku-prelaunch-001  
**上新产品阶段：** Pre‑Launch Test（搜索匹配验证）  
**决策：** **Pivot（调整）**

### 核心发现

查询 `salon chair`（按摩椅大类）与候选商品 `solid wood platform bed`（床类）存在根本性的类目不匹配。WANDS 基准数据中没有任何相关性标签将该产品与 "salon chair" 查询关联——查询意图（美发/按摩椅）与产品功能（实木平板床、卧室家具、仅限住宅使用）完全正交。

### 为什么不是 Kill

该 SKU（实木平板床，相思木/橡胶木，4.5★/15条评价，500-800磅承重，5年有限保修）本身具备正向信号，在正确类目下有明确的需求。问题出在查询定位，而非产品本身。

### 建议调整方向

| 维度 | 当前（停止） | 调整后（推进） |
|------|-------------|---------------|
| 目标查询 | `salon chair` | `platform bed` / `solid wood bed frame` / `twin bed frame` |
| 类目 | Massage Chairs | Beds / Bed Frames |
| 受众 | 美发/按摩椅买家 | 为孩子买床的父母、客房买家、首套公寓租户、小空间卧室 |

### 下一轮实验

- **7天搜索匹配测试**，使用修正后的查询词：`twin solid wood platform bed`、`acacia wood bed frame queen`、`low profile platform bed with headboard`
- 在 **Furniture / Bedroom Furniture / Beds & Headboards / Beds / Twin Beds** 类目下收集至少 10 次目标类目曝光信号 + 3 次购买意向信号
- **所有 "salon chair" 相关的推广立即停止**

### 数据局限

所有证据来自公共 WANDS 基准数据集。无商家私有指标（GMV、CTR、CVR、ROI、广告支出、利润率、退款率、复购率）。商品价格不可用。承重值存在冲突（500 lbs 和 800 lbs 两个值）。合规标识为供应商原始元数据，未经独立验证。

### 已生成的工件

- `launch-war-room.html`
- `evidence-ledger.json`
- `competitor-table.csv`
- `positioning-brief.md`
- `listing-pack.md`
- `content-pack.md`
- `launch-calendar.csv`
- `launch-state.json`
- `promotion-replan.md`
- `knowledge-deltas.json`

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

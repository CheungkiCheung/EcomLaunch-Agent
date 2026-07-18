# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-005
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 7c53bf3d-bec6-4356-99fc-b2aff5cb0efe
- thread_id: opensku-live-batch-opensku-prelaunch-005-1782691838
- user_id: 515e228b-405c-4dbc-a41d-be012efbb4d4
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/uploads/opensku-case.json",
    "size_bytes": 2130,
    "sha256": "fed157a7d639a60ff8c842728ec7590d03bb3d90c2b6c5f4b9b18f61f874191f"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 819,
    "sha256": "054e882745bd4b8c49db68ad825ea40be7241e8650f809942a03b3b15cc784a3"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'write_opensku_artifact_bundle', 'present_files']
- external_search_tool_calls: []
- knowledge_dir: None
- injected_knowledge_patterns: []
- missing_final_response_requirements: ['next_loop_test']
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "7c53bf3d-bec6-4356-99fc-b2aff5cb0efe"
  },
  {
    "elapsed_seconds": 5.02,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.04,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 15.05,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 20.07,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.1,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.11,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.15,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.16,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.17,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.19,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.2,
    "status": "running",
    "total_tokens": 70906,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 65.22,
    "status": "running",
    "total_tokens": 146536,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 70.24,
    "status": "running",
    "total_tokens": 146536,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 75.26,
    "status": "running",
    "total_tokens": 156280,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 80.29,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.3,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.32,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.33,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.35,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.37,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 110.39,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 115.41,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 120.43,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 125.45,
    "status": "running",
    "total_tokens": 223747,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 130.48,
    "status": "running",
    "total_tokens": 271278,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 135.5,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 140.52,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 145.54,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.56,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.58,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 160.59,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 165.61,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 170.62,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 175.63,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 180.65,
    "status": "running",
    "total_tokens": 343183,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 185.67,
    "status": "success",
    "total_tokens": 459020,
    "llm_call_count": 11,
    "message_count": 23
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 0

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/515e228b-405c-4dbc-a41d-be012efbb4d4/threads/opensku-live-batch-opensku-prelaunch-005-1782691838/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 验收简报 — batch-opensku-prelaunch-005

**上新阶段：** pre_launch_test（查询-产品搜索匹配验证）  
**决策：** **Pivot（转向）**

### 诊断摘要

候选产品 **Baldwin Prestige Alcott Passage Knob with Round Rosette**（产品类别：Door Knobs，品类层级：Home Improvement > Door Hardware > Round Door Knobs）与测试查询 **"chair and a half recliner"**（查询类别：Recliners，家具/坐具）之间存在 **完全的品类错配**：

- 查询意图是寻找大型可躺式扶手椅，产品是一款入户门通道球形把手
- WANDS 基准数据中不存在 `query_id=4` + `product_id=4` 的标签行 — 零相关性证据
- 产品本身经过验证：5.0 分评分（70 条评分、42 条评价）、纯铜材质、终身保修、ANSI/BHMA Grade 2 商用级耐久性

**决定依据：** 品类错配属于搜索路径问题，非产品本身问题 → 默认 **Pivot**（非 Kill、非 Hold）。

### 转向建议

- **新目标查询：** `passage door knob round rosette`、`brass interior door knob`、`Baldwin prestige door knob`
- **受众楔子：** 正在升级室内门配件的房主/DIY 装修者（非家具购物者）
- **核心承诺：** "纯铜材质搭配终身保修和商用级耐久性，让每一扇室内门都经得起时间考验"
- **推广调整：** 立刻停止 "chair and a half recliner" 类别下的所有推广投放，转向家装/门配件渠道

### 数据限制

所有证据来自 **公共基准数据 (WANDS benchmarks)**，无任何商户后台指标（GMV、CTR、CVR、ROI、广告花费、退款率、复购率等均不可用）。

### 已生成文档（10 份）

1. `launch-war-room.html`
2. `evidence-ledger.json`
3. `competitor-table.csv`
4. `positioning-brief.md`
5. `listing-pack.md`
6. `content-pack.md`
7. `launch-calendar.csv`
8. `launch-state.json`
9. `promotion-replan.md`
10. `knowledge-deltas.json`

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

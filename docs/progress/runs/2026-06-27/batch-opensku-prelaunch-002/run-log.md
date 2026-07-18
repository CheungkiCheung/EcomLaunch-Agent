# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-002
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: ecccbe2d-2193-4e3f-8263-85a24d6d4f69
- thread_id: opensku-live-batch-opensku-prelaunch-002-1782691117
- user_id: a06872c6-8f0a-4f4c-99af-9c5a0335a114
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/uploads/opensku-case.json",
    "size_bytes": 2433,
    "sha256": "5f4e8c8aaf744ef689c3157bd486a3ee7b19758e4fa0228aa2821c9e9be6d7a7"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 799,
    "sha256": "57ce285a3cc8ac1a040690445007026d890f12197ba8d5bbd79591383a3aa3ce"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'read_file', 'read_file', 'write_opensku_artifact_bundle', 'write_file', 'validate_opensku_artifacts', 'read_file', 'write_file', 'present_files']
- external_search_tool_calls: []
- knowledge_dir: None
- injected_knowledge_patterns: []
- missing_final_response_requirements: []
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "ecccbe2d-2193-4e3f-8263-85a24d6d4f69"
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
    "elapsed_seconds": 15.06,
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
    "elapsed_seconds": 25.09,
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
    "elapsed_seconds": 40.14,
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
    "elapsed_seconds": 50.18,
    "status": "running",
    "total_tokens": 73924,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 55.19,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 60.21,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 65.23,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 70.25,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.27,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 80.29,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.3,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.32,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.33,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.35,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.37,
    "status": "running",
    "total_tokens": 96456,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 110.38,
    "status": "running",
    "total_tokens": 145673,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 115.4,
    "status": "running",
    "total_tokens": 174946,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 120.41,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 125.43,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 130.45,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 135.47,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 140.48,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 145.5,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.52,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.54,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 160.56,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 165.56,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 170.58,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 175.6,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 180.62,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 185.63,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 190.65,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 195.67,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 200.68,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 205.7,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 210.72,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 215.73,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 220.75,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 225.77,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 230.78,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 235.8,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 240.82,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 245.84,
    "status": "running",
    "total_tokens": 191611,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 250.85,
    "status": "success",
    "total_tokens": 512932,
    "llm_call_count": 18,
    "message_count": 37
  }
]

## Artifact Evidence

- artifact_count: 11
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md', 'risk-notes.md']

## Validator

Exit code: 0

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/a06872c6-8f0a-4f4c-99af-9c5a0335a114/threads/opensku-live-batch-opensku-prelaunch-002-1782691117/user-data/outputs
artifact_count=11
status=PASS
```

## Decision

---

## 🔄 上新阶段诊断 & 决策快照

**上新阶段**: `pre_launch_test`（预上线测试）  
**决策**: **Pivot（转向）**

核心发现：查询词 `"smart coffee table"`（智能咖啡桌，Coffee & Cocktail Tables 类目）与产品 `"all-clad 7 qt slow cooker"`（7夸脱慢炖锅，Slow Cookers 类目）存在 **根本性类目错配**。这不是产品本身的缺陷——慢炖锅在厨房电器类目下仍有测试价值——而是查询方向完全跑偏。

### 下一轮测试计划（7天周期）

| 步骤 | 动作 |
|---|---|
| 1 | 爬取该产品已有的 **98条公开评论**，按缺陷类型分类（用户误操作/预期偏差 vs 硬件故障/安全隐患） |
| 2 | 如果可修复问题 >70% → 在全新正确类目下（Slow Cookers）用纠正后的标题和 Listing 重新上线 |
| 3 | 如果硬件故障为主 → 升级为 Kill，放弃该 SKU |
| 4 | 同时测试标题变体，收集搜索匹配信号 |

### 推广调整

**先修 Listing，再谈推广**。当前 2.0 评分在 100 条评价基础上构成严重信任赤字——如果直接投放广告，差评会被放大。必须在纠正类目和标题后，先以真实问答形式坦诚回应评分问题，邀请新买家留下真实体验评语，再考虑投放。

### 数据限制

全部证据来自公共测试数据（wands benchmark fixture）。无任何商业后台指标（GMV、CTR、CVR、ROI、广告花费、退款率、复购率）。无评论原文，无法确认 2.0 评分的具体原因。无价格数据、搜索量数据、转化数据。

### 已生成 11 份交付物

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
- `risk-notes.md`

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

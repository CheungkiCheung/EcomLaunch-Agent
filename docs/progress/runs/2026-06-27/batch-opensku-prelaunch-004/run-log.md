# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-004
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: ca9232c7-b69b-47fb-b754-dfe9228910e5
- thread_id: opensku-live-batch-opensku-prelaunch-004-1782691646
- user_id: 828d90aa-b936-40e0-a5d0-591f66354c0b
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/uploads/opensku-case.json",
    "size_bytes": 2116,
    "sha256": "b654aedde644d8ec6a51810416508537ed3c3efcfb5a2448a9cf383d0176a412"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 805,
    "sha256": "29c83db5c0a3d13625b659fd30620ed08de9c8021a5b26597e002f80d76c9a42"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'write_opensku_artifact_bundle', 'validate_opensku_artifacts', 'present_files']
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
    "run_id": "ca9232c7-b69b-47fb-b754-dfe9228910e5"
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
    "elapsed_seconds": 20.06,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.08,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.1,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.12,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.15,
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
    "elapsed_seconds": 55.18,
    "status": "running",
    "total_tokens": 71764,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 60.2,
    "status": "running",
    "total_tokens": 98035,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 65.22,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 70.23,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.25,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 80.27,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.29,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.31,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.32,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.34,
    "status": "running",
    "total_tokens": 138075,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.36,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 110.38,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 115.4,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 120.41,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 125.43,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 130.44,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 135.47,
    "status": "running",
    "total_tokens": 186492,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 140.48,
    "status": "running",
    "total_tokens": 198690,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 145.5,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.52,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.53,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 160.55,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 165.57,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 170.57,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 175.59,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 180.61,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 185.63,
    "status": "running",
    "total_tokens": 219958,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 190.64,
    "status": "success",
    "total_tokens": 359385,
    "llm_call_count": 12,
    "message_count": 25
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 0

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/828d90aa-b936-40e0-a5d0-591f66354c0b/threads/opensku-live-batch-opensku-prelaunch-004-1782691646/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 上新决策快照 — batch-opensku-prelaunch-004

**上新阶段**：pre_launch_test（搜索匹配评估）

**推荐决策**：**Pivot（转向）**

**核心发现**：搜索词「turquoise pillows」（query_class: Accent Pillows，家居装饰/靠枕）与候选产品「all-clad all professional tools pizza cutter」（product_class: Slicers, Peelers And Graters，厨房工具/披萨切刀）属于**完全不同的产品类别**，不存在任何交叉。WANDS基准数据集中该查询-产品对没有相关性标签，分类级不匹配是结构性的，非创意文案可以弥补。

**转向后的目标**：
- **搜索词**：从「turquoise pillows」→「pizza cutter」、「All-Clad pizza cutter」、「stainless steel pizza cutter」
- **品类**：从 Accent Pillows → Kitchen & Dining / Kitchen Tools & Gadgets / Slicers, Peelers And Graters
- **受众楔子**：从家居装饰购物者 → 家庭烹饪爱好者、All-Clad品牌消费者、厨房工具买家

**下一轮测试**：在修正后的搜索词和品类下执行有边界的预上线搜索匹配测试，收集3-5个同价位公开竞品的对比信号。

**宣传调整**：立即停止所有针对「turquoise pillows」或 Accent Pillows 品类的投放，品类/关键词修正前不启动任何推广。

**数据局限**：本次运行基于公开基准数据集（WANDS）固定快照；无价格数据、无消费者评论原文、无竞品数据、无商家后台指标（GMV/CTR/CVR/ROI/退款率/复购率）。

**已交付工件**（10份）：
- `launch-war-room.html`、`evidence-ledger.json`、`competitor-table.csv`、`positioning-brief.md`、`listing-pack.md`、`content-pack.md`、`launch-calendar.csv`、`launch-state.json`、`promotion-replan.md`、`knowledge-deltas.json`

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

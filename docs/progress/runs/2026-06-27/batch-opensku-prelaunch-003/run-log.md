# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-003
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 256b2628-538a-4f80-8bf0-45431f3e37fb
- thread_id: opensku-live-batch-opensku-prelaunch-003-1782691369
- user_id: 5aa35977-983e-414f-a3d3-5aaecf03b009
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/uploads/opensku-case.json",
    "size_bytes": 2133,
    "sha256": "ea717f8889502322a019bf14fb315293da4526dd4ad252774b2eb2e29d268e35"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 793,
    "sha256": "42eec65b9bb3042b66d2eab36178c75930d2b9b6e826b8a9182879525b4c3bb0"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/uploads/wands.jsonl",
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
    "run_id": "256b2628-538a-4f80-8bf0-45431f3e37fb"
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
    "elapsed_seconds": 25.08,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.09,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.1,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.11,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.15,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.16,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.18,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 65.19,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 70.2,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 75.22,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 80.23,
    "status": "running",
    "total_tokens": 73993,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 85.25,
    "status": "running",
    "total_tokens": 89817,
    "llm_call_count": 4,
    "message_count": 10
  },
  {
    "elapsed_seconds": 90.27,
    "status": "running",
    "total_tokens": 117191,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 95.28,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.29,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.31,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 110.33,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 115.34,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 120.36,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 125.37,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 130.39,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 135.4,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 140.42,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 145.44,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 150.46,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 155.47,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 160.49,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 165.5,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 170.52,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 175.54,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 180.56,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 185.58,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 190.59,
    "status": "running",
    "total_tokens": 144295,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 195.6,
    "status": "running",
    "total_tokens": 198518,
    "llm_call_count": 6,
    "message_count": 14
  },
  {
    "elapsed_seconds": 200.62,
    "status": "running",
    "total_tokens": 331970,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 205.64,
    "status": "running",
    "total_tokens": 331970,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 210.66,
    "status": "running",
    "total_tokens": 331970,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 215.68,
    "status": "running",
    "total_tokens": 331970,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 220.7,
    "status": "running",
    "total_tokens": 344630,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 225.72,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 230.73,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 235.75,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 240.76,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 245.78,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 250.79,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 255.81,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 260.83,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 265.84,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 270.85,
    "status": "running",
    "total_tokens": 400002,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 275.88,
    "status": "success",
    "total_tokens": 556500,
    "llm_call_count": 13,
    "message_count": 26
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 0

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/5aa35977-983e-414f-a3d3-5aaecf03b009/threads/opensku-live-batch-opensku-prelaunch-003-1782691369/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 🎯 OpenSKU 验证完成 — batch-opensku-prelaunch-003

### 验证结果

| 维度 | 结论 |
|------|------|
| **上新阶段** | `pre_launch_test`（搜索匹配测试） |
| **当前决策** | **🔄 Pivot（转向）** |
| **核心发现** | 查询词 "dinosaur" 分类为 **Kids Wall Décor**（儿童墙面装饰），而候选商品 "all-clad electrics 6.5 qt . slow cooker" 属于 **Slow Cookers**（厨房电器）—— 零类别对齐。这是一次明确的搜索匹配失灵。 |
| **为什么不是 Kill** | 商品本身是已上架销售的产品（208 条评分、181 条评价），特征集完整（6.5qt、可编程 26 小时定时器、陶瓷不粘内胆、洗碗机安全、防烫外壳）。没有证据表明产品质量/合规/供应链不可救药。 |
| **转向方向** | 放弃 "dinosaur" 查询词，将目标查询转向 **slow cooker / programmable slow cooker 6.5 qt** 等厨房电器类查询，将品类定位改为 Slow Cookers / Kitchen Appliances。 |
| **主要受众切入点** | 追求便捷的家庭烹饪者——早上备料、晚上到家即享热饭、清洗无负担 |
| **下一轮测试** | 7 天冲刺：在 "slow cooker" 等正确查询词下验证搜索匹配度，测试 3 组标题变体（容量+定时 / 陶瓷不粘+易清洁 / All-Clad 品牌） |

### 推广调整

| 动作 | 内容 |
|------|------|
| **STOP** | 停止在 "dinosaur" 查询词上投放任何资源 |
| **CONTINUE** | 转向厨房电器类查询词，在正确品类路径下进行搜索匹配验证 |

### 数据边界说明

所有证据均来自 **WANDS 公开基准测试数据集**，非实时电商平台数据。以下数据不可用、也未在输出中声明：商品定价、GMV、CTR、CVR、ROI、广告花费、利润率、退货率、复购率、实际销量。评分数据（3.0/208 条评分）来自基准测试集，时间戳与分布不可知。

### 生成的 10 个交付物

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

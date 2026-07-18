# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-001
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 9b2961b2-cc29-4b95-9fd2-04a803226714
- thread_id: opensku-live-batch-opensku-prelaunch-001-1782690951
- user_id: 633c65de-4e53-44f0-998a-e8c3d4cd34bc
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/uploads/opensku-case.json",
    "size_bytes": 2412,
    "sha256": "efa9772e3c02565c4b7e35bf07e035851d74f109a9a08462bcb9402988ef3978"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 778,
    "sha256": "26be7e016bd6ab8ed29968e614722e59135bf62818a3df768a9a5b6d4da772d4"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'read_file', 'read_file', 'write_opensku_artifact_bundle', 'present_files']
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
    "run_id": "9b2961b2-cc29-4b95-9fd2-04a803226714"
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
    "elapsed_seconds": 40.14,
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
    "elapsed_seconds": 55.19,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.2,
    "status": "running",
    "total_tokens": 87537,
    "llm_call_count": 5,
    "message_count": 10
  },
  {
    "elapsed_seconds": 65.22,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 70.23,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 75.25,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 80.27,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 85.28,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 90.3,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 95.32,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 100.34,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 105.35,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 110.36,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 115.37,
    "status": "running",
    "total_tokens": 155181,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 120.39,
    "status": "running",
    "total_tokens": 205237,
    "llm_call_count": 6,
    "message_count": 14
  },
  {
    "elapsed_seconds": 125.41,
    "status": "running",
    "total_tokens": 240796,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 130.43,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 135.44,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 140.47,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 145.49,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 150.51,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 155.52,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 160.54,
    "status": "running",
    "total_tokens": 294582,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 165.56,
    "status": "success",
    "total_tokens": 416333,
    "llm_call_count": 11,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/633c65de-4e53-44f0-998a-e8c3d4cd34bc/threads/opensku-live-batch-opensku-prelaunch-001-1782690951/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 上新决策快照

**查询**：`salon chair`（品类：按摩椅 Massage Chairs）  
**候选产品**：`solid wood platform bed`（实木平板床，品类：Beds）  
**产品评级**：4.5 / 5.0（15 条评价）  
**来源**：WANDS 公开 Benchmark 夹具

### 上新阶段 & 决策

| 维度 | 内容 |
|---|---|
| **上新阶段** | pre_launch_test（上市前测试） |
| **决策方向** | **🔁 Pivot（转向）** |
| **核心原因** | 查询"salon chair"（Massage Chairs 品类）与产品"solid wood platform bed"（Beds 品类）之间存在完全品类错配。WANDS 标签数据中，query_id=0 的 5 条标注全部指向其他产品 ID，没有任何一条联结到 product_id=0。 |

> 根据搜索匹配错位规则：pre_launch_test 搜索匹配失位默认走 **Pivot**（而非 Kill），因为产品本身（实木平板床架）在正确查询下仍然有价值——有 4.5 星评分、15 条评价、实木构造、5 年有限保修等正向信号。

### 转向建议

| 维度 | 建议 |
|---|---|
| **受众楔子** | 25-55 岁房主/租房族，寻求耐用实木卧室家具；首次购买平板床（无需弹簧底座）者；中古现代风装饰爱好者 |
| **核心承诺** | 相思木+橡胶木实木平板床架，无需弹簧底座，14 英寸床底储物空间，中古现代风格，5 年有限保修 |
| **推荐查询** | "solid wood platform bed"、"platform bed no box spring"、"twin platform bed with headboard"、"mid-century modern bed frame" |

### 下一轮测试

- **测试内容**：在正确的 Beds 品类下，以"solid wood platform bed"为查询词进行 bounded pre_launch test
- **收集信号**：20+ 目标搜索者的相关性反馈 + 5+ 购买意向信号（收藏、分享、评论、预购意向）
- **时长**：7 天

### 推广调整

完全放弃"salon chair"/"Massage Chairs"发现路径。将所有 listing、内容和推广资产重定向至 Beds 品类下的目标查询词。更新标题、卖点、内容钩子，聚焦卧室睡眠质量、耐用性和床底储物优势。

### 数据限制说明

所有证据均来自 WANDS 公开 Benchmark 夹具，非实时商户后台数据。无价格、销量、转化率、排名数据或真实评价文本。私有商户指标（GMV、CTR、CVR、ROI、CAC、广告花费、利润率、退款率、复购率）均不可用且未作为实测结果被引用。

### 生成制品（10 个）

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

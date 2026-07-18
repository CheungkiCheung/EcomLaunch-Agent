# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-live-5stage-opensku-prelaunch-001
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 1992db1e-6cfc-4c84-b477-8711df951af6
- thread_id: opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022
- user_id: 8dd462ca-d2f3-4a5d-ae12-32c88323f8fe
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/uploads/opensku-case.json",
    "size_bytes": 2412,
    "sha256": "efa9772e3c02565c4b7e35bf07e035851d74f109a9a08462bcb9402988ef3978"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 778,
    "sha256": "26be7e016bd6ab8ed29968e614722e59135bf62818a3df768a9a5b6d4da772d4"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/uploads/wands.jsonl",
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
- missing_final_response_requirements: []
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "1992db1e-6cfc-4c84-b477-8711df951af6"
  },
  {
    "elapsed_seconds": 5.01,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.03,
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
    "elapsed_seconds": 20.05,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.07,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.08,
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
    "elapsed_seconds": 60.17,
    "status": "running",
    "total_tokens": 69231,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 65.18,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 70.2,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.21,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 80.23,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.25,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.26,
    "status": "running",
    "total_tokens": 89600,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.28,
    "status": "running",
    "total_tokens": 135401,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 100.3,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 105.3,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 110.32,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 115.32,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 120.34,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 125.35,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 130.36,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 135.38,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 140.39,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 145.4,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.42,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.44,
    "status": "running",
    "total_tokens": 148798,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 160.46,
    "status": "success",
    "total_tokens": 262169,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/8dd462ca-d2f3-4a5d-ae12-32c88323f8fe/threads/opensku-live-batch-live-5stage-opensku-prelaunch-001-1782539022/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## ✅ OpenSKU 上新验证完成 — 案例 opensku-prelaunch-001

### 验证摘要

| 维度 | 结果 |
|------|------|
| **当前阶段** | `pre_launch_test`（预发布测试） |
| **推荐决策** | ⚠️ **Pivot（转向）** |
| **验证来源** | WANDS 公开基准测试集（仅此） |

### 核心发现

查询 **"salon chair"** 在 WANDS 中的意图归类为 **按摩椅（Massage Chairs）**，而候选商品 **solid wood platform bed（实木平板床）** 的分类是 **床（Beds）→ 家具/卧室家具/床/双人床**。WANDS 相关性标注显示：查询 ID=0 (salon chair) 的相关商品列表**不含**该床架（product_id=0）。这是一个**基础性品类错配**——两个产品类目之间不存在重叠的用户任务场景。

### 推荐行动

**方向：Pivot（转向）** — 停止将此商品与 "salon chair" 搜索查询关联，**转向床品类目相关查询**。

**下一轮测试（7天）**：针对 3-5 个床品类目相关查询进行测试——
- `twin platform bed`
- `solid wood bed frame`
- `acacia wood bed frame`
- `twin size bed with headboard`
- `platform bed no box spring`

**宣传调整**：
- ❌ **立即停止**所有针对 "salon chair"/按摩椅类查询的广告投放
- ✅ **重新分配预算**至床品类目查询
- 每条查询设定 **stop/continue 规则**：7天内若无正向互动信号则终止

**数据限制**：
- 所有证据来源均为 **WANDS 公开基准测试集**，非实时平台数据
- **不可用数据**：价格、客户评价文本、竞品定价、GMV/CTR/CVR/ROI/广告支出/退款率/复购率等私域指标
- 产品参数为制造商自报，非独立验证（"non-toxic" 需测试报告，"5-year warranty" 需确认条款）
- 15条评价的样本量较小

### 已生成制品（10个文件）

| 文件 | 说明 |
|------|------|
| `launch-war-room.html` | 决策作战室仪表板 |
| `evidence-ledger.json` | 证据分类账（5条条目） |
| `competitor-table.csv` | 竞品映射表 |
| `positioning-brief.md` | 定位简报（含证据限制声明） |
| `listing-pack.md` | 商品列表文案包（含声明就绪度矩阵） |
| `content-pack.md` | 内容资产包（含声明就绪度矩阵） |
| `launch-calendar.csv` | 7天下一轮实验日历 |
| `launch-state.json` | 上新状态快照 |
| `promotion-replan.md` | 宣传调整计划（含 stop/continue 规则） |
| `knowledge-deltas.json` | 知识增量记录 |

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

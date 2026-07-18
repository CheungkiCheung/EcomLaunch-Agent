# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-prelaunch-006
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 7d0d60ef-0450-48d3-a868-56712040a6d1
- thread_id: opensku-live-batch-opensku-prelaunch-006-1782692024
- user_id: f1346222-3534-44d4-bbf1-34028637c6e8
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/uploads/opensku-case.json",
    "size_bytes": 2089,
    "sha256": "83d12a5ae2642fa2901610b87077646b0c195abfbf9c614abb2ff5d2d78c15e6"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 778,
    "sha256": "26be7e016bd6ab8ed29968e614722e59135bf62818a3df768a9a5b6d4da772d4"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/uploads/wands.jsonl",
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
    "run_id": "7d0d60ef-0450-48d3-a868-56712040a6d1"
  },
  {
    "elapsed_seconds": 5.03,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.05,
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
    "elapsed_seconds": 20.09,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.11,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.15,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.16,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.18,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.19,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.21,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.23,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 65.24,
    "status": "running",
    "total_tokens": 73617,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 70.25,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.27,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 80.29,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.3,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.32,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.34,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.35,
    "status": "running",
    "total_tokens": 148179,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.37,
    "status": "running",
    "total_tokens": 196743,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 110.38,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 115.41,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 120.42,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 125.42,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 130.44,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 135.46,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 140.48,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 145.5,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.52,
    "status": "running",
    "total_tokens": 247729,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.54,
    "status": "success",
    "total_tokens": 388562,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/f1346222-3534-44d4-bbf1-34028637c6e8/threads/opensku-live-batch-opensku-prelaunch-006-1782692024/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 🎯 OpenSKU 验证完成 — 案例 `batch-opensku-prelaunch-006`

### 启动阶段诊断：`pre_launch_test`（预上线测试）

**推荐决策：Pivot（转向）**

证据非常明确：查询词 **"salon chair"（沙龙椅）** 属于 **Massage Chairs（按摩椅）** 品类，而候选产品 **"solid wood platform bed"（实木平板床）** 属于 **Furniture > Bedroom > Beds** 品类。WANDS 基准数据中，该查询词下标注为 Exact（精确匹配）的其他产品均为真正的按摩/沙龙椅，而我们的平台床与该查询存在结构性品类错配。

**不选择 Kill（放弃）的原因：** 该产品本身（实木平台床）在其真实品类中具有市场需求——4.5 星评分（15 条评价）、实木结构、双层规格，仍有商业价值。问题出在查询词定位，而非产品本身。

### 🎯 转向方向

| 维度 | 建议 |
|------|------|
| **目标查询词** | `platform bed` / `solid wood bed frame` / `wooden platform bed` |
| **目标品类** | Furniture → Bedroom → Beds → Platform Beds（放弃 Massage Chairs） |
| **受众楔子** | 寻找实木床架、无需弹簧底座的买家（公寓首购、宿舍、客房） |
| **核心承诺** | 实木（金合欢/橡胶木）平板床——无需弹簧底座，自带床头板 |

### 🔄 下一轮测试（7天周期）

在修正后的查询词 `platform bed` 下重新进行搜索匹配验证，收集 ≥20 次合格访问及 ≥5 次购买意向信号（加购、收藏、询单）。

### 📊 推广调整

- 移除所有 **salon chair / massage chair** 查询定位
- 重新归类至 **Furniture > Bedroom > Beds**
- 将全部上架文案改写为针对床架买家
- 内容策略转向家居/卧室场景，放弃美容/沙龙场景

### ⚠️ 数据限制

本验证基于 **公开 WANDS 基准数据**，不含：
- 商家私有指标（GMV / CTR / CVR / ROI / 广告支出 / 利润率 / 退货率 / 复购率）— **全部不可用**
- 搜索量、定价、客户评论原文
- 产品图片或视觉素材

### 📁 已生成工件（10个文件）

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

所有工件已通过 OpenSKU 校验器验证（status=PASS），存储在 `/mnt/user-data/outputs` 目录中。

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

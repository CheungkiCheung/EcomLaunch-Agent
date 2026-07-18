# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-scale-003
Status: PASS

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 83a9f2e6-f925-46c6-86e1-ca0cc0a4c145
- thread_id: opensku-live-batch-opensku-scale-003-1782693992
- user_id: 0a9d49e8-093b-473f-b084-d688c0467215
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/uploads/opensku-case.json",
    "size_bytes": 2274,
    "sha256": "0d1b6e059b6747baf2e4b69e484b0748498a89f4a083de1d1a825daad54d1be5"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 734,
    "sha256": "357247cc464fedd77e63801cef603c51763da10813955dbc5bbb6121e24bae9a"
  },
  {
    "name": "olist.jsonl",
    "virtual_path": "/mnt/user-data/uploads/olist.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/uploads/olist.jsonl",
    "size_bytes": 8444,
    "sha256": "9ad60b3fcbf921e55dec05474cee56c5d76951d97384142a9056270bb79421ad"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  }
]

## Tool Evidence

- present_files_called: True
- artifact_writer_called: True
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'read_file', 'write_opensku_artifact_bundle', 'present_files']
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
    "run_id": "83a9f2e6-f925-46c6-86e1-ca0cc0a4c145"
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
    "elapsed_seconds": 20.08,
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
    "elapsed_seconds": 30.12,
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
    "elapsed_seconds": 45.17,
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
    "elapsed_seconds": 60.22,
    "status": "running",
    "total_tokens": 79314,
    "llm_call_count": 4,
    "message_count": 10
  },
  {
    "elapsed_seconds": 65.24,
    "status": "running",
    "total_tokens": 90917,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 70.26,
    "status": "running",
    "total_tokens": 90917,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.28,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 80.3,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 85.31,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 90.33,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 95.34,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 100.35,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 105.37,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 110.39,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 115.4,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 120.41,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 125.43,
    "status": "running",
    "total_tokens": 171660,
    "llm_call_count": 4,
    "message_count": 13
  },
  {
    "elapsed_seconds": 130.44,
    "status": "running",
    "total_tokens": 227359,
    "llm_call_count": 6,
    "message_count": 15
  },
  {
    "elapsed_seconds": 135.47,
    "status": "running",
    "total_tokens": 244562,
    "llm_call_count": 7,
    "message_count": 18
  },
  {
    "elapsed_seconds": 140.48,
    "status": "running",
    "total_tokens": 285795,
    "llm_call_count": 8,
    "message_count": 20
  },
  {
    "elapsed_seconds": 145.5,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 150.51,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 155.52,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 160.54,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 165.55,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 170.57,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 175.58,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 180.61,
    "status": "running",
    "total_tokens": 295122,
    "llm_call_count": 9,
    "message_count": 21
  },
  {
    "elapsed_seconds": 185.62,
    "status": "success",
    "total_tokens": 407438,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/0a9d49e8-093b-473f-b084-d688c0467215/threads/opensku-live-batch-opensku-scale-003-1782693992/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 上新阶段判断

**阶段：`scale_iterate`（放量迭代期）** — 根据案例文件确认。已有已交付订单和正面的评价信号，无早期阶段阻碍风险。

## 决策方向

**▶ Scale（有节制放量）**

当前证据不支持无限制的全面放量，但支持继续沿现有方向做**有边界的下一轮测试**：

- ✅ **WANDS 公共数据集**确认搜索意图：「dinosaur」→ query_class「Kids Wall Décor」——查询类目匹配成立（高置信度）
- ✅ **Olist 订单**：5/5 按时或提前交付——履约能力信号存在（中等置信度）
- ✅ **评价分数**：[4,5,5,5,5] 均值 4.8——正面情绪（但样本为通用市场评价，非墙饰专用，低置信度）
- ⚠️ **关键数据缺口**：无直接竞品数据、无产品规格/安全认证、无私有商户指标

**不选择 Kill 或 Pivot**：搜索意图匹配已经过验证，订单和评价未出现质量投诉或履约失败的不可挽救信号。不选择 Hold：已存在足够证据进入下一轮有边界的放量测试。

## 核心受众楔子

**搜索恐龙主题男孩房装饰的巴西家长（28-40 岁，孩子 2-7 岁）**，核心购买任务：**「不用装修、不弄脏墙、快速把孩子房间变成一个他喜欢的恐龙世界」**

## 下一轮测试

**14 天有机列表观察实验：**
- 上架一个恐龙墙饰 SKU（标题优化「dinossauro quarto」） vs 一个通用动物主题 SKU
- 采集信号：搜索展示次数、收藏/心愿单数、客户咨询主题
- 最小成功标准：恐龙变体在 7 天内获得 ≥10 次收藏或咨询
- 决策规则：≥5 条咨询且无安装异议 → 继续放量测试广告；<5 条 → 换标题/主图；出现安装异议 → Pivot 安装方式描述

## 推广调整

- 从单一查询「dinosaur」扩展到相邻葡萄牙语查询：`adesivo parede dinossauro infantil`、`decoração quarto dinossauro`、`mural infantil dinossauro`
- 当前渠道不调整，建议记录下 50 个订单的来源以收集归因数据
- 若有机搜索获得 traction，可测试少量搜索广告
- 价格段待首次 14 天运行后验证（若在中价位 59-99 BRL，测试 ±10%）

## 数据局限性

所有私有商户指标（GMV、CTR、CVR、ROI、广告支出、退款率、复购率、利润率）均不可用。Olist 基准数据来自通用巴西市场（2016-2018），非 Kids Wall Décor 专项。无产品规格、安全认证、或竞品数据。证据整体置信度：**低**（因缺乏类目专属数据）。

---

**已生成工件（10 件）：**

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

# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-softlaunch-007
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: e8c33741-cb84-46b7-9c7f-7e9683928b3f
- thread_id: opensku-live-batch-opensku-softlaunch-007-1782693210
- user_id: d26b6bd3-f874-4041-8793-865a72b7b16c
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/uploads/opensku-case.json",
    "size_bytes": 3229,
    "sha256": "95dacb753c6de633ae6ab3db5444bdc2eaeadea85b965ab1b666d70b5a49d022"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 749,
    "sha256": "e73057511d15fbc15a890a562cd9403ef9c8795e4666748509a316f016f7fbc0"
  },
  {
    "name": "olist.jsonl",
    "virtual_path": "/mnt/user-data/uploads/olist.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/uploads/olist.jsonl",
    "size_bytes": 8444,
    "sha256": "9ad60b3fcbf921e55dec05474cee56c5d76951d97384142a9056270bb79421ad"
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
- missing_final_response_requirements: ['next_loop_test']
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "e8c33741-cb84-46b7-9c7f-7e9683928b3f"
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
    "elapsed_seconds": 55.2,
    "status": "running",
    "total_tokens": 73344,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 60.21,
    "status": "running",
    "total_tokens": 128955,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 65.23,
    "status": "running",
    "total_tokens": 128955,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 70.24,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 75.26,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 80.28,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 85.29,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.31,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.33,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.35,
    "status": "running",
    "total_tokens": 171760,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.37,
    "status": "running",
    "total_tokens": 219741,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 110.39,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 115.41,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 120.43,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 125.44,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 130.46,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 135.48,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 140.5,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 145.52,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 150.54,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 155.55,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 160.57,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 165.58,
    "status": "running",
    "total_tokens": 359199,
    "llm_call_count": 5,
    "message_count": 15
  },
  {
    "elapsed_seconds": 170.6,
    "status": "success",
    "total_tokens": 515202,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/d26b6bd3-f874-4041-8793-865a72b7b16c/threads/opensku-live-batch-opensku-softlaunch-007-1782693210/user-data/outputs
artifact_count=10
status=PASS
```

## Decision

## 完成：OpenSKU 柔和启动验证 — `batch-opensku-softlaunch-007`

### 检测结果

| 项目 | 结果 |
|------|------|
| **上新阶段** | `soft_launch`（但实际为零成交存量） |
| **决策** | **Pivot（转舵）** |
| **目标受众楔子** | 手工/DIY爱好者（从泛类"artes"转向更具体的 craft supplies 子类） |
| **核心主张** | "一个可靠的手工创作基材，送货上门" |

### 关键诊断

该 SKU 已上架（产品目录存在），但在 Olist 基准数据样本中 **零订单、零评论、零交易**。相同平台上其他品类（perfumaria, esporte_lazer, bebes, utilidades_domesticas）均有正常销售（已妥投、信用卡支付、评分4-5）。问题不在产品本身无法挽救，**而是当前品类定位/视觉呈现/受众锚定没有奏效**。

### 下一步实验

**品类重新归类测试**（7天周期）：识别产品实际材质和类型 → 将Olist品类从"artes"调整为更具体的子类（artesanato / pintura_desenho / papelaria）→ 补充3-5张照片（目前仅1张）→ 用新的葡萄牙语标题重新上架 → 监控是否产生首次咨询或加购。

### 推广调整

无法从零基线"调整"——需先获取首单。建议：补充产品多角度照片、上架时叠加短期折扣以激励首单、将本品作为高流量品类的交叉销售附加项、联系2-3位手工类微创作者进行试用反馈。

### 数据限制

- 本案例使用 **Olist 公开基准数据**，非真实商家遥测数据
- 该 SKU 在该样本中零订单（不保证完整数据集中也为零）
- 产品规格（材质、类型、表面处理、品牌）均不可获取
- 定价、客户画像、竞争格局均不可获取
- 私人商业指标（GMV、CTR、CVR、ROI、广告支出、利润率、退货率、复购率）**均不可用**

### 已生成并验证的工件

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

所有工件均已通过 OpenSKU 验证器检查。下一步可根据真实产品规格和照片补充后执行品类重归类实验。

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: live-demo-portable-coffee-tumbler-001-validator-tool-900
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: b9151c4d-a093-4920-8ad0-7f08448ee933
- thread_id: opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511
- user_id: 3cfae978-9ece-46c6-9ea4-3685e1f27fa6
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
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "demo-brief.portable-coffee-tumbler.json",
    "virtual_path": "/mnt/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "size_bytes": 1235,
    "sha256": "29cf266db3fcce021d108553ae7c41ab08b3fe0ef7f780487952364f9a32ac7d"
  },
  {
    "name": "amazon_reviews.jsonl",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads/amazon_reviews.jsonl",
    "size_bytes": 8708,
    "sha256": "28169be585f2f0d315f23b826ab094cf221d7e29dfb70c288014244602273818"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  },
  {
    "name": "amazon_reviews.schema.json",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads/amazon_reviews.schema.json",
    "size_bytes": 8023,
    "sha256": "9ae96311794fbfc059b505b575ec7af2438e2625b045ef8e6df3aec87b35bfca"
  },
  {
    "name": "wands.schema.json",
    "virtual_path": "/mnt/user-data/uploads/wands.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/uploads/wands.schema.json",
    "size_bytes": 6217,
    "sha256": "586edfcba16d150a1bdd283f0640f35ed66b9bd1d45a5e9e25d0f49845b39d48"
  }
]

## Tool Evidence

- present_files_called: False
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'read_file', 'read_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file']
- external_search_tool_calls: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "b9151c4d-a093-4920-8ad0-7f08448ee933"
  },
  {
    "elapsed_seconds": 5.08,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.09,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 15.1,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 20.11,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.12,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.14,
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
    "elapsed_seconds": 45.17,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.18,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.19,
    "status": "running",
    "total_tokens": 79120,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 60.2,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 65.21,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 70.22,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 75.22,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 80.23,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 85.25,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 90.26,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 95.27,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 100.28,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 105.29,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 110.3,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 115.31,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 120.32,
    "status": "running",
    "total_tokens": 116714,
    "llm_call_count": 4,
    "message_count": 14
  },
  {
    "elapsed_seconds": 125.33,
    "status": "running",
    "total_tokens": 172392,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 130.34,
    "status": "running",
    "total_tokens": 172392,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 135.35,
    "status": "running",
    "total_tokens": 184193,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 140.36,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 145.37,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 150.38,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 155.39,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 160.4,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 165.42,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 170.43,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 175.44,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 180.45,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 185.46,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 190.47,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 195.48,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 200.49,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 205.5,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 210.51,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 215.52,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 220.53,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 225.54,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 230.56,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 235.57,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 240.58,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 245.59,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 250.6,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 255.61,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 260.62,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 265.63,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 270.64,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 275.65,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 280.66,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 285.67,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 290.69,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 295.69,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 300.7,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 305.71,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 310.72,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 315.74,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 320.74,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 325.76,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 330.77,
    "status": "running",
    "total_tokens": 238345,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 335.77,
    "status": "success",
    "total_tokens": 481956,
    "llm_call_count": 16,
    "message_count": 39
  }
]

## Artifact Evidence

- artifact_count: 9
- missing_required_artifacts: ['launch-war-room.html']
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 1

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs
artifact_count=9
status=FAIL
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs: missing required artifact launch-war-room.html
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/competitor-table.csv: missing CSV columns: competitor, confidence, limitation, observed_claim
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/positioning-brief.md: positioning brief must include Decision:
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/positioning-brief.md: contains private metric claim without unavailable/do-not boundary
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/launch-calendar.csv: missing CSV columns: asset, channel, decision_rule, expected_output, experiment, objective, validation_signal_to_collect
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/promotion-replan.md: promotion-replan.md missing section 'observed signal'
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/promotion-replan.md: promotion-replan.md missing section 'interpretation'
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/promotion-replan.md: promotion-replan.md missing section 'plan change'
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/promotion-replan.md: promotion-replan.md missing section 'next test'
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3cfae978-9ece-46c6-9ea4-3685e1f27fa6/threads/opensku-live-live-demo-portable-coffee-tumbler-001-validator-tool-900-1782533511/user-data/outputs/knowledge-deltas.json: knowledge-deltas.json must be a JSON array
```

## Decision

Now writing the launch-war-room.html — the most comprehensive dashboard file.

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

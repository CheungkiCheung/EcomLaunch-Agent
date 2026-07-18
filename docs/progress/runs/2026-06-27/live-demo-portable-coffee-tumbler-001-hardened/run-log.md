# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: live-demo-portable-coffee-tumbler-001-hardened
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: d84410e8-c84e-442c-a343-3f91e53f2b6c
- thread_id: opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276
- user_id: 114c3af5-9324-426c-915a-8eb9e189b875
- model_provider: deepseek
- model_name: deepseek-v4-flash
- reasoning_effort: medium
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: true
- run_status: timeout
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "demo-brief.portable-coffee-tumbler.json",
    "virtual_path": "/mnt/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "size_bytes": 1235,
    "sha256": "29cf266db3fcce021d108553ae7c41ab08b3fe0ef7f780487952364f9a32ac7d"
  },
  {
    "name": "amazon_reviews.jsonl",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads/amazon_reviews.jsonl",
    "size_bytes": 8708,
    "sha256": "28169be585f2f0d315f23b826ab094cf221d7e29dfb70c288014244602273818"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  },
  {
    "name": "amazon_reviews.schema.json",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads/amazon_reviews.schema.json",
    "size_bytes": 8023,
    "sha256": "9ae96311794fbfc059b505b575ec7af2438e2625b045ef8e6df3aec87b35bfca"
  },
  {
    "name": "wands.schema.json",
    "virtual_path": "/mnt/user-data/uploads/wands.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/uploads/wands.schema.json",
    "size_bytes": 6217,
    "sha256": "586edfcba16d150a1bdd283f0640f35ed66b9bd1d45a5e9e25d0f49845b39d48"
  }
]

## Tool Evidence

- present_files_called: False
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['write_todos', 'task', 'task', 'task', 'write_todos', 'task', 'task', 'read_file', 'read_file']

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "d84410e8-c84e-442c-a343-3f91e53f2b6c"
  },
  {
    "elapsed_seconds": 5.02,
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
    "elapsed_seconds": 15.05,
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
    "elapsed_seconds": 50.14,
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
    "elapsed_seconds": 75.21,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 80.23,
    "status": "running",
    "total_tokens": 118316,
    "llm_call_count": 6,
    "message_count": 14
  },
  {
    "elapsed_seconds": 85.25,
    "status": "running",
    "total_tokens": 159275,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 90.26,
    "status": "running",
    "total_tokens": 159275,
    "llm_call_count": 6,
    "message_count": 16
  },
  {
    "elapsed_seconds": 95.28,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 100.3,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 105.31,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 110.32,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 115.33,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 120.35,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 125.36,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 130.38,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 135.39,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 140.41,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 145.42,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 150.44,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 155.45,
    "status": "running",
    "total_tokens": 184581,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 160.46,
    "status": "running",
    "total_tokens": 239306,
    "llm_call_count": 8,
    "message_count": 20
  },
  {
    "elapsed_seconds": 165.48,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 170.49,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 175.5,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 180.51,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 185.53,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 190.55,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 195.56,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 200.57,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 205.58,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 210.6,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 215.61,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 220.63,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 225.64,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 230.65,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 235.67,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 240.68,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 245.7,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 250.71,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 255.73,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 260.74,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 265.75,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 270.77,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 275.78,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 280.8,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 285.81,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 290.83,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 295.85,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 300.86,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 305.88,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 310.9,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 315.91,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 320.96,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 325.97,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 330.98,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 336.0,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 341.02,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 346.03,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 351.04,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 356.05,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 361.07,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 366.08,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 371.1,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 376.11,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 381.13,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 386.15,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 391.16,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 396.18,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 401.19,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 406.2,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 411.22,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 416.23,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 421.24,
    "status": "running",
    "total_tokens": 279139,
    "llm_call_count": 8,
    "message_count": 21
  },
  {
    "elapsed_seconds": 421.24,
    "status": "timeout_cancel_requested",
    "http_status": 204,
    "body": ""
  }
]

## Artifact Evidence

- artifact_count: 0
- missing_required_artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']
- artifacts: []

## Validator

Exit code: 1

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs
artifact_count=0
status=FAIL
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact launch-war-room.html
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact evidence-ledger.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact competitor-table.csv
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact positioning-brief.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact listing-pack.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact content-pack.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact launch-calendar.csv
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact launch-state.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact promotion-replan.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs: missing required artifact knowledge-deltas.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/114c3af5-9324-426c-915a-8eb9e189b875/threads/opensku-live-live-demo-portable-coffee-tumbler-001-hardened-1782531276/user-data/outputs/evidence-ledger.json: missing evidence-ledger.json
```

## Decision

The asset-studio timed out, but I have the full outputs from market-voc-researcher and evidence-checker saved. Let me read them and then proceed to synthesis.

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: live-demo-portable-coffee-tumbler-001-tool-gated
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 79943e1a-ce18-4755-bccc-8aa478652403
- thread_id: opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167
- user_id: 3413a138-c6aa-4be0-a516-1ab6a670b558
- model_provider: None
- model_name: None
- reasoning_effort: medium
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: true
- opensku_benchmark_fixture_mode: true
- disable_external_search: true
- run_status: error
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "demo-brief.portable-coffee-tumbler.json",
    "virtual_path": "/mnt/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "size_bytes": 1235,
    "sha256": "29cf266db3fcce021d108553ae7c41ab08b3fe0ef7f780487952364f9a32ac7d"
  },
  {
    "name": "amazon_reviews.jsonl",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads/amazon_reviews.jsonl",
    "size_bytes": 8708,
    "sha256": "28169be585f2f0d315f23b826ab094cf221d7e29dfb70c288014244602273818"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  },
  {
    "name": "amazon_reviews.schema.json",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads/amazon_reviews.schema.json",
    "size_bytes": 8023,
    "sha256": "9ae96311794fbfc059b505b575ec7af2438e2625b045ef8e6df3aec87b35bfca"
  },
  {
    "name": "wands.schema.json",
    "virtual_path": "/mnt/user-data/uploads/wands.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/uploads/wands.schema.json",
    "size_bytes": 6217,
    "sha256": "586edfcba16d150a1bdd283f0640f35ed66b9bd1d45a5e9e25d0f49845b39d48"
  }
]

## Tool Evidence

- present_files_called: True
- subagent_types: []
- missing_subagents: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- tool_call_names: ['write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_todos', 'write_file', 'write_todos', 'present_files', 'write_todos']
- external_search_tool_calls: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "79943e1a-ce18-4755-bccc-8aa478652403"
  },
  {
    "elapsed_seconds": 5.01,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 10.02,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 15.03,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 20.04,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 25.05,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 30.06,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 35.07,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 40.08,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 45.09,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 50.1,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.12,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 65.13,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 70.15,
    "status": "running",
    "total_tokens": 63619,
    "llm_call_count": 4,
    "message_count": 9
  },
  {
    "elapsed_seconds": 75.16,
    "status": "running",
    "total_tokens": 74764,
    "llm_call_count": 4,
    "message_count": 10
  },
  {
    "elapsed_seconds": 80.17,
    "status": "running",
    "total_tokens": 95889,
    "llm_call_count": 4,
    "message_count": 11
  },
  {
    "elapsed_seconds": 85.18,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 90.19,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 95.2,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 100.21,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 105.23,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 110.24,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 115.25,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 120.25,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 125.26,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 130.28,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 135.29,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 140.29,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 145.3,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 150.31,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 155.32,
    "status": "running",
    "total_tokens": 145372,
    "llm_call_count": 4,
    "message_count": 12
  },
  {
    "elapsed_seconds": 160.34,
    "status": "running",
    "total_tokens": 187905,
    "llm_call_count": 5,
    "message_count": 13
  },
  {
    "elapsed_seconds": 165.35,
    "status": "running",
    "total_tokens": 365955,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 170.35,
    "status": "running",
    "total_tokens": 365955,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 175.36,
    "status": "running",
    "total_tokens": 365955,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 180.38,
    "status": "running",
    "total_tokens": 377469,
    "llm_call_count": 5,
    "message_count": 14
  },
  {
    "elapsed_seconds": 185.39,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 190.4,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 195.42,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 200.43,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 205.44,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 210.45,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 215.46,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 220.47,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 225.48,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 230.5,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 235.51,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 240.53,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 245.55,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 250.56,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 255.58,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 260.6,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 265.61,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 270.62,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 275.63,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 280.65,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 285.66,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 290.67,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 295.68,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 300.69,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 305.71,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 310.71,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 315.73,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 320.74,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 325.76,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 330.78,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 335.79,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 340.8,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 345.81,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 350.83,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 355.84,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 360.85,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 365.87,
    "status": "running",
    "total_tokens": 452557,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 370.88,
    "status": "error",
    "total_tokens": 756176,
    "llm_call_count": 17,
    "message_count": 41
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 1

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs
artifact_count=10
status=FAIL
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 2 references unknown evidence id 标签的日本品牌
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 3 references unknown evidence id RMB 99-139价格带
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 4 references unknown evidence id RMB 29-59价格带
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 5 references unknown evidence id RMB 149-199价格带
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 6 references unknown evidence id 环保概念
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 7 references unknown evidence id RMB 199+价格带
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/competitor-table.csv: row 8 references unknown evidence id RMB 59-89价格带
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/positioning-brief.md: positioning brief must include Evidence limitations:
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/content-pack.md: content-pack.md must include Claim readiness labels
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/3413a138-c6aa-4be0-a516-1ab6a670b558/threads/opensku-live-live-demo-portable-coffee-tumbler-001-tool-gated-1782532167/user-data/outputs/promotion-replan.md: promotion-replan.md missing section 'stop/continue rule'
```

## Decision



## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

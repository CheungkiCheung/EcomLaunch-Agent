# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: live-runner-timeout-smoke-001
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 427809b1-8358-4610-9e4e-a32627b972be
- thread_id: opensku-live-live-runner-timeout-smoke-001-1782530886
- user_id: 332ac921-a4dd-4ec6-a30b-df07e8255f5e
- model_provider: deepseek
- model_name: deepseek-v4-flash
- reasoning_effort: high
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: true
- run_status: timeout
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "demo-brief.portable-coffee-tumbler.json",
    "virtual_path": "/mnt/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads/demo-brief.portable-coffee-tumbler.json",
    "size_bytes": 1235,
    "sha256": "29cf266db3fcce021d108553ae7c41ab08b3fe0ef7f780487952364f9a32ac7d"
  },
  {
    "name": "amazon_reviews.jsonl",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads/amazon_reviews.jsonl",
    "size_bytes": 8708,
    "sha256": "28169be585f2f0d315f23b826ab094cf221d7e29dfb70c288014244602273818"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  },
  {
    "name": "amazon_reviews.schema.json",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads/amazon_reviews.schema.json",
    "size_bytes": 8023,
    "sha256": "9ae96311794fbfc059b505b575ec7af2438e2625b045ef8e6df3aec87b35bfca"
  },
  {
    "name": "wands.schema.json",
    "virtual_path": "/mnt/user-data/uploads/wands.schema.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/uploads/wands.schema.json",
    "size_bytes": 6217,
    "sha256": "586edfcba16d150a1bdd283f0640f35ed66b9bd1d45a5e9e25d0f49845b39d48"
  }
]

## Tool Evidence

- present_files_called: False
- subagent_types: []
- missing_subagents: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'write_todos', 'web_search', 'web_search', 'web_search', 'web_search']

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "427809b1-8358-4610-9e4e-a32627b972be"
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
    "elapsed_seconds": 20.04,
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
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs
artifact_count=0
status=FAIL
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact launch-war-room.html
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact evidence-ledger.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact competitor-table.csv
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact positioning-brief.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact listing-pack.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact content-pack.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact launch-calendar.csv
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact launch-state.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact promotion-replan.md
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs: missing required artifact knowledge-deltas.json
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/332ac921-a4dd-4ec6-a30b-df07e8255f5e/threads/opensku-live-live-runner-timeout-smoke-001-1782530886/user-data/outputs/evidence-ledger.json: missing evidence-ledger.json
```

## Decision

Now let me start the market research in parallel.

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

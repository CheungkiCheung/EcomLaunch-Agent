# OpenSKU Live Agent Run

Date: 2026-06-27
Case id: batch-opensku-supplier-002
Status: FAIL

## Why

Phase 4 needs one real run through the production gateway path before the agent contract can be considered hardened. This run verifies auth, CSRF, gateway context injection, lead-agent construction, ecom-launch skill loading, live model access, subagent routing, artifact writing, present_files, and external artifact validation.

## Runtime Evidence

- run_id: 3e609cb1-71bc-45b2-a79f-74659eca4ef5
- thread_id: opensku-live-batch-opensku-supplier-002-1782669935
- user_id: e72406ba-b77e-4364-a01b-065e7a6d6719
- model_provider: deepseek
- model_name: deepseek-v4-flash
- reasoning_effort: medium
- mode: ultra
- agent_name: ecom-launch
- subagent_enabled: true
- is_plan_mode: false
- opensku_benchmark_fixture_mode: true
- disable_external_search: true
- run_status: error
- uploads_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/uploads
- outputs_dir: /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs

## Uploaded Fixtures

[
  {
    "name": "opensku-case.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/uploads/opensku-case.json",
    "size_bytes": 2327,
    "sha256": "d2d119558c4e1a1de40c2c43c87d51150be22bf4811b0208cfa12686bd423344"
  },
  {
    "name": "opensku-case-brief.json",
    "virtual_path": "/mnt/user-data/uploads/opensku-case-brief.json",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/uploads/opensku-case-brief.json",
    "size_bytes": 852,
    "sha256": "9ec1ce616ecdc3b41df8dfc2d72a844401dfb92842da3ede68fa226b9fb8f6fa"
  },
  {
    "name": "wands.jsonl",
    "virtual_path": "/mnt/user-data/uploads/wands.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/uploads/wands.jsonl",
    "size_bytes": 11611,
    "sha256": "d08f34401216e202878d89b12b32596e6c82215eaa6e3af6edd026acc1064c25"
  },
  {
    "name": "amazon_reviews.jsonl",
    "virtual_path": "/mnt/user-data/uploads/amazon_reviews.jsonl",
    "host_path": "/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/uploads/amazon_reviews.jsonl",
    "size_bytes": 8708,
    "sha256": "28169be585f2f0d315f23b826ab094cf221d7e29dfb70c288014244602273818"
  }
]

## Tool Evidence

- present_files_called: False
- artifact_writer_called: False
- subagent_types: ['asset-studio', 'evidence-checker', 'growth-analyst', 'market-voc-researcher', 'offer-architect']
- missing_subagents: []
- tool_call_names: ['read_file', 'read_file', 'read_file', 'read_file', 'read_file', 'grep', 'grep', 'read_file', 'read_file', 'read_file', 'task', 'task', 'task', 'task', 'task', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'write_file', 'validate_opensku_artifacts', 'str_replace', 'str_replace', 'write_file', 'read_file', 'read_file', 'read_file', 'write_file', 'write_file', 'write_file', 'read_file', 'write_file', 'write_file']
- external_search_tool_calls: []
- knowledge_dir: None
- injected_knowledge_patterns: []
- missing_final_response_requirements: ['launch_stage', 'next_loop_test', 'promotion_adjustment', 'data_limitations', 'artifact:launch-war-room.html', 'artifact:evidence-ledger.json', 'artifact:competitor-table.csv', 'artifact:positioning-brief.md', 'artifact:listing-pack.md', 'artifact:content-pack.md', 'artifact:launch-calendar.csv', 'artifact:launch-state.json', 'artifact:promotion-replan.md', 'artifact:knowledge-deltas.json']
- final_response_consistency_errors: []

## Poll Log

[
  {
    "elapsed_seconds": 0.0,
    "status": "pending",
    "run_id": "3e609cb1-71bc-45b2-a79f-74659eca4ef5"
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
    "elapsed_seconds": 50.16,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 55.18,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 60.19,
    "status": "running",
    "total_tokens": 0,
    "llm_call_count": 0,
    "message_count": 0
  },
  {
    "elapsed_seconds": 65.21,
    "status": "running",
    "total_tokens": 134637,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 70.22,
    "status": "running",
    "total_tokens": 134637,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 75.24,
    "status": "running",
    "total_tokens": 134637,
    "llm_call_count": 6,
    "message_count": 17
  },
  {
    "elapsed_seconds": 80.25,
    "status": "running",
    "total_tokens": 145947,
    "llm_call_count": 6,
    "message_count": 18
  },
  {
    "elapsed_seconds": 85.27,
    "status": "running",
    "total_tokens": 155800,
    "llm_call_count": 6,
    "message_count": 19
  },
  {
    "elapsed_seconds": 90.29,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 95.3,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 100.32,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 105.34,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 110.35,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 115.37,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 120.37,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 125.39,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 130.41,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 135.42,
    "status": "running",
    "total_tokens": 188907,
    "llm_call_count": 6,
    "message_count": 20
  },
  {
    "elapsed_seconds": 140.44,
    "status": "running",
    "total_tokens": 252578,
    "llm_call_count": 8,
    "message_count": 22
  },
  {
    "elapsed_seconds": 145.45,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 150.47,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 155.48,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 160.5,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 165.51,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 170.52,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 175.53,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 180.54,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 185.55,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 190.56,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 195.57,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 200.58,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 205.59,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 210.6,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 215.62,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 220.63,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 225.64,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 230.65,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 235.66,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 240.68,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 245.69,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 250.7,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 255.71,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 260.72,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 265.72,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 270.74,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 275.74,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 280.75,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 285.76,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 290.77,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 295.79,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 300.8,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 305.81,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 310.82,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 315.84,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 320.85,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 325.86,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 330.87,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 335.88,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 340.89,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 345.91,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 350.92,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 355.93,
    "status": "running",
    "total_tokens": 305148,
    "llm_call_count": 8,
    "message_count": 24
  },
  {
    "elapsed_seconds": 360.95,
    "status": "error",
    "total_tokens": 660493,
    "llm_call_count": 21,
    "message_count": 57
  }
]

## Artifact Evidence

- artifact_count: 10
- missing_required_artifacts: []
- artifacts: ['competitor-table.csv', 'content-pack.md', 'evidence-ledger.json', 'knowledge-deltas.json', 'launch-calendar.csv', 'launch-state.json', 'launch-war-room.html', 'listing-pack.md', 'positioning-brief.md', 'promotion-replan.md']

## Validator

Exit code: 1

```text
bundle=/Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs
artifact_count=10
status=FAIL
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/positioning-brief.md: positioning brief must include Decision:
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 0 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 0 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 0 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 1 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 1 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 1 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 2 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 2 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 2 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 3 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 3 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 3 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 4 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 4 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 4 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 5 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 5 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 5 missing source_case_id or source_run_id
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 6 invalid type None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 6 invalid maturity None
- /Users/zhangqixiang/0_2实习/deepagents/deer-flow/backend/.deer-flow/users/e72406ba-b77e-4364-a01b-065e7a6d6719/threads/opensku-live-batch-opensku-supplier-002-1782669935/user-data/outputs/knowledge-deltas.json: knowledge delta 6 missing source_case_id or source_run_id
```

## Decision

Let me fix the positioning brief to use plain "Decision:" text and the knowledge-deltas with required fields.

## Next

If this run passes, Phase 4 can be closed with the contract tests and live evidence. If it fails, fix the agent contract or artifact instructions and rerun the same case until the real validator passes.

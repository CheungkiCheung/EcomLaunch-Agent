# Agent Contract Hardening

Date: 2026-06-27
Status: in progress

## Thinking

The first real OpenSKU live validation did not fail because the model was unavailable or the gateway path was fake. It failed for a more important product reason: the agent contract allowed the launch loop to dissolve into open-ended public research. That is exactly the distinction between a demo harness and a credible loop-engineering project.

For OpenSKU to be portfolio-grade, "full run" cannot mean "search until time runs out." It must mean:

- bounded evidence collection
- explicit stage decision
- artifact production even under partial evidence
- validator-enforced claim safety
- knowledge capture from failed/partial runs

## Actions

- Added a real live validation runner at `evals/opensku/run_live_agent_validation.py`.
- Proved the real gateway path can create an `ecom-launch` run and call the live model.
- Ran a full live validation attempt for `live-demo-portable-coffee-tumbler-001`.
- Recorded the failure under `docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001/`.
- Changed the runner from blocking `/api/runs/stream` to create-run/poll/cancel.
- Added benchmark-fixture mode instructions to the runner prompt.
- Hardened `skills/custom/ecom-launch/SKILL.md` and `agents/ecom-launch/SOUL.md`:
  - uploaded files and benchmark fixtures must be inspected first
  - benchmark-fixture validation must not do broad web search unless explicitly permitted
  - specialist timeout/partial findings must still lead to artifacts with limitations
- Updated contract tests to lock the new rules.

## Commands

```bash
cd backend
uv run pytest tests/test_ecom_launch_contract.py -q
```

Result:

```text
3 passed, 1 warning
```

Smoke runner behavior check:

```bash
cd backend
uv run python ../evals/opensku/run_live_agent_validation.py --case-id live-runner-timeout-smoke-001 --timeout-seconds 20 --reasoning-effort low --no-subagents
```

Observed behavior:

- real user registration succeeded
- thread creation succeeded
- run creation returned run_id `427809b1-8358-4610-9e4e-a32627b972be`
- runner polled run status
- runner called `/cancel?wait=true&action=interrupt` at 20 seconds
- run became `interrupted`
- evidence files were written under `docs/progress/runs/2026-06-27/live-runner-timeout-smoke-001/`

## Evidence

Primary failure evidence:

```text
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001/run-log.md
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001/validator-output.txt
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001/artifacts-manifest.json
```

Runner smoke evidence:

```text
docs/progress/runs/2026-06-27/live-runner-timeout-smoke-001/run-log.md
docs/progress/runs/2026-06-27/live-runner-timeout-smoke-001/raw-run-events.json
docs/progress/runs/2026-06-27/live-runner-timeout-smoke-001/validator-output.txt
```

## Validation

Passed:

- contract tests for the hardened OpenSKU agent/skill/manual prompt
- real create-run/poll/cancel path in the runner smoke check

Failed:

- first full live OpenSKU validation
- artifact validator for the full live run
- artifact validator for the timeout smoke run, as expected

## Decision

Do not mark Phase 4 complete yet.

The right next move is to rerun the same live case after the benchmark-fixture and timeout rules are in place. If it still ignores the no-search rule or fails to create artifacts, add a stricter workflow scaffold that forces:

```text
read uploads -> extract evidence -> write artifacts -> validate -> present_files
```

before any optional public research.

## Next

Run:

```bash
cd backend
uv run python ../evals/opensku/run_live_agent_validation.py --case-id live-demo-portable-coffee-tumbler-001 --timeout-seconds 420 --reasoning-effort medium
```

Acceptance for the rerun:

- run status is `success`
- all five subagent roles are invoked or explicitly recorded as unavailable with artifacts still produced
- `present_files_called=true`
- all ten required artifacts exist
- validator status is `PASS`
- final response states stage, decision, next-loop test, promotion adjustment, data limitations, and artifact list

---

## Runtime Tool Gate Update

### Thinking

The hardened rerun still failed after all five specialist roles were invoked. The important finding was that prompt-level constraints were not sufficient: `asset-studio` still called external search tools in benchmark-fixture mode and timed out before artifacts were created.

For OpenSKU, benchmark validation must be a real agent run, but it must not be an unbounded public-research run. The correct hardening layer is therefore runtime tool policy:

- `disable_external_search` is a generic run-scoped switch.
- `opensku_benchmark_fixture_mode` implies `disable_external_search`.
- The same filter must apply before lead-agent tool binding and before subagent executor construction.
- The gateway must explicitly forward the new context keys, otherwise live HTTP validation would silently ignore them.

### Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Added failing regression coverage for benchmark tool gating | `backend/tests/test_opensku_benchmark_tool_policy.py` | Initially failed because `filter_tools_by_runtime_constraints` did not exist |
| 2026-06-27 | Added subagent inheritance regression coverage | `backend/tests/test_task_tool_core_logic.py` | Locks that `task` removes `web_search`, `web_fetch`, and `image_search` before specialist execution |
| 2026-06-27 | Added runtime filtering helpers | `backend/packages/harness/deerflow/skills/tool_policy.py` | Centralizes external-search gate and exact tool names |
| 2026-06-27 | Applied filtering before lead tool binding | `backend/packages/harness/deerflow/agents/lead_agent/agent.py` | Lead agent cannot see external search tools when benchmark mode is active |
| 2026-06-27 | Applied filtering before subagent executor construction | `backend/packages/harness/deerflow/tools/builtins/task_tool.py` | Specialist agents inherit the parent run's search gate |
| 2026-06-27 | Forwarded context through the real gateway | `backend/app/gateway/services.py` | `/api/threads/{thread_id}/runs` can now carry the new tool-policy keys |
| 2026-06-27 | Updated live validation runner | `evals/opensku/run_live_agent_validation.py` | Sends both context keys and fails validation if external search is observed |

### Validation

Red test observed before implementation:

```bash
cd backend
uv run pytest tests/test_opensku_benchmark_tool_policy.py tests/test_task_tool_core_logic.py::test_task_tool_filters_external_search_tools_in_opensku_benchmark_mode -q
```

Result:

```text
ImportError: cannot import name 'filter_tools_by_runtime_constraints'
```

Targeted tests after implementation:

```bash
cd backend
uv run pytest tests/test_opensku_benchmark_tool_policy.py tests/test_task_tool_core_logic.py::test_task_tool_filters_external_search_tools_in_opensku_benchmark_mode tests/test_ecom_launch_contract.py -q
```

Result:

```text
8 passed, 1 warning
```

Broader related regression suite:

```bash
cd backend
uv run pytest tests/test_opensku_benchmark_tool_policy.py tests/test_task_tool_core_logic.py tests/test_lead_agent_model_resolution.py tests/test_ecom_launch_contract.py tests/test_lead_agent_skills.py tests/test_subagent_prompt_security.py -q
uv run python -m py_compile ../evals/opensku/run_live_agent_validation.py
```

Result:

```text
76 passed, 1 warning
```

### Decision

Proceed to a new real live validation. Phase 4 is still not complete until the real gateway/model/subagent/artifact path passes with `present_files` and validator evidence.

### Next

Run:

```bash
cd backend
uv run python ../evals/opensku/run_live_agent_validation.py --case-id live-demo-portable-coffee-tumbler-001-tool-gated --timeout-seconds 420 --reasoning-effort medium
```

Acceptance remains strict:

- run status is `success`
- all five required specialist roles are invoked
- no `web_search`, `web_fetch`, or `image_search` tool calls are exposed in benchmark mode
- `present_files_called=true`
- all ten required artifacts exist
- validator status is `PASS`
- final response states stage, decision, next-loop test, promotion adjustment, data limitations, and artifact list

---

## Tool-Gated Live Run Follow-Up

### Thinking

The tool-gated live run moved the failure forward:

- external search calls were eliminated
- all ten required artifacts were written
- `present_files` was called

The run still failed because the agent treated self-audit as natural-language reasoning instead of an executable validator gate. It also called `write_todos` after `present_files`, then hit the graph recursion limit before sending the final Chinese response.

This points to the next product hardening layer: OpenSKU needs a first-class artifact validator tool in the agent runtime, not only an external eval harness.

### Evidence

Run evidence:

```text
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001-tool-gated/run-log.md
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001-tool-gated/artifacts-manifest.json
docs/progress/runs/2026-06-27/live-demo-portable-coffee-tumbler-001-tool-gated/validator-output.txt
```

Key observed facts:

- run_id: `79943e1a-ce18-4755-bccc-8aa478652403`
- run_status: `error`
- external_search_tool_calls: `[]`
- artifact_count: `10`
- missing_required_artifacts: `[]`
- present_files_called: `true`
- validator status: `FAIL`

Validator failures:

- `competitor-table.csv` used descriptive labels and price bands as `evidence_id` instead of exact `EVID-...` ids from `evidence-ledger.json`
- `positioning-brief.md` missed exact `Evidence limitations:`
- `content-pack.md` missed exact `Claim readiness:`
- `promotion-replan.md` missed exact `stop/continue rule`

### Actions Executed

| Time | Action | Command / File | Result |
|---|---|---|---|
| 2026-06-27 | Added real OpenSKU validator tool tests | `backend/tests/test_opensku_artifact_validator_tool.py` | Red first: module did not exist |
| 2026-06-27 | Added live runner parser regression test | `backend/tests/test_opensku_live_runner.py` | Locks subagent/model extraction from run messages after state summarization |
| 2026-06-27 | Added runtime validator tool | `backend/packages/harness/deerflow/tools/builtins/opensku_artifact_validator.py` | Agent can validate `/mnt/user-data/outputs` without bash |
| 2026-06-27 | Registered validator as built-in tool | `backend/packages/harness/deerflow/tools/builtins/__init__.py`, `backend/packages/harness/deerflow/tools/tools.py` | Exposed to skill policy |
| 2026-06-27 | Allowed validator in EcomLaunch skill | `skills/custom/ecom-launch/SKILL.md` | `validate_opensku_artifacts` is available in ecom runs |
| 2026-06-27 | Hardened exact artifact rules | `skills/custom/ecom-launch/SKILL.md`, `agents/ecom-launch/SOUL.md`, `docs/ecom-launch/manual-run-prompt.md` | Locks exact `EVID-...`, `Evidence limitations:`, `Claim readiness:`, and `stop/continue rule` |
| 2026-06-27 | Bounded live runner finalization | `evals/opensku/run_live_agent_validation.py` | Default `is_plan_mode=false`; prompt requires `present_files -> final answer -> stop` |

### Validation

Targeted tool and contract tests:

```bash
cd backend
uv run pytest tests/test_opensku_artifact_validator_tool.py tests/test_opensku_live_runner.py tests/test_opensku_benchmark_tool_policy.py tests/test_task_tool_core_logic.py::test_task_tool_filters_external_search_tools_in_opensku_benchmark_mode tests/test_ecom_launch_contract.py -q
```

Result:

```text
11 passed, 1 warning
```

Broader related regression suite:

```bash
cd backend
uv run pytest tests/test_opensku_artifact_validator_tool.py tests/test_opensku_live_runner.py tests/test_opensku_benchmark_tool_policy.py tests/test_task_tool_core_logic.py tests/test_lead_agent_model_resolution.py tests/test_tool_deduplication.py tests/test_ecom_launch_contract.py tests/test_opensku_artifact_validators.py tests/test_lead_agent_skills.py tests/test_subagent_prompt_security.py -q
uv run python -m py_compile ../evals/opensku/run_live_agent_validation.py
```

Result:

```text
88 passed, 1 warning
```

### Decision

Run a new live validation with the validator tool exposed and plan mode off by default. Phase 4 is still not complete until this passes.

### Next

```bash
cd backend
uv run python ../evals/opensku/run_live_agent_validation.py --case-id live-demo-portable-coffee-tumbler-001-validator-tool --timeout-seconds 420 --reasoning-effort medium
```

# OpenSKU Live Agent Run Failure

Date: 2026-06-27
Case id: live-demo-portable-coffee-tumbler-001
Status: FAIL

## Thinking

Phase 4 requires a real OpenSKU run through the production gateway path before the agent contract can be considered hardened. A short model probe had already shown live model access. This run was intended to verify the complete path: authenticated request, CSRF, gateway context injection, lead-agent construction, `ecom-launch` skill loading, subagent execution, artifact writing, `present_files`, and artifact validator acceptance.

The run intentionally used a realistic coffee tumbler brief and public fixture uploads. The expected behavior was not a small smoke response; it was a full adaptive launch-loop artifact set.

## Actions

- Created a real test user through `/api/v1/auth/register`.
- Staged public benchmark fixture uploads under the thread's `/mnt/user-data/uploads` mapping.
- Called the gateway run path with `agent_name=ecom-launch`, `mode=ultra`, `is_plan_mode=true`, `subagent_enabled=true`, and `reasoning_effort=high`.
- Observed real LLM calls to DeepSeek and real web/search/fetch tool activity.
- Interrupted the run after it exceeded the intended 900 second budget and continued external search/fetch loops without creating artifacts.
- Ran the artifact validator against the real outputs directory.

## Commands

```bash
cd backend
uv run python ../evals/opensku/run_live_agent_validation.py --timeout-seconds 900 --reasoning-effort high
```

The runner was interrupted manually because the initial SSE implementation blocked inside `TestClient` while the app kept producing tool logs. The runner has since been changed to create-run/poll/cancel.

Validator command:

```bash
cd backend
uv run python - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, '..')
from evals.opensku.validators.core import validate_artifact_bundle
path = Path('.deer-flow/users/c4d345e6-402a-4113-a7c6-836a16b88009/threads/opensku-live-live-demo-portable-coffee-tumbler-001-1782529769/user-data/outputs')
result = validate_artifact_bundle(path)
print(f'artifact_count={result.artifact_count}')
print(f'status={"PASS" if result.ok else "FAIL"}')
for error in result.errors:
    print(f'- {error}')
PY
```

## Evidence

- run_id: `5c453404-75c8-4918-b9a8-8db8b7718623`
- thread_id: `opensku-live-live-demo-portable-coffee-tumbler-001-1782529769`
- user_id: `c4d345e6-402a-4113-a7c6-836a16b88009`
- model path: `deepseek-reasoner` through gateway-created `ecom-launch`
- observed lead-agent log: `Create Agent(ecom-launch) -> thinking_enabled: True, reasoning_effort: high, model_name: deepseek-reasoner, is_plan_mode: True, subagent_enabled: True`
- observed subagents:
  - `market-voc-researcher`
  - `offer-architect`
  - `growth-analyst`
- observed subagent failures:
  - `offer-architect` timed out after 300 seconds
  - `growth-analyst` timed out after 360 seconds
  - `market-voc-researcher` timed out after 480 seconds
- observed successful external fetches included `consumer.org.hk`, `coffeeao.com`, `chinapp.com`, `coffeeprism.com`, and other pages.
- observed repeated search timeouts from DuckDuckGo/Brave/Mojeek/Yahoo/Wikipedia/Grokipedia paths.
- outputs directory existed but contained zero artifacts.

## Validation

Validator result: FAIL.

The validator found zero artifacts and all required files missing:

```text
launch-war-room.html
evidence-ledger.json
competitor-table.csv
positioning-brief.md
listing-pack.md
content-pack.md
launch-calendar.csv
launch-state.json
promotion-replan.md
knowledge-deltas.json
```

## Decision

Phase 4 is not complete.

The failure is valuable because it exposes the project-level issue the user was worried about: a nominal "full agent" can become an uncontrolled long-running research loop instead of an evidence-governed launch loop. The fix is not to relax acceptance. The fix is to harden the loop:

- benchmark/uploaded fixture mode must avoid broad external web search by default
- subagents need strict evidence budgets
- specialist timeout must degrade into partial evidence, not trigger more broad search
- the lead agent must write artifacts with limitations even when evidence is incomplete
- live runner must use create-run/poll/cancel rather than blocking SSE capture

## Next

1. Contract hardening was updated in `agents/ecom-launch/SOUL.md`, `skills/custom/ecom-launch/SKILL.md`, and `backend/tests/test_ecom_launch_contract.py`.
2. `evals/opensku/run_live_agent_validation.py` was changed to use create-run/poll/cancel and to make benchmark-fixture runs avoid external web research.
3. Rerun `live-demo-portable-coffee-tumbler-001` with the hardened benchmark-fixture contract.
4. Phase 4 can only close after a real live run creates artifacts, calls `present_files`, and passes validators.

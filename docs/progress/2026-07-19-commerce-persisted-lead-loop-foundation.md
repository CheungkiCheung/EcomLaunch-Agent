# Commerce Persisted Lead Loop Foundation

Date: 2026-07-19

## Outcome

The continuous Commerce Lead now has a deterministic, restart-safe foundation and a fresh DeepSeek V4 transaction gate. This milestone does not claim that Fresh Verification, Replan Runs or the complete Commerce product are finished.

Implemented flow:

```text
path.completed
-> persisted PathEvidenceScope (IDs and hashes only)
-> CommerceLeadObserver reloads Case/Event/Evidence/latest Hypothesis/Checkpoint
-> LeadLoopPlanner chooses investigate/replan/wait/answer/stop
-> CommercePathPreparationService prepares only selected missing Paths
-> build_persisted_lead_context joins persisted Evidence with Path allowlists
```

## Contracts added

- `PathEvidenceScope` persists Workspace/Case/Run/Task/Path identity, Context/Artifact hashes and allowed Evidence/Fact/Metric/Anomaly IDs. It never stores API keys, raw rows, Prompt text, response text or Path reasoning.
- `CommerceSubagentCommitter` writes the scope into terminal Path Domain Events. Completed Evidence and its ContextManifest boundary can therefore be reconstructed after process restart.
- `ContextPacketLoader` accepts Path-derived Metric IDs only when the owning completed Path Event proves the persisted scope. Missing, duplicated, cross-Case or scope-escaping Evidence fails closed.
- `PersistedLeadContextPacket` contains only persisted, Barrier-released Evidence and the union of each owning Path allowlist. Raw Path ContextPackets and reasoning history are explicitly excluded.
- A zero-Path Lead context is valid and can produce unknown-only structured output; it cannot fabricate a claim without Evidence.
- `CommerceLeadObserver` reloads state on every turn instead of depending on in-memory Path results or chat history.
- `LeadLoopPlanner` distinguishes `investigate`, `replan`, `wait`, `answer` and `stop`. Existing-conclusion follow-ups schedule no Paths; explicit new angles schedule only routable missing Paths; zero routable Paths return an unknown answer.
- `CommercePathPreparationService` converts only selected Paths into Case-bound `PreparedCommercePath` entries for the existing `CommerceSubagentCoordinator`.

## Verification

```text
PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce
338 passed, 15 real-model tests deselected, exit 0

PYTHONPATH=. .venv/bin/pytest -q tests/commerce/agents/test_continuous_lead_turn_live.py -m real_model -vv
1 passed, exit 0

.venv/bin/ruff check <scoped changed files>
All checks passed

git diff --check
exit 0
```

The live gate used the official DeepSeek endpoint and confirmed `deepseek-v4-flash` for Path, Lead and read-only Answer calls. The accepted Lead synthesis used `3,094` tokens in about `3.69s`; the fresh read-only Answer used `3,445` tokens in about `3.45s`, role `answer`, profile `fast_structured`, one request and zero retry. A prior rejected `indicating` claim exercised the bounded repair path: the original and repair calls used separate Provider IDs, `2,954 + 3,443` tokens, about `3.63s + 2.81s`, and zero provider retries.

## Remaining boundary

- Create a distinct Replan Run for a new investigation angle.
- Replace the legacy Verification path with a fresh-context DeerFlow Verification Subagent.
- Persist verified Hypothesis versions and terminal GoalLoop decisions in the new transaction.

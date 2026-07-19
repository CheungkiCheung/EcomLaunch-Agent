# Commerce Case Agent — Restart Resume Classifier

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic restart classification complete
> Model requests: `0`

## Outcome

The Worker no longer treats every expired lease or process restart as permission to call the external model again.

`RunResumeClassifier` reconstructs a fail-closed decision from the latest durable GoalLoop Checkpoint and authoritative Run Event stream:

| Persisted state | Disposition | May call external model automatically? |
| --- | --- | --- |
| No Checkpoint and no Path execution events | `initial_call_allowed` | Yes |
| Pre-call Checkpoint + `path.started`, no completion | `await_retry_decision` | No |
| Pre-call Checkpoint + Path-linked partial Evidence | `reconcile_partial_evidence` | No |
| `path.completed` + consistent post-call Checkpoint | `continue_after_completed_path` | No; skip repeated Path |
| Event/Checkpoint identity or shape mismatch | `invalid_state` | No |

This makes the exactly-once boundary explicit. A pre-call Checkpoint proves that the system intended to call the provider, but after a crash it cannot prove whether the remote request executed. Automatic retry would risk duplicate cost and inconsistent external side effects, so retry requires a future explicit policy or user decision.

## Safety Contracts

- only `initial_call_allowed` can set `may_invoke_external_model=true`;
- a completed Path must have loop iteration at least `1`, no active Path task and Evidence IDs included in the post-call Checkpoint;
- Path-linked partial Evidence is discovered through `evidence.appended.causation_event_id → path.started`;
- a completion event without a post-call Checkpoint is invalid, even if the model output looked successful;
- Workspace/Case/Run identity mismatches fail closed;
- active task IDs must have matching `path.started` events;
- duplicate task or Evidence IDs are rejected by the immutable ResumePlan contract.

`CommerceInvestigationWorker.plan_resume` exposes the decision without mutating state or calling a model. `execute_fulfillment_step` now refuses automatic execution whenever a Checkpoint already exists and reports the classified disposition.

## TDD Evidence

RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.resume'
exit code: 2
```

Focused deterministic tests:

```text
5 passed
exit code: 0
```

Full deterministic Commerce regression:

```text
234 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed. No provider request was made because restart classification is deterministic control-plane behavior.

## Known Limits

- `await_retry_decision` does not yet expose an approval/resume API.
- `reconcile_partial_evidence` identifies partial IDs but does not yet append the missing post-call Checkpoint or prove completeness.
- `continue_after_completed_path` classifies the next safe action but does not yet execute Lead synthesis or another Path.
- Resume token verification and lease release for waiting Runs remain unimplemented.
- Exactly-once external model execution remains impossible; the system manages risk through durable intent, fencing, idempotent IDs and explicit retry authority.

## Next

Implement a resume application service and API for the two non-automatic branches:

1. approve or reject a duplicate-risk retry after showing the preflight/request evidence available;
2. reconcile partial Evidence IDs against deterministic PathResult hashes or mark the Run inconclusive when completeness cannot be proven.

Then allow `continue_after_completed_path` to proceed into the next deterministic route or Lead synthesis without repeating the completed Fulfillment Path.

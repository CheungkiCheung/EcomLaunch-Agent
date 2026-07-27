# Commerce Subagent Committer and Structured Event Bridge

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: Gate C deterministic contracts complete; live parity still blocked

## Outcome

Validated DeerFlow outcomes now cross a dedicated fenced persistence boundary:

```text
DeerFlow SubagentResult
→ CommerceSubagentAdapter
→ CommerceSubagentOutcome + secret-free Tool events
→ CommerceSubagentCommitter
→ one fenced SQL transaction
   ├── immutable Evidence batch
   ├── optimistic Case membership update
   ├── evidence.appended events
   ├── tool.completed / tool.failed events
   ├── path.completed / path.blocked / path.failed event
   └── post-call Checkpoint + run.checkpoint_saved
```

The Adapter still owns no Repository or Unit of Work. The Committer accepts
only typed tasks, outcomes, manifests and checkpoints. It never parses model or
Tool response prose to infer state.

## Safety Contracts

- Lease worker ID and fencing token must match the Commerce task before any SQL write.
- The database lease is rechecked in the same transaction that writes Evidence.
- Completed results are revalidated against task, schema, context, model, Skill,
  Tool allowlist, trace ID and canonical SHA256.
- Evidence may reference only Fact and MetricObservation IDs in the ContextManifest.
- Evidence IDs come unchanged from the validated PathResult and are immutable.
- Path, Tool and pre/post Checkpoint event IDs are deterministic per Task and
  phase, so a repeated terminal commit reuses the existing event stream.
- A Path Evidence set, terminal events and post-checkpoint commit atomically.
- A concurrent Path may rebase on the latest Case version; an actual optimistic
  concurrency race is retried with a fresh Case read.
- Partial pre-existing Evidence IDs and immutable-content mismatches fail closed.
- Blocked, failed, cancelled and timed-out outcomes never write Evidence.
- Runtime Tool payloads are not persisted; only hashes, status, name, call ID and latency are retained.
- The supervisor heartbeats the fenced lease while polling, requests Harness
  cancellation after the bounded poll budget, and refuses to fabricate a
  terminal result when cancellation still has no explicit Harness outcome.
- Restart classification now recognizes completed, blocked and failed Path
  post-checkpoints and resumes the loop/barrier without automatically invoking
  an external model.

## Verification

```text
Committer contracts: 13 passed
Adapter + Committer contracts: 40 passed
Full deterministic Commerce suite: 296 passed, 9 live tests deselected
Relevant Harness/model/middleware suite: 108 passed
Supervisor and restart contracts: 10 passed
Ruff: passed
git diff --check: passed
```

The nine deselected tests are live real-model tests. Gate C completion does not
claim Agent behavior parity. The fresh DeepSeek V4 preflight remains blocked by
the Provider connection, so no Mock, replay, cache, fallback model or increased
retry count was used as live evidence.

Latest fresh preflight after Gate C:

```text
status: blocked_real_model_unavailable
endpoint: https://api.deepseek.com/v1
provider: deerflow.models.patched_deepseek:PatchedChatDeepSeek
request_attempt_count: 1
retry_count: 0
actual_model_identity: null
provider_request_id: null
error_code: APIConnectionError
error_message: Connection error.
```

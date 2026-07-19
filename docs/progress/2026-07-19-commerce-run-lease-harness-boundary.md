# Commerce Case Agent — Fenced Run Lease and Harness Boundary

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic Worker ownership contract complete
> Model requests: `0`

## Outcome

Queued Commerce Runs can now be acquired by exactly one Worker, heartbeated, taken over after expiry and resumed from the latest safe Checkpoint without allowing the old Worker to continue writing.

Implemented:

- `commerce_run_leases` migration and ORM row;
- SHA-256-only lease-token persistence;
- monotonically increasing fencing tokens;
- atomic queued → running transition plus `run.status_changed` event;
- expired-lease takeover plus `run.lease_reacquired` event;
- heartbeat extension without fake business events;
- latest Checkpoint return during reacquisition;
- lease validation inside running-Run Checkpoint transactions;
- stale heartbeat and stale Checkpoint write rejection.

## Concurrency evidence

Ten concurrent acquisition attempts against one queued Run produced:

```text
1 RunLeaseGrant
9 RunLeaseConflictError
```

The winning Worker received fencing token `1`. After its lease expired, a second Worker received fencing token `2` and the latest Checkpoint. The old Worker then failed both heartbeat and Checkpoint writes with `RunLeaseLostError`.

Raw lease tokens are never persisted. The database stores:

```text
sha256(raw_lease_token)
```

The grant carries the raw value as Pydantic `SecretStr` only inside the Worker process.

## Harness boundary decision

The existing DeerFlow runtime was inspected before adding another execution abstraction.

Reused later:

- `run_agent`;
- `StreamBridge`;
- LangGraph Checkpointer;
- Tool/Sandbox middleware;
- token/model telemetry;
- bounded cancellation/shutdown primitives.

Not used as Commerce truth:

- generic `RunManager` status;
- Thread/Assistant run projection;
- generic startup orphan-to-error policy.

The accepted rationale is recorded in `docs/adr/0004-commerce-run-is-domain-source-of-truth.md`.

## Validation

Full deterministic Commerce regression:

```text
216 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

No model request was made because lease ownership, heartbeat, fencing and Checkpoint authorization are deterministic infrastructure behavior.

## Discovered lineage gap

The next executor step requires a reproducible initial `ContextPacket`. Current anomaly analysis writes a derived artifact containing Dataset ID, baseline/current windows, seller metrics and Case IDs, but the persisted Case row does not explicitly reference that Dataset or artifact.

The executor must not recover this information from:

- Case title/summary text;
- deterministic Case ID reverse engineering;
- directory scanning guesses;
- the latest arbitrary Dataset in a Workspace.

Therefore the next task is explicit Case data-lineage persistence before any live Path Agent call.
